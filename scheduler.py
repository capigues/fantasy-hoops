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
        self.evaluator = DailyEvaluator(injury_source, DEFAULT_CONFIG.min_roster_size, DEFAULT_CONFIG.max_ir_slots)
        self.state_machine = StateMachine(db)
        self.scoring_period_start_date = scoring_period_start_date

    def get_scoring_period_id_for_date(self, target_date: date) -> int:
        """Dynamically map calendar date to ESPN scoring period id."""
        if self.scoring_period_start_date:
            delta = (target_date - self.scoring_period_start_date).days + 1
            return max(1, delta)
        
        # Query latestScoringPeriod from ESPN
        try:
            ok, data, _ = self.espn_client._get_json(
                f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{self.espn_client.season_year}/segments/0/leagues/{self.espn_client.league_id}?view=mScoreboard"
            )
            if ok and data and "status" in data:
                latest_sp = data["status"].get("latestScoringPeriod", 1)
                today_et = datetime.now(ET_TZ).date()
                day_diff = (today_et - target_date).days
                return max(1, latest_sp - day_diff)
        except Exception as e:
            logger.warning("Could not query dynamic scoring period: %s", e)
        return 1

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
        if not pre_tip_snap or pre_tip_snap.get("status") == "failed":
            logger.warning("Pre-tip snapshot missing or failed for %s. Treating as unknown day.", eval_date_str)
            # Create unknown day facts
            # In an unknown day, counters pause, state unchanged
            return self._record_unknown_day(eval_date_str)

        pre_tip_payload = pre_tip_snap.get("payload", {})
        sb_info = pre_tip_payload.get("scoreboard", {})
        is_game_day = sb_info.get("is_game_day", False)

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
        teams_pre_tip = self._normalize_teams_roster(pre_tip_payload.get("roster_data", {}))
        teams_final = self._normalize_teams_roster(final_roster_data)

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

    def _normalize_teams_roster(self, raw_espn_data: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
        """Normalize ESPN v3 roster response into a clean dictionary by teamId."""
        teams = {}
        for t in raw_espn_data.get("teams", []):
            tid = t.get("id")
            team_name = t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}".strip() or f"Team_{tid}"
            roster = t.get("roster", {})
            entries = roster.get("entries", [])
            players = []
            for entry in entries:
                pid = entry.get("playerId")
                slot_id = entry.get("lineupSlotId")
                injury_status = entry.get("injuryStatus", "ACTIVE")
                player_pool = entry.get("playerPoolEntry", {})
                player_info = player_pool.get("player", {})
                p_name = player_info.get("fullName") or f"Player_{pid}"
                eligible_slots = player_info.get("eligibleSlots", [])
                pro_team = player_info.get("proTeam", "")

                players.append({
                    "playerId": pid,
                    "name": p_name,
                    "lineupSlotId": slot_id,
                    "injuryStatus": injury_status,
                    "eligibleSlots": eligible_slots,
                    "proTeam": pro_team
                })
            teams[tid] = {
                "team_id": tid,
                "team_name": team_name,
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
