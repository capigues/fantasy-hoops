"""State machine handling R1-R4 criteria transitions, grace, cooldown, and audit logging."""

import logging
from typing import Any, Dict, List, Optional
from config import (
    R1_CLEAR_THRESHOLD,
    R1_FLAG_THRESHOLD,
    R1_WINDOW_GAME_DAYS,
    R2_COOLDOWN_GAME_DAYS,
    R2_GRACE_GAME_DAYS,
    R3_COOLDOWN_GAME_DAYS,
    R3_GRACE_GAME_DAYS,
    R4_COOLDOWN_GAME_DAYS,
    R4_GRACE_GAME_DAYS,
)
from db import Database

logger = logging.getLogger(__name__)

CRITERIA = ["R1", "R2", "R3", "R4"]

class StateMachine:
    def __init__(self, db: Database):
        self.db = db

    def update_team_criteria(self, fact: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Update state machine for a team based on daily facts for date D.
        Returns a list of state changes that occurred (for notifications).
        """
        eval_date = fact["eval_date"]
        team_id = fact["team_id"]
        team_name = fact["team_name"]
        is_game_day = fact["is_game_day"]
        is_unknown = fact["is_unknown"]

        # If it's not a game day, skip entirely: no counter changes
        if not is_game_day:
            logger.info("Date %s is not a game day. Skipping team %s (%d)", eval_date, team_name, team_id)
            return []

        # If it's an unknown day, counters pause, state unchanged, never clears flag
        if is_unknown:
            logger.warning("Date %s is unknown/incomplete for team %s (%d). Counters paused.", eval_date, team_name, team_id)
            return []

        state_changes = []

        # Process each criterion
        for crit in CRITERIA:
            current_state = self.db.get_team_criterion_state(team_id, crit)
            if not current_state:
                current_state = {
                    "team_id": team_id,
                    "team_name": team_name,
                    "criterion": crit,
                    "is_flagged": False,
                    "flagged_since": None,
                    "consecutive_violations": 0,
                    "consecutive_clean": 0,
                    "history": []
                }

            is_violating = bool(fact.get(f"{crit.lower()}_violation", False))
            details = fact.get(f"{crit.lower()}_details", {})

            if crit == "R1":
                change = self._update_r1(current_state, eval_date, is_violating, details)
            else:
                grace_days = (
                    R2_GRACE_GAME_DAYS if crit == "R2"
                    else (R3_GRACE_GAME_DAYS if crit == "R3" else R4_GRACE_GAME_DAYS)
                )
                cooldown_days = (
                    R2_COOLDOWN_GAME_DAYS if crit == "R2"
                    else (R3_COOLDOWN_GAME_DAYS if crit == "R3" else R4_COOLDOWN_GAME_DAYS)
                )
                change = self._update_grace_cooldown(
                    current_state, eval_date, is_violating, details, grace_days, cooldown_days
                )

            self.db.save_team_criterion_state(current_state)

            if change:
                self.db.log_state_change(
                    eval_date=eval_date,
                    team_id=team_id,
                    team_name=team_name,
                    criterion=crit,
                    old_state=change["old_state"],
                    new_state=change["new_state"],
                    reason=change["reason"],
                    details=details
                )
                state_changes.append(change)

        return state_changes

    def _update_r1(self, state: Dict[str, Any], eval_date: str,
                   is_violating: bool, details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        R1 trailing 14-game-day sliding window:
        - Flag at >= 4 wasted days
        - Clear at <= 1 wasted day
        - Hysteresis: at 2 or 3 wasted days, retain current state
        """
        history = list(state.get("history", []))

        # Check if date already exists in history (for replay / idempotent update)
        date_index = next((i for i, h in enumerate(history) if h["date"] == eval_date), None)
        if date_index is not None:
            history[date_index] = {"date": eval_date, "violation": is_violating}
        else:
            history.append({"date": eval_date, "violation": is_violating})

        # Sort history by date chronologically
        history.sort(key=lambda h: h["date"])
        state["history"] = history

        # Window: trailing 14 game days
        window = history[-R1_WINDOW_GAME_DAYS:]
        wasted_count = sum(1 for h in window if h.get("violation"))
        was_flagged = state["is_flagged"]
        state_change = None

        if wasted_count >= R1_FLAG_THRESHOLD:
            if not was_flagged:
                state["is_flagged"] = True
                state["flagged_since"] = eval_date
                state_change = {
                    "team_id": state["team_id"],
                    "team_name": state["team_name"],
                    "criterion": "R1",
                    "old_state": "CLEAN",
                    "new_state": "FLAGGED",
                    "reason": f"Wasted active slots on {wasted_count} of the last {len(window)} game days (threshold: {R1_FLAG_THRESHOLD})"
                }
        elif wasted_count <= R1_CLEAR_THRESHOLD:
            if was_flagged:
                state["is_flagged"] = False
                state["flagged_since"] = None
                state_change = {
                    "team_id": state["team_id"],
                    "team_name": state["team_name"],
                    "criterion": "R1",
                    "old_state": "FLAGGED",
                    "new_state": "CLEAN",
                    "reason": f"Wasted active slots dropped to {wasted_count} in 14-day window (clear threshold: {R1_CLEAR_THRESHOLD})"
                }
        else:
            # 2 or 3 wasted days: hysteresis, preserve current state
            pass

        return state_change

    def _update_grace_cooldown(
        self, state: Dict[str, Any], eval_date: str, is_violating: bool,
        details: Dict[str, Any], grace_days: int, cooldown_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        R2, R3, R4 grace & cooldown logic:
        - Grace: 2 game days. Flagged from 3rd consecutive violating game day.
        - Cooldown: 2 game days. Cleared after 2 consecutive clean game days.
        - Violation fixed within grace: never flagged, no cooldown.
        - Reappears during cooldown: stays flagged, cooldown restarts, no new grace.
        - Deterministic replay: history of all game days is maintained.
        """
        history = list(state.get("history", []))
        date_index = next((i for i, h in enumerate(history) if h["date"] == eval_date), None)
        if date_index is not None:
            history[date_index] = {"date": eval_date, "violation": is_violating}
        else:
            history.append({"date": eval_date, "violation": is_violating})

        history.sort(key=lambda h: h["date"])
        state["history"] = history

        # Was flagged before date D
        was_flagged = state["is_flagged"]

        # Re-evaluate sequential state up to date D
        cur_flagged = False
        cur_flagged_since = None
        cur_consec_viol = 0
        cur_consec_clean = 0

        # Run sequential transitions
        for item in history:
            d_date = item["date"]
            v = item["violation"]

            if not cur_flagged:
                if v:
                    cur_consec_viol += 1
                    cur_consec_clean = 0
                    if cur_consec_viol > grace_days:
                        cur_flagged = True
                        cur_flagged_since = d_date
                else:
                    cur_consec_viol = 0
                    cur_consec_clean = 0
            else:
                if v:
                    cur_consec_viol += 1
                    cur_consec_clean = 0
                else:
                    cur_consec_clean += 1
                    if cur_consec_clean >= cooldown_days:
                        cur_flagged = False
                        cur_flagged_since = None
                        cur_consec_viol = 0
                        cur_consec_clean = 0

        state["is_flagged"] = cur_flagged
        state["flagged_since"] = cur_flagged_since
        state["consecutive_violations"] = cur_consec_viol
        state["consecutive_clean"] = cur_consec_clean

        state_change = None
        if not was_flagged and cur_flagged:
            state_change = {
                "team_id": state["team_id"],
                "team_name": state["team_name"],
                "criterion": state["criterion"],
                "old_state": "CLEAN",
                "new_state": "FLAGGED",
                "reason": f"{state['criterion']} violated for {cur_consec_viol} consecutive game days (grace: {grace_days})"
            }
        elif was_flagged and not cur_flagged:
            state_change = {
                "team_id": state["team_id"],
                "team_name": state["team_name"],
                "criterion": state["criterion"],
                "old_state": "FLAGGED",
                "new_state": "CLEAN",
                "reason": f"Completed {cooldown_days} consecutive clean game days cooldown"
            }

        return state_change

    def get_league_eligibility_report(self) -> List[Dict[str, Any]]:
        """
        Produce a consolidated report of all teams and their eligibility.
        A team is TRADE_INELIGIBLE if any criterion is flagged.
        """
        all_states = self.db.get_all_team_states()
        teams_map: Dict[int, Dict[str, Any]] = {}

        for s in all_states:
            tid = s["team_id"]
            if tid not in teams_map:
                teams_map[tid] = {
                    "team_id": tid,
                    "team_name": s["team_name"],
                    "is_flagged": False,
                    "active_flags": [],
                    "earliest_flag_date": None,
                    "criteria_status": {}
                }

            crit = s["criterion"]
            teams_map[tid]["criteria_status"][crit] = s

            if s["is_flagged"]:
                teams_map[tid]["is_flagged"] = True
                teams_map[tid]["active_flags"].append(crit)
                if (teams_map[tid]["earliest_flag_date"] is None or
                    (s["flagged_since"] and s["flagged_since"] < teams_map[tid]["earliest_flag_date"])):
                    teams_map[tid]["earliest_flag_date"] = s["flagged_since"]

        report = list(teams_map.values())
        report.sort(key=lambda t: (not t["is_flagged"], t["team_name"]))
        return report
