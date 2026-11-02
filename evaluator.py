"""Pure, deterministic evaluation of criteria R1 to R4 for NBA Fantasy."""

import logging
from typing import Any, Dict, List, Optional, Set
from config import (
    BENCH_SLOTS,
    INJURY_STATUSES_COUNTED_AS_INJURED,
    IR_SLOTS,
    SLOT_BENCH,
    SLOT_IR,
    STATUS_OUT,
    is_active_slot,
)
from injury_source import InjurySource

logger = logging.getLogger(__name__)

class DailyEvaluator:
    def __init__(self, injury_source: InjurySource, min_roster_size: int = 13, max_ir_slots: int = 1):
        self.injury_source = injury_source
        self.min_roster_size = min_roster_size
        self.max_ir_slots = max_ir_slots

    def evaluate_team_day(
        self,
        eval_date: str,
        team_id: int,
        team_name: str,
        pre_tip_roster: List[Dict[str, Any]],
        final_roster: List[Dict[str, Any]],
        teams_with_games: Set[str],
        is_game_day: bool,
        is_unknown: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluate a single team for date D.
        - Injury statuses are taken from pre_tip_roster (what the manager could act on).
        - Lineup slots are taken from final_roster (how lineup locked).
        """
        fact = {
            "eval_date": eval_date,
            "team_id": team_id,
            "team_name": team_name,
            "is_game_day": is_game_day,
            "is_unknown": is_unknown,
            "r1_violation": False,
            "r1_details": {},
            "r2_violation": False,
            "r2_details": {},
            "r3_violation": False,
            "r3_details": {},
            "r4_violation": False,
            "r4_details": {}
        }

        if is_unknown or not is_game_day:
            return fact

        # Map pre-tip injury status by player_id
        # Also map player NBA team / proTeam
        pre_tip_injuries: Dict[int, str] = {}
        pre_tip_pro_teams: Dict[int, str] = {}
        pre_tip_notes: Dict[int, str] = {}

        for entry in pre_tip_roster:
            pid = entry.get("playerId")
            if pid is None:
                continue
            status = entry.get("injuryStatus", "ACTIVE")
            pre_tip_injuries[pid] = status.upper()
            pro_team = entry.get("proTeam", "")
            if pro_team:
                pre_tip_pro_teams[pid] = pro_team.upper()
            notes = entry.get("injuryNotes", "")
            if notes:
                pre_tip_notes[pid] = notes

        # Parse final roster slots
        # Separate into active slots, bench slots, IR slots
        active_entries = []
        bench_entries = []
        ir_entries = []

        total_players = len(final_roster)

        for entry in final_roster:
            pid = entry.get("playerId")
            slot_id = entry.get("lineupSlotId")
            p_name = entry.get("name", f"Player_{pid}")
            eligible_slots = set(entry.get("eligibleSlots", []))
            pro_team = (entry.get("proTeam") or pre_tip_pro_teams.get(pid, "")).upper()
            injury_status = pre_tip_injuries.get(pid, entry.get("injuryStatus", "ACTIVE")).upper()
            injury_notes = pre_tip_notes.get(pid, entry.get("injuryNotes", ""))

            player_item = {
                "playerId": pid,
                "name": p_name,
                "lineupSlotId": slot_id,
                "eligibleSlots": list(eligible_slots),
                "proTeam": pro_team,
                "injuryStatus": injury_status,
                "injuryNotes": injury_notes
            }

            if slot_id in IR_SLOTS:
                ir_entries.append(player_item)
            elif slot_id in BENCH_SLOTS:
                bench_entries.append(player_item)
            elif is_active_slot(slot_id):
                active_entries.append(player_item)

        # ---------------------------------------------------------------------
        # R1: Wasted Active Slot
        # Active slot is empty OR holds an OUT player, while a healthy eligible
        # bench player was available with an NBA game on date D.
        # ---------------------------------------------------------------------
        # Find healthy eligible bench players who have a game today
        available_bench_candidates = []
        for b in bench_entries:
            # Must NOT be OUT
            if b["injuryStatus"] == STATUS_OUT:
                continue
            # Must have an NBA game today
            p_team = b["proTeam"]
            if p_team and p_team not in teams_with_games:
                continue
            available_bench_candidates.append(b)

        wasted_slots = []
        for a in active_entries:
            is_wasted = False
            waste_reason = ""
            if a["injuryStatus"] == STATUS_OUT:
                is_wasted = True
                waste_reason = f"Active slot {a['lineupSlotId']} holds OUT player {a['name']}"
            elif a["playerId"] is None:
                is_wasted = True
                waste_reason = f"Active slot {a['lineupSlotId']} is empty"

            if is_wasted:
                # Check if any candidate bench player is eligible for this active slot
                eligible_replacements = [
                    cand["name"] for cand in available_bench_candidates
                    if a["lineupSlotId"] in cand["eligibleSlots"]
                ]
                if eligible_replacements:
                    wasted_slots.append({
                        "slot_id": a["lineupSlotId"],
                        "current_player": a["name"],
                        "reason": waste_reason,
                        "eligible_bench_replacements": eligible_replacements
                    })

        if wasted_slots:
            fact["r1_violation"] = True
            fact["r1_details"] = {
                "wasted_slots": wasted_slots,
                "available_healthy_bench": [c["name"] for c in available_bench_candidates]
            }

        # ---------------------------------------------------------------------
        # R2: Unused IR Spot
        # The IR slot is empty while an OUT player sits in an active or bench slot.
        # ---------------------------------------------------------------------
        ir_is_empty = len(ir_entries) == 0
        out_players_not_in_ir = []
        for p in active_entries + bench_entries:
            if p["injuryStatus"] == STATUS_OUT:
                out_players_not_in_ir.append({
                    "playerId": p["playerId"],
                    "name": p["name"],
                    "lineupSlotId": p["lineupSlotId"]
                })

        if ir_is_empty and out_players_not_in_ir:
            fact["r2_violation"] = True
            fact["r2_details"] = {
                "ir_count": len(ir_entries),
                "unplaced_out_players": out_players_not_in_ir
            }

        # ---------------------------------------------------------------------
        # R3: Dead Roster Spot
        # A player officially out for the season is on the roster in any slot (including IR).
        # ---------------------------------------------------------------------
        dead_players = []
        for p in active_entries + bench_entries + ir_entries:
            if self.injury_source.is_player_out_for_season(
                p["playerId"], p["name"], p.get("injuryNotes")
            ):
                dead_players.append({
                    "playerId": p["playerId"],
                    "name": p["name"],
                    "lineupSlotId": p["lineupSlotId"]
                })

        if dead_players:
            fact["r3_violation"] = True
            fact["r3_details"] = {
                "dead_roster_spots": dead_players
            }

        # ---------------------------------------------------------------------
        # R4: Invalid Roster
        # Roster below league minimum or exceeding slot limits.
        # ---------------------------------------------------------------------
        r4_reasons = []
        if total_players < self.min_roster_size:
            r4_reasons.append(
                f"Roster size {total_players} is below league minimum {self.min_roster_size}"
            )
        if len(ir_entries) > self.max_ir_slots:
            r4_reasons.append(
                f"IR slot count {len(ir_entries)} exceeds maximum allowed {self.max_ir_slots}"
            )

        if r4_reasons:
            fact["r4_violation"] = True
            fact["r4_details"] = {
                "reasons": r4_reasons,
                "total_players": total_players,
                "ir_count": len(ir_entries)
            }

        return fact
