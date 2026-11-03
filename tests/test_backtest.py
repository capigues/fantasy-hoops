"""Unit tests for the Historical Backtesting Engine and uniform data structures."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from backtester import BacktestRunner
from espn_client import EspnClient
from evaluator import DailyEvaluator
from injury_source import InjurySource
from scheduler import DailyWorkflowRunner

class TestBacktester(unittest.TestCase):
    def test_daily_game_injuries_parsing(self):
        """Verify fetch_daily_game_injuries parses both injuries block and boxscore DNP."""
        espn = EspnClient()
        mock_summary = {
            "injuries": [
                {
                    "team": {"displayName": "Hornets"},
                    "injuries": [
                        {
                            "athlete": {"id": "1001", "displayName": "Injured Star"},
                            "status": "Out",
                            "details": {"type": "Hamstring"}
                        },
                        {
                            "athlete": {"id": "1002", "displayName": "Probable Star"},
                            "status": "Day-To-Day",
                            "details": {"type": "Rest"}
                        }
                    ]
                }
            ],
            "boxscore": {
                "players": [
                    {
                        "statistics": [
                            {
                                "athletes": [
                                    {
                                        "athlete": {"id": "1003", "displayName": "DNP Coach"},
                                        "didNotPlay": True,
                                        "reason": "COACH'S DECISION"
                                    },
                                    {
                                        "athlete": {"id": "1004", "displayName": "DNP Injury"},
                                        "didNotPlay": True,
                                        "reason": "INJURY - ANKLE"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        with patch.object(espn, "fetch_game_summary", return_value=(True, mock_summary, None)):
            res, athletes = espn.fetch_daily_game_injuries(["99999"])
            self.assertEqual(res[1001]["status"], "OUT")
            self.assertEqual(res[1002]["status"], "DAY_TO_DAY")
            self.assertEqual(res[1003]["status"], "ACTIVE") # Coach's decision is not an injury
            self.assertEqual(res[1004]["status"], "OUT")   # DNP due to injury is OUT
            self.assertIn(1003, athletes)
            self.assertIn(1004, athletes)

    def test_uniform_data_structure(self):
        """Ensure _parse_roster_entry conforms to the exact uniform player data schema."""
        runner = DailyWorkflowRunner(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        raw_entry = {
            "playerId": 555,
            "lineupSlotId": 0,
            "playerPoolEntry": {
                "appliedStatTotal": 25.0,
                "player": {
                    "fullName": "Test Player",
                    "proTeamId": 2,
                    "eligibleSlots": [0, 11, 12]
                }
            }
        }
        injury_map = {555: {"status": "OUT", "notes": "Knee"}}
        
        parsed = runner._parse_roster_entry(
            entry=raw_entry,
            player_stats_map={},
            scoring_period_id=1,
            daily_injury_map=injury_map
        )
        # Even though injury_map said OUT, box score points / minutes proves ACTIVE
        self.assertEqual(parsed["playerId"], 555)
        self.assertEqual(parsed["lineupSlotId"], 0)
        self.assertEqual(parsed["injuryStatus"], "ACTIVE")
        self.assertTrue(parsed["has_played"])
        self.assertEqual(parsed["proTeam"], "2")
        self.assertEqual(parsed["eligibleSlots"], [0, 11, 12])

    def test_backtest_runner_dry_run(self):
        """Verify backtest runner executes in-memory dry run without file writes."""
        runner = BacktestRunner(dry_run=True)
        # Mock scoreboard with 0 games to test clean off-day execution
        with patch.object(runner.espn_client, "fetch_nba_scoreboard", return_value=(True, {"events": []}, None)):
            res = runner.run_backtest(
                start_date=date(2026, 10, 20),
                end_date=date(2026, 10, 21),
                verbose=False
            )
            self.assertEqual(res["total_days"], 2)
            self.assertEqual(res["game_days"], 0)
            self.assertEqual(len(res["violations"]), 0)

if __name__ == "__main__":
    unittest.main()
