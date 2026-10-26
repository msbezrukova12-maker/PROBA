"""Offline analyzer for the proposed PROBA career-interest experiment.

Zero network/database calls. Source CSV is either a clearly labeled synthetic
fixture or an approved export of real events. Data are session-level, NOT users.
No personal identifiers, emails, IP addresses, or answers are processed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROLES = (
    "project_manager", "system_analyst", "financial_analyst",
    "internet_marketer", "python_developer", "frontend_developer",
    "data_scientist",
)
EVENTS = {"card_impression", "card_open", "waitlist_intent"}
FIELDS = (
    "event_id", "experiment_id", "session_id", "profession_id",
    "placement_variant", "position", "event_time_utc", "event_name",
    "data_origin",
)
WINDOW = timedelta(hours=24)


def time_utc(s: str) -> datetime:
    value = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("All event times must be explicitly UTC")
    return value.astimezone(timezone.utc)


def wilson(success: int, trials: int, z: float = 1.959963984540054):
    """Descriptive Wilson 95% interval; NOT a multiple-testing adjustment."""
    if trials == 0:
        return None, None
    p = success / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    radius = (z / denominator) * math.sqrt(
        p * (1 - p) / trials + z * z / (4 * trials * trials)
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def read_events(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or set(reader.fieldnames) != set(FIELDS):
            raise ValueError("Wrong CSV columns; see documentation")
        seen = {}
        entries = []
        for row in reader:
            if any(row.get(k, "") == "" for k in FIELDS):
                raise ValueError("Every field is mandatory")
            if row["profession_id"] not in ROLES:
                raise ValueError("Unregistered profession_id")
            if row["event_name"] not in EVENTS:
                raise ValueError("Unregistered event_name")
            if row["data_origin"] not in {"SYNTHETIC", "OBSERVED"}:
                raise ValueError("Explicit data origin must be SYNTHETIC or OBSERVED")
            if not 1 <= int(row["position"]) <= 7:
                raise ValueError("Position out of 1–7 range")
            row["timestamp"] = time_utc(row["event_time_utc"])
            event_id = row["event_id"]
            # Duplicate delivery of an identical event is harmless; conflicting
            # payloads for the same id should never silently be accepted.
            comparable = tuple(row[k] for k in FIELDS)
            if event_id in seen:
                if seen[event_id] != comparable:
                    raise ValueError("Conflicting duplicate event_id")
                continue
            seen[event_id] = comparable
            entries.append(row)
    origins = {e["data_origin"] for e in entries}
    if len(origins) != 1:
        raise ValueError("Synthetic and observed data cannot be combined")
    return entries, (next(iter(origins)) if origins else "EMPTY")


def analyze(entries, experiment: str, start: datetime, end: datetime,
            min_exposures: int = 100):
    if not start < end:
        raise ValueError("End must be after start")
    if min_exposures < 1:
        raise ValueError("min_exposures must be >= 1")
    selected = [e for e in entries if e["experiment_id"] == experiment]
    variants_by_session = defaultdict(set)
    for e in selected:
        variants_by_session[e["session_id"]].add(e["placement_variant"])
    if any(len(v) > 1 for v in variants_by_session.values()):
        raise ValueError("One session assigned to multiple layout variants")

    # Cohort is *first actually visible impression*, within the analysis window.
    cohorts = {}
    for e in selected:
        if e["event_name"] != "card_impression" or not start <= e["timestamp"] < end:
            continue
        key = (e["session_id"], e["profession_id"])
        if key not in cohorts or e["timestamp"] < cohorts[key]["timestamp"]:
            cohorts[key] = e

    events_by_key = defaultdict(list)
    for e in selected:
        events_by_key[e["session_id"], e["profession_id"]].append(e)
    counts = defaultdict(lambda: {"impressions": 0, "opens": 0, "intents": 0,
                                  "positions": Counter()})
    for key, impression in cohorts.items():
        c = counts[(impression["profession_id"], impression["placement_variant"])]
        c["impressions"] += 1
        c["positions"][int(impression["position"])] += 1
        subsequent = {
            e["event_name"] for e in events_by_key[key]
            if impression["timestamp"] <= e["timestamp"] <=
               impression["timestamp"] + WINDOW
        }
        c["opens"] += int("card_open" in subsequent)
        c["intents"] += int("waitlist_intent" in subsequent)
    variants = sorted(set(e["placement_variant"] for e in selected))
    rows = []
    for variant in variants:
        for role in ROLES:
            values = counts[(role, variant)]
            n = values["impressions"]
            x = values["intents"]
            lo, hi = wilson(x, n)
            rows.append({
                "profession_id": role, "placement_variant": variant,
                "sessions_exposed": n, "sessions_opened": values["opens"],
                "sessions_intent": x,
                "intent_rate": round(x / n, 5) if n else None,
                "intent_ci95_lower": round(lo, 5) if lo is not None else None,
                "intent_ci95_upper": round(hi, 5) if hi is not None else None,
                "open_rate": round(values["opens"] / n, 5) if n else None,
                "min_position_exposures": min(
                    values["positions"].get(pos, 0) for pos in range(1, 8)
                ) if n else 0,
                "max_position_exposures": max(
                    values["positions"].get(pos, 0) for pos in range(1, 8)
                ) if n else 0,
                "interpretation": "exploratory_only" if n >= min_exposures
                                  else "insufficient_exposures",
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD in UTC, inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD in UTC, exclusive")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-exposures", type=int, default=100,
                        help="Descriptive QC threshold, NOT statistical power")
    args = parser.parse_args()
    start = datetime.combine(date.fromisoformat(args.start),
                             datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(date.fromisoformat(args.end),
                           datetime.min.time(), tzinfo=timezone.utc)
    events, origin = read_events(args.input)
    result = analyze(events, args.experiment_id, start, end,
                     args.min_exposures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "status": "DEMONSTRATION_ONLY" if origin == "SYNTHETIC" else "OBSERVED_UNAUDITED",
        "data_origin": origin, "experiment_id": args.experiment_id,
        "start_utc": args.start, "end_utc_exclusive": args.end,
        "min_exposures": args.min_exposures,
        "unit": "anonymous_sessions_not_unique_people",
        "outcome_window_hours": 24, "multiple_comparison_adjustment": "none",
        "caution": "No causal claims, no purchases inferred, no winner selection",
        "results": result,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(result)} rows; data_origin={origin}; "
          "never interpret synthetic data as observed demand.")


if __name__ == "__main__":
    main()
