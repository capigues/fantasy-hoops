"""Scheduler and workflow runner for pre-tip and 2 AM ET captures and evaluations."""

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from config import DEFAULT_CONFIG, ET_TZ
from db import Database
from espn_client import EspnClient
from evaluator import DailyEvaluator
from injury_source import InjurySource
from notifier import Notifier
from state_machine import StateMachine

logger = logging.getLogger(__name__)

class DailyWorkflowRunner:
    def __init__(
        self,
        db: Database,
        espn_client: EspnClient,
        injury_source: InjurySource,
        notifier: Notifier,
        scoring_period_start_date: Optional[date] = None
    ):
        self.db = db
        self.espn_client = espn_client
        self.injury_source = injury_source
        self.notifier = notifier
        self.evaluator = DailyEvaluator(
            injury_source,
            DEFAULT_CONFIG.min_roster_size,
            DEFAULT_CONFIG.max_ir_slots,
            expected_active_slots=10
        )
        self.state_machine = StateMachine(db)
        self.scoring_period_start_date = scoring_period_start_date

    def get_scoring_period_id_for_date(self, target_date: date) -> int:
        """Dynamically map calendar date to ESPN scoring period id (Season Start: Oct 20, 2026 = SP 1)."""
        start_date = self.scoring_period_start_date or date(2026, 10, 20)
        delta = (target_date - start_date).days + 1
        return max(1, delta)

    def run_pre_tip_capture(self, eval_date_str: str) -> bool:
        """Capture injury statuses and schedule before first tip for eval_date."""
        logger.info("Executing Pre-Tip Capture for %s", eval_date_str)

        # 1. Fetch NBA scoreboard to verify games and teams playing
        ok_sb, sb_data, err_sb = self.espn_client.fetch_nba_scoreboard(eval_date_str)
        if not ok_sb or not sb_data:
            logger.error("Failed to fetch NBA scoreboard for %s: %s", eval_date_str, err_sb)
            self.db.save_snapshot(eval_date_str, "pre_tip", {"error": err_sb}, status="failed")
            return False

        sb_info = self.espn_client.parse_scoreboard_info(sb_data)
        if not sb_info["is_game_day"]:
            logger.info("No NBA games on %s. Recording no-game day.", eval_date_str)
            self.db.save_snapshot(eval_date_str, "pre_tip", {
                "scoreboard": sb_info,
                "is_game_day": False
            }, status="success")
            return True

        # 2. Fetch league rosters for current scoring period
        eval_dt = datetime.strptime(eval_date_str, "%Y-%m-%d").date()
        sp_id = self.get_scoring_period_id_for_date(eval_dt)
        ok_roster, roster_data, err_roster = self.espn_client.fetch_rosters(sp_id)

        if not ok_roster or not roster_data:
            logger.error("Failed to fetch fantasy rosters for %s: %s", eval_date_str, err_roster)
            self.db.save_snapshot(eval_date_str, "pre_tip", {
                "scoreboard": sb_info,
                "error": err_roster
            }, status="failed")
            return False

        # Store raw pre-tip snapshot
        payload = {
            "scoreboard": sb_info,
            "is_game_day": True,
            "roster_data": roster_data
        }
        self.db.save_snapshot(eval_date_str, "pre_tip", payload, status="success")
        logger.info("Pre-tip capture succeeded for %s", eval_date_str)
        return True

    def run_final_capture_and_evaluation(self, eval_date_str: str) -> bool:
        """
        Runs at 2:00 AM ET for date D (eval_date_str).
        Records final locked lineup slots and evaluates R1-R4.
        """
        logger.info("Executing Final Capture & Evaluation for %s", eval_date_str)

        # Check pre-tip snapshot first
        pre_tip_snap = self.db.get_snapshot(eval_date_str, "pre_tip")
        if pre_tip_snap and pre_tip_snap.get("status") == "success":
            pre_tip_payload = pre_tip_snap.get("payload", {})
            sb_info = pre_tip_payload.get("scoreboard", {})
            is_game_day = sb_info.get("is_game_day", False)
            pre_tip_roster_data = pre_tip_payload.get("roster_data", {})
        else:
            # Single-run mode: fetch scoreboard directly for eval_date
            logger.info("Pre-tip snapshot not found for %s. Operating in single-run mode.", eval_date_str)
            ok_sb, sb_data, err_sb = self.espn_client.fetch_nba_scoreboard(eval_date_str)
            if not ok_sb or not sb_data:
                logger.error("Failed to fetch NBA scoreboard for %s: %s", eval_date_str, err_sb)
                return self._record_unknown_day(eval_date_str)
            sb_info = self.espn_client.parse_scoreboard_info(sb_data)
            is_game_day = sb_info.get("is_game_day", False)
            pre_tip_roster_data = None

        if not is_game_day:
            logger.info("%s is not a game day. Skipping evaluation.", eval_date_str)
            self._record_no_game_day(eval_date_str)
            return True

        # Fetch final locked lineups for date D
        eval_dt = datetime.strptime(eval_date_str, "%Y-%m-%d").date()
        sp_id = self.get_scoring_period_id_for_date(eval_dt)
        ok_final, final_roster_data, err_final = self.espn_client.fetch_rosters(sp_id)

        if not ok_final or not final_roster_data:
            logger.error("Final capture failed for %s: %s. Treating as unknown day.", eval_date_str, err_final)
            self.db.save_snapshot(eval_date_str, "final", {"error": err_final}, status="failed")
            return self._record_unknown_day(eval_date_str)

        self.db.save_snapshot(eval_date_str, "final", {"roster_data": final_roster_data}, status="success")

        # Now evaluate each team
        teams_with_games = set(sb_info.get("teams_playing", []))
        teams_pre_tip = self._normalize_teams_roster(pre_tip_roster_data, sp_id) if pre_tip_roster_data else self._normalize_teams_roster(final_roster_data, sp_id)
        teams_final = self._normalize_teams_roster(final_roster_data, sp_id)

        all_state_changes = []

        for tid, t_final in teams_final.items():
            team_name = t_final["team_name"]
            t_pre_tip = teams_pre_tip.get(tid, {})
            pre_tip_players = t_pre_tip.get("players", [])
            final_players = t_final.get("players", [])

            fact = self.evaluator.evaluate_team_day(
                eval_date=eval_date_str,
                team_id=tid,
                team_name=team_name,
                pre_tip_roster=pre_tip_players,
                final_roster=final_players,
                teams_with_games=teams_with_games,
                is_game_day=True,
                is_unknown=False
            )

            self.db.save_daily_fact(fact)
            changes = self.state_machine.update_team_criteria(fact)
            all_state_changes.extend(changes)

        if all_state_changes:
            self.notifier.send_state_change_notifications(all_state_changes)

        logger.info("Evaluation complete for %s. State changes: %d", eval_date_str, len(all_state_changes))
        return True

    def replay_date(self, eval_date_str: str) -> bool:
        """Deterministic replay of evaluation for date D using existing snapshots."""
        logger.info("Replaying evaluation for %s from stored snapshots", eval_date_str)
        pre_tip_snap = self.db.get_snapshot(eval_date_str, "pre_tip")
        final_snap = self.db.get_snapshot(eval_date_str, "final")

        if not pre_tip_snap or not final_snap:
            logger.error("Cannot replay %s: missing stored snapshots", eval_date_str)
            return False

        sb_info = pre_tip_snap["payload"].get("scoreboard", {})
        is_game_day = sb_info.get("is_game_day", False)

        if not is_game_day:
            self._record_no_game_day(eval_date_str)
            return True

        teams_with_games = set(sb_info.get("teams_playing", []))
        teams_pre_tip = self._normalize_teams_roster(pre_tip_snap["payload"].get("roster_data", {}))
        teams_final = self._normalize_teams_roster(final_snap["payload"].get("roster_data", {}))

        all_state_changes = []
        for tid, t_final in teams_final.items():
            team_name = t_final["team_name"]
            t_pre_tip = teams_pre_tip.get(tid, {})
            pre_tip_players = t_pre_tip.get("players", [])
            final_players = t_final.get("players", [])

            fact = self.evaluator.evaluate_team_day(
                eval_date=eval_date_str,
                team_id=tid,
                team_name=team_name,
                pre_tip_roster=pre_tip_players,
                final_roster=final_players,
                teams_with_games=teams_with_games,
                is_game_day=True,
                is_unknown=False
            )
            self.db.save_daily_fact(fact)
            changes = self.state_machine.update_team_criteria(fact)
            all_state_changes.extend(changes)

        if all_state_changes:
            self.notifier.send_state_change_notifications(all_state_changes)
        return True

    def _parse_roster_entry(
        self,
        entry: Dict[str, Any],
        player_stats_map: Dict[int, Dict[str, Any]],
        scoring_period_id: int,
        daily_injury_map: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Parse an individual ESPN roster entry and extract ground-truth minutes and status."""
        pid = entry.get("playerId")
        slot_id = entry.get("lineupSlotId")
        ppe = entry.get("playerPoolEntry", {})
        player_info = ppe.get("player", {}) or player_stats_map.get(pid, {})

        # Stats & minutes extraction
        stats_list = player_info.get("stats", []) or player_stats_map.get(pid, {}).get("stats", [])
        minutes_played = 0.0
        has_played_minutes = False
        if scoring_period_id > 0:
            for s in stats_list:
                if s.get("scoringPeriodId") == scoring_period_id and s.get("statSourceId") == 0:
                    st = s.get("stats", {})
                    min_val = float(st.get("40", 0.0))
                    pts_val = float(s.get("appliedTotal", 0.0))
                    if min_val > 0 or pts_val != 0 or len(st) > 0:
                        minutes_played = max(minutes_played, min_val)
                        has_played_minutes = True

        applied_stat = ppe.get("appliedStatTotal", 0.0)
        if applied_stat and applied_stat != 0:
            has_played_minutes = True

        p_name = player_info.get("fullName") or f"Player_{pid}"
        pro_team = player_info.get("proTeamId") if player_info.get("proTeamId") is not None else player_info.get("proTeam", "")
        raw_inj = player_info.get("injuryStatus") or entry.get("injuryStatus", "ACTIVE")
        injury_notes = ""

        # Ground truth determination:
        # 1. If player logged box score minutes or fantasy points, they were indisputably ACTIVE
        if has_played_minutes:
            injury_status = "ACTIVE"
        # 2. If official game injury report for date D exists, use that authoritative status
        elif daily_injury_map and pid in daily_injury_map:
            injury_status = daily_injury_map[pid].get("status", "ACTIVE")
            injury_notes = daily_injury_map[pid].get("notes", "")
        # 3. Otherwise, retain the player's fantasy injury status (e.g. OUT, DTD, etc.)
        else:
            injury_status = raw_inj

        return {
            "playerId": pid,
            "name": p_name,
            "lineupSlotId": slot_id,
            "injuryStatus": injury_status,
            "rawInjuryStatus": raw_inj,
            "eligibleSlots": player_info.get("eligibleSlots", []),
            "proTeam": str(pro_team) if pro_team is not None else "",
            "minutes_played": minutes_played,
            "has_played": has_played_minutes,
            "injuryNotes": injury_notes
        }

    def _normalize_teams_roster(
        self,
        raw_espn_data: Dict[str, Any],
        scoring_period_id: int = 0,
        daily_injury_map: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        """Normalize ESPN v3 roster response into a clean dictionary by teamId."""
        # 1. Build player stats map and team metadata from raw_espn_data['teams']
        player_stats_map = {}
        team_names = {}
        for t in raw_espn_data.get("teams", []):
            tid = t.get("id")
            raw_loc = t.get('location', '').strip()
            raw_nick = t.get('nickname', '').strip()
            full_nick = f"{raw_loc} {raw_nick}".strip()
            team_names[tid] = t.get("name") or (full_nick if full_nick else f"Team_{tid}")
            for e in t.get("roster", {}).get("entries", []):
                pid = e.get("playerId")
                p = e.get("playerPoolEntry", {}).get("player", {})
                player_stats_map[pid] = p

        # 2. Check if historical lineups exist in schedule -> rosterForCurrentScoringPeriod
        teams = {}
        if scoring_period_id > 0 and raw_espn_data.get("schedule"):
            for m in raw_espn_data.get("schedule", []):
                for side in ["home", "away"]:
                    t_side = m.get(side)
                    if not t_side:
                        continue
                    tid = t_side.get("teamId")
                    if tid is None or tid in teams:
                        continue
                    rf = t_side.get("rosterForCurrentScoringPeriod")
                    if not rf:
                        continue

                    players = [
                        self._parse_roster_entry(entry, player_stats_map, scoring_period_id, daily_injury_map)
                        for entry in rf.get("entries", [])
                    ]
                    teams[tid] = {
                        "team_id": tid,
                        "team_name": team_names.get(tid, f"Team_{tid}"),
                        "players": players
                    }

        # 3. Fallback to teams object (used for current day / pre-tip) if schedule didn't provide rosters
        if not teams:
            for t in raw_espn_data.get("teams", []):
                tid = t.get("id")
                players = [
                    self._parse_roster_entry(entry, player_stats_map, scoring_period_id, daily_injury_map)
                    for entry in t.get("roster", {}).get("entries", [])
                ]
                teams[tid] = {
                    "team_id": tid,
                    "team_name": team_names.get(tid, f"Team_{tid}"),
                    "players": players
                }
        return teams



    def _record_unknown_day(self, eval_date_str: str) -> bool:
        # Create fact with is_unknown = True for all known teams
        all_states = self.db.get_all_team_states()
        team_ids = {s["team_id"]: s["team_name"] for s in all_states}
        if not team_ids:
            team_ids = {1: "Default Team"}

        for tid, tname in team_ids.items():
            fact = {
                "eval_date": eval_date_str,
                "team_id": tid,
                "team_name": tname,
                "is_game_day": True,
                "is_unknown": True,
                "r1_violation": False,
                "r2_violation": False,
                "r3_violation": False,
                "r4_violation": False
            }
            self.db.save_daily_fact(fact)
            self.state_machine.update_team_criteria(fact)
        return False

    def _record_no_game_day(self, eval_date_str: str):
        all_states = self.db.get_all_team_states()
        team_ids = {s["team_id"]: s["team_name"] for s in all_states}
        for tid, tname in team_ids.items():
            fact = {
                "eval_date": eval_date_str,
                "team_id": tid,
                "team_name": tname,
                "is_game_day": False,
                "is_unknown": False,
                "r1_violation": False,
                "r2_violation": False,
                "r3_violation": False,
                "r4_violation": False
            }
            self.db.save_daily_fact(fact)
            self.state_machine.update_team_criteria(fact)
