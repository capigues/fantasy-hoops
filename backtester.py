"""Historical Backtesting Engine for NBA Fantasy Trade Eligibility System.

Uses historical ESPN fantasy locked lineups, actual box-score minutes, and
official game-day injury reports to evaluate R1-R4 criteria across any date range.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from config import DEFAULT_CONFIG, ET_TZ
from db import Database
from espn_client import EspnClient
from evaluator import DailyEvaluator
from injury_source import InjurySource
from notifier import Notifier
from scheduler import DailyWorkflowRunner
from state_machine import StateMachine

logger = logging.getLogger(__name__)

class BacktestRunner:
    def __init__(
        self,
        db_path: str = "fantasy_backtest.db",
        dry_run: bool = False,
        scoring_period_start_date: Optional[date] = None
    ):
        self.dry_run = dry_run
        self.db_path = ":memory:" if dry_run else db_path
        self.db = Database(self.db_path)
        self.espn_client = EspnClient(
            league_id=DEFAULT_CONFIG.league_id,
            season_year=DEFAULT_CONFIG.season_year,
            espn_s2=DEFAULT_CONFIG.espn_s2,
            swid=DEFAULT_CONFIG.swid
        )
        self.injury_source = InjurySource(self.db)
        self.evaluator = DailyEvaluator(
            self.injury_source,
            min_roster_size=DEFAULT_CONFIG.min_roster_size,
            max_ir_slots=DEFAULT_CONFIG.max_ir_slots,
            expected_active_slots=10
        )
        self.state_machine = StateMachine(self.db)
        self.workflow_runner = DailyWorkflowRunner(
            self.db, self.espn_client, self.injury_source, Notifier(), scoring_period_start_date
        )
        self.scoring_period_start_date = scoring_period_start_date or date(2026, 10, 20)
        # Carryover map for injured players across off-days: {player_id: {status: 'OUT', notes: str}}
        self.injury_carryover: Dict[int, Dict[str, Any]] = {}

    def get_scoring_period_id_for_date(self, target_date: date) -> int:
        delta = (target_date - self.scoring_period_start_date).days + 1
        return max(1, delta)

    def run_backtest(
        self,
        start_date: date,
        end_date: date,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Execute backtest chronologically from start_date to end_date.
        Uniform data discovery -> Uniform evaluation contract -> State Machine.
        """
        if verbose:
            mode_str = "DRY RUN (In-Memory DB)" if self.dry_run else f"Database: {self.db_path}"
            print(f"\n=======================================================")
            print(f"🏀 NBA FANTASY BACKTESTING ENGINE ({mode_str})")
            print(f"Period: {start_date} to {end_date}")
            print(f"=======================================================\n")

        current_dt = start_date
        total_days = 0
        game_days = 0
        all_violations: List[Dict[str, Any]] = []
        all_state_changes: List[Dict[str, Any]] = []

        while current_dt <= end_date:
            date_str = current_dt.isoformat()
            sp_id = self.get_scoring_period_id_for_date(current_dt)
            total_days += 1

            if verbose:
                print(f"📅 Date: {date_str} (Scoring Period {sp_id:2}) ...", end=" ", flush=True)

            # 1. Fetch NBA Scoreboard for date D
            ok_sb, sb_data, err_sb = self.espn_client.fetch_nba_scoreboard(date_str)
            if not ok_sb or not sb_data:
                if verbose:
                    print(f"⚠️ Scoreboard fetch failed: {err_sb}")
                self.workflow_runner._record_unknown_day(date_str)
                current_dt += timedelta(days=1)
                continue

            sb_info = self.espn_client.parse_scoreboard_info(sb_data)
            if not sb_info["is_game_day"]:
                if verbose:
                    print("No NBA games (Off-Day). Skipped.")
                self.workflow_runner._record_no_game_day(date_str)
                current_dt += timedelta(days=1)
                continue

            game_days += 1
            teams_with_games = set(sb_info.get("teams_playing", []))
            events = sb_data.get("events", [])
            event_ids = [e.get("id") for e in events if e.get("id")]

            # 2. Extract official game injury reports and active roster athletes for date D
            daily_game_injuries, boxscore_athletes = self.espn_client.fetch_daily_game_injuries(event_ids)

            # 3. Fetch historical fantasy rosters for date D
            ok_roster, roster_data, err_roster = self.espn_client.fetch_rosters(sp_id)
            if not ok_roster or not roster_data:
                if verbose:
                    print(f"⚠️ Fantasy roster fetch failed: {err_roster}")
                self.workflow_runner._record_unknown_day(date_str)
                current_dt += timedelta(days=1)
                continue

            # 4. Normalize fantasy rosters using uniform data contract
            teams_data = self.workflow_runner._normalize_teams_roster(
                raw_espn_data=roster_data,
                scoring_period_id=sp_id,
                daily_injury_map=daily_game_injuries
            )

            # 5. Evaluate all teams for date D
            day_violations_count = 0
            for tid, tinfo in sorted(teams_data.items()):
                tname = tinfo["team_name"]
                players = tinfo.get("players", [])

                fact = self.evaluator.evaluate_team_day(
                    eval_date=date_str,
                    team_id=tid,
                    team_name=tname,
                    pre_tip_roster=players,
                    final_roster=players,
                    teams_with_games=teams_with_games,
                    is_game_day=True,
                    is_unknown=False,
                    available_nba_athletes=boxscore_athletes
                )

                self.db.save_daily_fact(fact)
                changes = self.state_machine.update_team_criteria(fact)
                if changes:
                    all_state_changes.extend(changes)

                # Check if any violation occurred
                if fact["r1_violation"] or fact["r2_violation"] or fact["r3_violation"] or fact["r4_violation"]:
                    day_violations_count += 1
                    all_violations.append(fact)

            if verbose:
                v_str = f"{day_violations_count} team violation(s)" if day_violations_count > 0 else "All clean"
                print(f"Done ({len(teams_data)} teams evaluated | {v_str})")

            current_dt += timedelta(days=1)

        # Generate final report
        final_report = self.state_machine.get_league_eligibility_report()

        if verbose:
            print(f"\n=======================================================")
            print(f"📊 BACKTEST COMPLETED ({game_days} Game Days Evaluated)")
            print(f"Total Team-Day Violations: {len(all_violations)}")
            print(f"Total State Changes: {len(all_state_changes)}")
            print(f"=======================================================\n")
            notifier = Notifier()
            print(notifier.format_eligibility_table(final_report))

            if all_state_changes:
                print(f"\n📜 STATE TRANSITION LOG ({len(all_state_changes)} transitions):")
                print("-" * 80)
                for sc in all_state_changes:
                    print(f"• [{sc.get('eval_date')}] {sc.get('team_name')} ({sc.get('team_id')}): {sc.get('criterion')} -> {sc.get('new_state')} ({sc.get('reason')})")

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_days": total_days,
            "game_days": game_days,
            "violations": all_violations,
            "state_changes": all_state_changes,
            "final_report": final_report
        }
