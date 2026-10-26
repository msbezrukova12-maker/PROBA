"""Tests for the *offline* synthetic/approved-export interest-pilot analyzer."""
from __future__ import annotations
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_interest_pilot import analyze, read_events, wilson, ROLES  # noqa: E402

START = datetime(2026, 10, 20, tzinfo=timezone.utc)
END = datetime(2026, 10, 21, tzinfo=timezone.utc)
FIXTURE = ROOT / "tests" / "fixtures" / "SYNTHETIC_interest_events.csv"


class InterestPilotTests(unittest.TestCase):
    def setUp(self):
        self.events, self.origin = read_events(FIXTURE)
        self.experiment = "proba_career_interest_v1"

    def one_role(self, events=None, role="system_analyst", min_exposures=100):
        rows = analyze(
            events if events is not None else self.events,
            self.experiment, START, END, min_exposures,
        )
        self.assertEqual(len(rows), 7)
        return next(r for r in rows if r["profession_id"] == role)

    def test_fixture_is_explicitly_synthetic(self):
        self.assertEqual(self.origin, "SYNTHETIC")
        self.assertEqual(len(self.events), 91)
        self.assertEqual({x["data_origin"] for x in self.events}, {"SYNTHETIC"})
        out = self.one_role()
        self.assertEqual(out["sessions_exposed"], 7)
        self.assertEqual(out["interpretation"], "insufficient_exposures")
        self.assertLessEqual(out["sessions_intent"], out["sessions_exposed"])
        self.assertEqual(out["min_position_exposures"], 1)
        self.assertEqual(out["max_position_exposures"], 1)

    def test_missing_card_positions_are_counted_as_zero(self):
        one_session = [
            e for e in self.events if e["session_id"] == "demo_s_01"
        ]
        row = self.one_role(one_session, role="system_analyst")
        self.assertEqual(row["sessions_exposed"], 1)
        self.assertEqual(row["min_position_exposures"], 0)
        self.assertEqual(row["max_position_exposures"], 1)

    def test_duplicate_delivery_is_deduplicated(self):
        rows, _ = read_events(FIXTURE)
        duplicate = copy.deepcopy(rows[0])
        rows.append(duplicate)
        self.assertEqual(self.one_role(rows), self.one_role(self.events))

    def test_events_before_first_exposure_do_not_count(self):
        old = self.one_role()["sessions_intent"]
        wrong = copy.deepcopy(self.events[0])
        wrong.update(
            event_id="wrong_time_event",
            profession_id="system_analyst",
            event_name="waitlist_intent",
            event_time_utc="2026-10-20T09:00:00Z",
            timestamp=datetime(2026, 10, 20, 9, tzinfo=timezone.utc),
        )
        self.assertEqual(self.one_role(self.events + [wrong])["sessions_intent"], old)

    def test_unexposed_role_intent_is_not_counted(self):
        wrong = copy.deepcopy(self.events[0])
        wrong.update(
            event_id="unexposed_intent",
            session_id="another_session",
            profession_id="system_analyst",
            event_name="waitlist_intent",
        )
        self.assertEqual(
            self.one_role(self.events + [wrong])["sessions_intent"],
            self.one_role()["sessions_intent"],
        )

    def test_bad_assignment_rejected(self):
        wrong = copy.deepcopy(self.events[0])
        wrong["event_id"] = "new_bad_variant"
        wrong["placement_variant"] = "alternative"
        with self.assertRaisesRegex(ValueError, "multiple"):
            self.one_role(self.events + [wrong])

    def test_zero_events_are_not_zero_conversion(self):
        outcome = analyze([], self.experiment, START, END)
        self.assertEqual(outcome, [])
        other_experiment = analyze(
            self.events, "does_not_exist", START, END
        )
        self.assertEqual(other_experiment, [])

    def test_wilson_interval_and_invalid_inputs(self):
        lo, hi = wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertGreater(hi, 0)
        self.assertEqual(wilson(0, 0), (None, None))
        with self.assertRaises(ValueError):
            analyze(self.events, self.experiment, END, START)
        with self.assertRaises(ValueError):
            analyze(self.events, self.experiment, START, END, 0)

    def test_exploratory_threshold_does_not_choose_winner(self):
        a = self.one_role(min_exposures=7)
        self.assertEqual(a["interpretation"], "exploratory_only")
        self.assertNotIn("winner", a)
        self.assertEqual({e["profession_id"] for e in self.events}, set(ROLES))


if __name__ == "__main__":
    unittest.main()
