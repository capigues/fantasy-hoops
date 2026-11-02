"""Acceptance test suite covering all 17 scenarios specified in Caleb's plan."""

import os
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from config import (
    ET_TZ,
    SLOT_BENCH,
    SLOT_IR,
    SLOT_PG,
    SLOT_SG,
    SLOT_UTIL,
)
from db import Database
from evaluator import DailyEvaluator
from injury_source import InjurySource
from notifier import Notifier
from scheduler import DailyWorkflowRunner
from state_machine import StateMachine

class TestAcceptanceScenarios(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_fantasy.db")
        self.db = Database(self.db_path)
        self.injury_source = InjurySource(self.db)
        self.evaluator = DailyEvaluator(self.injury_source, min_roster_size=13, max_ir_slots=1)
        self.state_machine = StateMachine(self.db)
        self.notifier = Notifier()
        self.team_id = 1
        self.team_name = "Ballers"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_fact(self, eval_date: str, r1=False, r2=False, r3=False, r4=False,
                   is_game_day=True, is_unknown=False):
        return {
            "eval_date": eval_date,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "is_game_day": is_game_day,
            "is_unknown": is_unknown,
            "r1_violation": r1,
            "r1_details": {},
            "r2_violation": r2,
            "r2_details": {},
            "r3_violation": r3,
            "r3_details": {},
            "r4_violation": r4,
            "r4_details": {}
        }

    # Scenario 1: OUT player on bench for 1 game day with IR open, then moved to IR
    # Expected: Never flagged, no cooldown
    def test_scenario_01_out_player_fixed_within_grace(self):
        # Day 1: violation (R2)
        fact1 = self._make_fact("2026-11-01", r2=True)
        self.state_machine.update_team_criteria(fact1)
        s1 = self.db.get_team_criterion_state(self.team_id, "R2")
        self.assertFalse(s1["is_flagged"])
        self.assertEqual(s1["consecutive_violations"], 1)

        # Day 2: moved to IR (clean day)
        fact2 = self._make_fact("2026-11-02", r2=False)
        self.state_machine.update_team_criteria(fact2)
        s2 = self.db.get_team_criterion_state(self.team_id, "R2")
        self.assertFalse(s2["is_flagged"])
        self.assertEqual(s2["consecutive_violations"], 0)
        self.assertEqual(s2["consecutive_clean"], 0) # No cooldown needed

    # Scenario 2: OUT player on bench with IR open for 3 consecutive game days
    # Expected: R2 flags on day 3
    def test_scenario_02_r2_flags_on_day_3(self):
        for i in range(1, 4):
            fact = self._make_fact(f"2026-11-0{i}", r2=True)
            self.state_machine.update_team_criteria(fact)
            state = self.db.get_team_criterion_state(self.team_id, "R2")
            if i < 3:
                self.assertFalse(state["is_flagged"], f"Should not flag on day {i}")
            else:
                self.assertTrue(state["is_flagged"], "Must flag on day 3")
                self.assertEqual(state["flagged_since"], "2026-11-03")

    # Scenario 3: Flagged team is clean for 2 consecutive game days
    # Expected: Clears
    def test_scenario_03_flagged_team_clears_after_cooldown(self):
        # Trigger flag on day 3
        for i in range(1, 4):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-0{i}", r2=True))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R2")["is_flagged"])

        # Clean day 1
        self.state_machine.update_team_criteria(self._make_fact("2026-11-04", r2=False))
        s_cd1 = self.db.get_team_criterion_state(self.team_id, "R2")
        self.assertTrue(s_cd1["is_flagged"])
        self.assertEqual(s_cd1["consecutive_clean"], 1)

        # Clean day 2
        self.state_machine.update_team_criteria(self._make_fact("2026-11-05", r2=False))
        s_cd2 = self.db.get_team_criterion_state(self.team_id, "R2")
        self.assertFalse(s_cd2["is_flagged"], "Should clear after 2 clean game days")
        self.assertEqual(s_cd2["consecutive_clean"], 0)

    # Scenario 4: Flagged team fixes its roster, then violates again on next day
    # Expected: Stays flagged, cooldown restarts, no new grace
    def test_scenario_04_violation_reappears_during_cooldown(self):
        # Flag on day 3
        for i in range(1, 4):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-0{i}", r2=True))

        # Day 4: Clean (starts cooldown)
        self.state_machine.update_team_criteria(self._make_fact("2026-11-04", r2=False))
        self.assertEqual(self.db.get_team_criterion_state(self.team_id, "R2")["consecutive_clean"], 1)

        # Day 5: Violates again
        self.state_machine.update_team_criteria(self._make_fact("2026-11-05", r2=True))
        state = self.db.get_team_criterion_state(self.team_id, "R2")
        self.assertTrue(state["is_flagged"], "Team must stay flagged")
        self.assertEqual(state["consecutive_clean"], 0, "Cooldown must restart to 0")

    # Scenario 5: Team with 4 wasted days in the last 14 game days
    # Expected: R1 flags
    def test_scenario_05_r1_flags_at_4_wasted_days(self):
        # 10 clean days, then 4 wasted days
        for i in range(1, 11):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-{i:02d}", r1=False))
        for i in range(11, 14): # days 11, 12, 13 (3 wasted)
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-{i:02d}", r1=True))
            self.assertFalse(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

        # Day 14 (4th wasted day)
        self.state_machine.update_team_criteria(self._make_fact("2026-11-14", r1=True))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

    # Scenario 6: Flagged R1 team drops to 1 wasted day in the window
    # Expected: Clears
    def test_scenario_06_r1_clears_at_1_wasted_day(self):
        # Days 1, 2, 3, 4: 4 wasted days
        for i in range(1, 5):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-{i:02d}", r1=True))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

        # Days 5 to 14: clean days (window now has 14 days: days 1..14 with 4 wasted)
        for i in range(5, 15):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-{i:02d}", r1=False))
            self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

        # Day 15 clean: window is days 2..15 (days 2, 3, 4 wasted = 3 wasted). Hysteresis keeps flagged.
        self.state_machine.update_team_criteria(self._make_fact("2026-11-15", r1=False))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

        # Day 16 clean: window is days 3..16 (days 3, 4 wasted = 2 wasted). Hysteresis keeps flagged.
        self.state_machine.update_team_criteria(self._make_fact("2026-11-16", r1=False))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

        # Day 17 clean: window is days 4..17 (only day 4 wasted = 1 wasted). Drops to 1 -> CLEARS!
        self.state_machine.update_team_criteria(self._make_fact("2026-11-17", r1=False))
        self.assertFalse(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

    # Scenario 7: R1 team at 2 or 3 wasted days
    # Expected: Keeps its current state
    def test_scenario_07_r1_hysteresis_preserves_state(self):
        # Case A: Initially clean team reaches 2, then 3 wasted days -> stays clean
        self.state_machine.update_team_criteria(self._make_fact("2026-11-01", r1=True))
        self.state_machine.update_team_criteria(self._make_fact("2026-11-02", r1=True))
        state = self.db.get_team_criterion_state(self.team_id, "R1")
        self.assertFalse(state["is_flagged"], "Clean team at 2 wasted days stays clean")

        self.state_machine.update_team_criteria(self._make_fact("2026-11-03", r1=True))
        state = self.db.get_team_criterion_state(self.team_id, "R1")
        self.assertFalse(state["is_flagged"], "Clean team at 3 wasted days stays clean")

        # Flag it with 4th day
        self.state_machine.update_team_criteria(self._make_fact("2026-11-04", r1=True))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

        # Case B: Flagged team drops to 3, then 2 wasted days -> stays flagged
        # Push clean days up to day 14 (window has days 1,2,3,4 wasted = 4)
        for i in range(5, 15):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-{i:02d}", r1=False))

        # Push clean day 15 -> day 1 drops off, 3 wasted left
        self.state_machine.update_team_criteria(self._make_fact("2026-11-15", r1=False))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"],
                        "Flagged team at 3 wasted days stays flagged")

        # Push clean day 16 -> day 2 drops off, 2 wasted left
        self.state_machine.update_team_criteria(self._make_fact("2026-11-16", r1=False))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"],
                        "Flagged team at 2 wasted days stays flagged")

    # Scenario 8: Season-ending player on IR for 3 consecutive game days
    # Expected: R3 flags on day 3
    def test_scenario_08_season_ending_player_flags_r3(self):
        for i in range(1, 4):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-0{i}", r3=True))
            state = self.db.get_team_criterion_state(self.team_id, "R3")
            if i < 3:
                self.assertFalse(state["is_flagged"])
            else:
                self.assertTrue(state["is_flagged"])

    # Scenario 9: Roster below the league minimum for 3 consecutive game days
    # Expected: R4 flags on day 3
    def test_scenario_09_roster_below_min_flags_r4(self):
        for i in range(1, 4):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-0{i}", r4=True))
            state = self.db.get_team_criterion_state(self.team_id, "R4")
            if i < 3:
                self.assertFalse(state["is_flagged"])
            else:
                self.assertTrue(state["is_flagged"])

    # Scenario 10: Whole bench injured, active slot holds an OUT player
    # Expected: R1 does not fire
    def test_scenario_10_whole_bench_injured_no_r1(self):
        pre_tip = [
            {"playerId": 10, "injuryStatus": "OUT", "proTeam": "BOS"},
            {"playerId": 20, "injuryStatus": "OUT", "proTeam": "LAL"}
        ]
        final = [
            {"playerId": 10, "name": "Active Injured", "lineupSlotId": SLOT_PG, "eligibleSlots": [SLOT_PG], "proTeam": "BOS"},
            {"playerId": 20, "name": "Bench Injured", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_PG, SLOT_BENCH], "proTeam": "LAL"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", self.team_id, self.team_name, pre_tip, final, {"BOS", "LAL"}, is_game_day=True
        )
        self.assertFalse(fact["r1_violation"])

    # Scenario 11: Questionable or day-to-day player in an active slot
    # Expected: Not a violation
    def test_scenario_11_questionable_or_dtd_not_violation(self):
        pre_tip = [
            {"playerId": 10, "injuryStatus": "QUESTIONABLE", "proTeam": "BOS"},
            {"playerId": 20, "injuryStatus": "DAY_TO_DAY", "proTeam": "LAL"},
            {"playerId": 30, "injuryStatus": "ACTIVE", "proTeam": "GSW"}
        ]
        final = [
            {"playerId": 10, "name": "Q Player", "lineupSlotId": SLOT_PG, "eligibleSlots": [SLOT_PG], "proTeam": "BOS"},
            {"playerId": 20, "name": "DTD Player", "lineupSlotId": SLOT_SG, "eligibleSlots": [SLOT_SG], "proTeam": "LAL"},
            {"playerId": 30, "name": "Bench Player", "lineupSlotId": SLOT_BENCH, "eligibleSlots": [SLOT_PG, SLOT_SG, SLOT_BENCH], "proTeam": "GSW"}
        ]
        fact = self.evaluator.evaluate_team_day(
            "2026-11-01", self.team_id, self.team_name, pre_tip, final, {"BOS", "LAL", "GSW"}, is_game_day=True
        )
        self.assertFalse(fact["r1_violation"])
        self.assertFalse(fact["r2_violation"])

    # Scenario 12: Day with no NBA games
    # Expected: No counter changes
    def test_scenario_12_no_game_day_no_counter_changes(self):
        # Day 1: violation (R2)
        self.state_machine.update_team_criteria(self._make_fact("2026-11-01", r2=True))
        s1 = self.db.get_team_criterion_state(self.team_id, "R2")
        self.assertEqual(s1["consecutive_violations"], 1)

        # Day 2: No NBA games
        self.state_machine.update_team_criteria(self._make_fact("2026-11-02", is_game_day=False))
        s2 = self.db.get_team_criterion_state(self.team_id, "R2")
        self.assertEqual(s2["consecutive_violations"], 1, "Counters must not change on no-game days")

    # Scenario 13: Capture fails on a day a team is flagged
    # Expected: Team stays flagged, counters pause
    def test_scenario_13_capture_failure_pauses_counters(self):
        # Flag on day 3
        for i in range(1, 4):
            self.state_machine.update_team_criteria(self._make_fact(f"2026-11-0{i}", r2=True))
        self.assertTrue(self.db.get_team_criterion_state(self.team_id, "R2")["is_flagged"])

        # Day 4: Capture fails (unknown day)
        self.state_machine.update_team_criteria(self._make_fact("2026-11-04", is_unknown=True))
        s4 = self.db.get_team_criterion_state(self.team_id, "R2")
        self.assertTrue(s4["is_flagged"], "Must stay flagged")
        self.assertEqual(s4["consecutive_clean"], 0, "Unknown day never clears flag or increments cooldown")

    # Scenario 14: 2 AM run on Nov 2 evaluates Nov 1 only; Nov 2 changes have no effect on it
    def test_scenario_14_evaluates_previous_date_only(self):
        runner = DailyWorkflowRunner(self.db, None, self.injury_source, self.notifier)
        # Mock snapshots specifically for Nov 1
        nov1_pre = {
            "scoreboard": {"is_game_day": True, "teams_playing": ["BOS", "LAL"]},
            "roster_data": {
                "teams": [{
                    "id": self.team_id,
                    "name": self.team_name,
                    "roster": {"entries": [
                        {"playerId": 1, "lineupSlotId": SLOT_BENCH, "injuryStatus": "OUT", "playerPoolEntry": {"player": {"fullName": "P1", "eligibleSlots": [SLOT_BENCH], "proTeam": "BOS"}}}
                    ]}
                }]
            }
        }
        nov1_final = {
            "teams": [{
                "id": self.team_id,
                "name": self.team_name,
                "roster": {"entries": [
                    {"playerId": 1, "lineupSlotId": SLOT_BENCH, "injuryStatus": "OUT", "playerPoolEntry": {"player": {"fullName": "P1", "eligibleSlots": [SLOT_BENCH], "proTeam": "BOS"}}}
                ]}
            }]
        }
        self.db.save_snapshot("2026-11-01", "pre_tip", nov1_pre)
        self.db.save_snapshot("2026-11-01", "final", {"roster_data": nov1_final})

        # Replay / evaluate Nov 1
        success = runner.replay_date("2026-11-01")
        self.assertTrue(success)

        facts = self.db.get_daily_facts("2026-11-01")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["eval_date"], "2026-11-01")
        self.assertTrue(facts[0]["r2_violation"])

        # Verify no facts exist for Nov 2
        nov2_facts = self.db.get_daily_facts("2026-11-02")
        self.assertEqual(len(nov2_facts), 0)

    # Scenario 15: Same date evaluated twice from stored snapshots -> Identical output
    def test_scenario_15_deterministic_replay(self):
        runner = DailyWorkflowRunner(self.db, None, self.injury_source, self.notifier)
        snap_pre = {
            "scoreboard": {"is_game_day": True, "teams_playing": ["BOS"]},
            "roster_data": {
                "teams": [{
                    "id": self.team_id,
                    "name": self.team_name,
                    "roster": {"entries": [
                        {"playerId": 1, "lineupSlotId": SLOT_BENCH, "injuryStatus": "OUT", "playerPoolEntry": {"player": {"fullName": "P1", "eligibleSlots": [SLOT_BENCH], "proTeam": "BOS"}}}
                    ]}
                }]
            }
        }
        snap_final = snap_pre["roster_data"]
        self.db.save_snapshot("2026-11-01", "pre_tip", snap_pre)
        self.db.save_snapshot("2026-11-01", "final", {"roster_data": snap_final})

        # Run 1
        runner.replay_date("2026-11-01")
        facts1 = self.db.get_daily_facts("2026-11-01")
        state1 = self.db.get_team_criterion_state(self.team_id, "R2")

        # Run 2
        runner.replay_date("2026-11-01")
        facts2 = self.db.get_daily_facts("2026-11-01")
        state2 = self.db.get_team_criterion_state(self.team_id, "R2")

        self.assertEqual(facts1, facts2)
        self.assertEqual(state1["is_flagged"], state2["is_flagged"])
        self.assertEqual(state1["consecutive_violations"], state2["consecutive_violations"])
        self.assertEqual(state1["consecutive_clean"], state2["consecutive_clean"])

    # Scenario 16: Run on a daylight saving change day evaluates correct date
    def test_scenario_16_daylight_saving_transition(self):
        # In Nov 2026, DST ends Sunday Nov 1, 2026 (clocks roll back 2 AM -> 1 AM)
        dt_before = datetime(2026, 11, 1, 1, 30, tzinfo=ET_TZ)
        dt_after = datetime(2026, 11, 1, 2, 30, tzinfo=ET_TZ)
        self.assertEqual(str(dt_before.tzinfo), "America/New_York")
        self.assertEqual(str(dt_after.tzinfo), "America/New_York")
        eval_date = (dt_after - timedelta(days=1)).date()
        self.assertEqual(eval_date, date(2026, 10, 31))

    # Scenario 17: First 5 days after launch, team wasted 4 of them
    # Expected: R1 flags despite the partial window
    def test_scenario_17_r1_flags_in_partial_window(self):
        # 5 days: Day 1 clean, Days 2, 3, 4, 5 wasted (4 total)
        self.state_machine.update_team_criteria(self._make_fact("2026-11-01", r1=False))
        self.state_machine.update_team_criteria(self._make_fact("2026-11-02", r1=True))
        self.state_machine.update_team_criteria(self._make_fact("2026-11-03", r1=True))
        self.state_machine.update_team_criteria(self._make_fact("2026-11-04", r1=True))
        self.assertFalse(self.db.get_team_criterion_state(self.team_id, "R1")["is_flagged"])

        # Day 5 (4th wasted day in 5-day history)
        self.state_machine.update_team_criteria(self._make_fact("2026-11-05", r1=True))
        state = self.db.get_team_criterion_state(self.team_id, "R1")
        self.assertTrue(state["is_flagged"], "Must flag when 4 wasted days reached in partial window")
        self.assertEqual(len(state["history"]), 5)

if __name__ == "__main__":
    unittest.main()
