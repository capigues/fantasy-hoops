"""Unit tests for DailyEvaluator rule evaluation (R1-R4)."""

import unittest
from evaluator import DailyEvaluator
from injury_source import InjurySource
from db import Database
from config import SLOT_PG, SLOT_SG, SLOT_C, SLOT_BENCH, SLOT_IR

class DummyDB:
    def get_season_ending_players(self):
        return {
            999: {
                "player_id": 999,
                "player_name": "Out For Season Star",
                "date_designated": "2026-10-20",
                "source": "commissioner",
                "notes": "ACL tear"
            }
        }

class TestDailyEvaluator(unittest.TestCase):
    def setUp(self):
        self.injury_source = InjurySource(DummyDB())
        self.evaluator = DailyEvaluator(self.injury_source, min_roster_size=13, max_ir_slots=1)
        self.teams_with_games = {"BOS", "LAL", "GSW"}

    def test_r1_wasted_slot_when_eligible_healthy_bench_available(self):
        """Active slot has OUT player, bench has healthy eligible player with game."""
        pre_tip = [
            {"playerId": 1, "injuryStatus": "OUT", "proTeam": "BOS"},
            {"playerId": 2, "injuryStatus": "ACTIVE", "proTeam": "LAL"}
        ]
        final = [
            {"playerId": 1, "name": "Injured Guard", "lineupSlotId": SLOT_PG, "eligibleSlots": [SLOT_PG, SLOT_BENCH], "proTeam": "BOS"},
            {"playerId": 2, "name": "Healthy Guard", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_PG, SLOT_SG, SLOT_BENCH], "proTeam": "LAL"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertTrue(fact["r1_violation"])
        self.assertEqual(len(fact["r1_details"]["wasted_slots"]), 1)

    def test_r1_no_violation_when_whole_bench_injured(self):
        """Active slot has OUT player, but bench player is also OUT."""
        pre_tip = [
            {"playerId": 1, "injuryStatus": "OUT", "proTeam": "BOS"},
            {"playerId": 2, "injuryStatus": "OUT", "proTeam": "LAL"}
        ]
        final = [
            {"playerId": 1, "name": "Injured Guard 1", "lineupSlotId": SLOT_PG, "eligibleSlots": [SLOT_PG, SLOT_BENCH], "proTeam": "BOS"},
            {"playerId": 2, "name": "Injured Guard 2", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_PG, SLOT_SG, SLOT_BENCH], "proTeam": "LAL"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertFalse(fact["r1_violation"])

    def test_r1_no_violation_when_bench_player_has_no_game_today(self):
        """Bench player is healthy, but their NBA team does not play on date D."""
        pre_tip = [
            {"playerId": 1, "injuryStatus": "OUT", "proTeam": "BOS"},
            {"playerId": 2, "injuryStatus": "ACTIVE", "proTeam": "MIA"} # MIA has no game
        ]
        final = [
            {"playerId": 1, "name": "Injured Guard", "lineupSlotId": SLOT_PG, "eligibleSlots": [SLOT_PG, SLOT_BENCH], "proTeam": "BOS"},
            {"playerId": 2, "name": "Healthy Guard", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_PG, SLOT_SG, SLOT_BENCH], "proTeam": "MIA"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertFalse(fact["r1_violation"])

    def test_r1_no_violation_when_bench_player_not_position_eligible(self):
        """Bench player is healthy and has game, but is Center while wasted slot is PG."""
        pre_tip = [
            {"playerId": 1, "injuryStatus": "OUT", "proTeam": "BOS"},
            {"playerId": 2, "injuryStatus": "ACTIVE", "proTeam": "LAL"}
        ]
        final = [
            {"playerId": 1, "name": "Injured Guard", "lineupSlotId": SLOT_PG, "eligibleSlots": [SLOT_PG, SLOT_BENCH], "proTeam": "BOS"},
            {"playerId": 2, "name": "Healthy Center", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_C, SLOT_BENCH], "proTeam": "LAL"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertFalse(fact["r1_violation"])

    def test_r1_questionable_or_dtd_in_active_slot_not_violation(self):
        """Questionable / DTD player in active slot is not considered injured."""
        pre_tip = [
            {"playerId": 1, "injuryStatus": "QUESTIONABLE", "proTeam": "BOS"},
            {"playerId": 2, "injuryStatus": "DAY_TO_DAY", "proTeam": "LAL"},
            {"playerId": 3, "injuryStatus": "ACTIVE", "proTeam": "GSW"}
        ]
        final = [
            {"playerId": 1, "name": "Q Guard", "lineupSlotId": SLOT_PG, "eligibleSlots": [SLOT_PG], "proTeam": "BOS"},
            {"playerId": 2, "name": "DTD Guard", "lineupSlotId": SLOT_SG, "eligibleSlots": [SLOT_SG], "proTeam": "LAL"},
            {"playerId": 3, "name": "Bench Guard", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_PG, SLOT_SG, SLOT_BENCH], "proTeam": "GSW"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertFalse(fact["r1_violation"])

    def test_r2_unused_ir_spot(self):
        """IR is empty while OUT player is on bench."""
        pre_tip = [
            {"playerId": 1, "injuryStatus": "OUT", "proTeam": "BOS"}
        ]
        final = [
            {"playerId": 1, "name": "Injured Bench Player", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_PG, SLOT_BENCH], "proTeam": "BOS"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertTrue(fact["r2_violation"])

    def test_r2_no_violation_when_ir_occupied(self):
        """IR is occupied by an OUT player."""
        pre_tip = [
            {"playerId": 1, "injuryStatus": "OUT", "proTeam": "BOS"}
        ]
        final = [
            {"playerId": 1, "name": "Injured Player", "lineupSlotId": SLOT_IR, "eligibleSlots": [SLOT_IR], "proTeam": "BOS"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertFalse(fact["r2_violation"])

    def test_r3_season_ending_player_on_roster(self):
        """Player with official season-ending designation on roster."""
        pre_tip = [{"playerId": 999, "injuryStatus": "OUT", "proTeam": "BOS"}]
        final = [{"playerId": 999, "name": "Out For Season Star", "lineupSlotId": SLOT_IR, "eligibleSlots": [SLOT_IR], "proTeam": "BOS"}]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertTrue(fact["r3_violation"])

    def test_r4_invalid_roster_below_min_size_or_over_ir_limit(self):
        """Roster below minimum size or over IR limit."""
        # 12 players when min is 13
        pre_tip = [{"playerId": i, "injuryStatus": "ACTIVE", "proTeam": "BOS"} for i in range(12)]
        final = [{"playerId": i, "name": f"P{i}", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_BENCH], "proTeam": "BOS"} for i in range(12)]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", 101, "Team Alpha", pre_tip, final, self.teams_with_games, is_game_day=True
        )
        self.assertTrue(fact["r4_violation"])
        self.assertIn("below league minimum", fact["r4_details"]["reasons"][0])

if __name__ == "__main__":
    unittest.main()
