"""Validate real interest measures without filling missing observations."""
import csv
from pathlib import Path
path = Path(__file__).resolve().parents[1] / "data" / "interest_wordstat_collection_template.csv"
with path.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 14
assert len({r["role"] for r in rows}) == 7
assert all(r["region"] == "Россия" for r in rows)
assert all((r["period_start"],r["period_end"]) == ("2025-10","2026-09") for r in rows)
assert all(r["metric_type"] == "monthly_searches_total" for r in rows)
for role in sorted({r["role"] for r in rows}):
    subset = [r for r in rows if r["role"] == role]
    assert len(subset) == 2
    assert {r["intent_type"] for r in subset} == {"career_learning","internship"}
    missing = [r["intent_type"] for r in subset if not r["observed_value"].strip()]
    if missing:
        print(f"{role}: missing {', '.join(missing)}")
    else:
        for r in subset:
            value = float(r["observed_value"])
            assert value >= 0, "Negative search frequency"
        print(f"{role}: both observations supplied")
print("Missing values remain missing. No unsupported ranking calculated.")
