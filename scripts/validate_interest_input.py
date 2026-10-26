"""Check old and new Wordstat templates, and transcribed partial screenshot data.

The v2 template intentionally has no measured frequencies. Do not invent results.
"""
import csv
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "data"

def load(filename):
    with (root / filename).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

legacy = load("interest_wordstat_collection_template.csv")
assert len(legacy) == 14 and len({r["role"] for r in legacy}) == 7
assert all(not r["observed_value"] for r in legacy)

v2 = load("interest_wordstat_v2_template.csv")
assert len(v2) == 21 and len({r["role"] for r in v2}) == 7
assert all(r["region"] == "Россия" for r in v2)
assert all((r["period_start"], r["period_end"]) == ("2025-10","2026-09") for r in v2)
assert all(r["metric_type"] == "sum_of_12_monthly_dynamics_counts" for r in v2)
assert all(not r["observed_total"] for r in v2)
expected_intents = {"occupation_broad", "learning_intent", "internship_intent"}
for role in {r["role"] for r in v2}:
    subset = [r for r in v2 if r["role"] == role]
    assert len(subset) == 3 and {r["intent_type"] for r in subset} == expected_intents

observed = load("wordstat_how_to_partial_2026-10-26.csv")
assert len(observed) == 48 and len({r["phrase_as_shown"] for r in observed}) == 4
assert all(r["region_as_shown"] == "Все регионы" for r in observed)
assert all(r["devices"] == "все устройства" for r in observed)
by_phrase = {}
for row in observed:
    by_phrase.setdefault(row["phrase_as_shown"], []).append(row)
for phrase, rows in by_phrase.items():
    assert len(rows) == 12
    months = sorted(r["month"] for r in rows)
    assert months == [
        "2025-10","2025-11","2025-12","2026-01","2026-02","2026-03",
        "2026-04","2026-05","2026-06","2026-07","2026-08","2026-09",
    ]
    assert sum(bool(r["count_visible"]) for r in rows) == 11
    assert all(int(r["count_visible"]) >= 0 for r in rows if r["count_visible"])
    assert next(r for r in rows if r["month"] == "2026-09")["observation_status"] == "not_visible_on_screenshot"
    assert next(r for r in rows if r["month"] == "2026-09")["count_visible"] == ""

assert sum(bool(r["count_visible"]) for r in observed) == 44
assert sum(not r["count_visible"] for r in observed) == 4
print("PASS: legacy 14 blank observations; v2 21 blank observation rows")
print("PASS: screenshot 44 visible monthly counts, 4 missing September values")
print("MISSING: comparable Russia-only broad occupation names; no ranking calculated")
