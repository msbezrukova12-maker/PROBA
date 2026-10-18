"""Reproduce the BLS-based PROBA scenario and verify analytical SQL locally.

Only Python standard library required; source CSV is a transcription from BLS.
This is NOT a scraping tool and does NOT measure Russian internships or student demand.
"""
from __future__ import annotations

import csv
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def read_csv(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

roles = read_csv("bls_role_mapping_2025_35.csv")
skills = read_csv("junior_requirements_curated.csv")
assert len(roles) == 12 and len(skills) == 22
assert len({r["role"] for r in roles}) == 12
candidates = [r for r in roles if r["stage"] == "candidate"]
assert len(candidates) == 7

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE occupation(role TEXT PRIMARY KEY, stage TEXT, soc_code TEXT, openings_k REAL, growth_pct REAL, quality TEXT, feasibility REAL)")
db.execute("CREATE TABLE requirement(role TEXT, skill TEXT, category TEXT)")
db.executemany("INSERT INTO occupation VALUES (?,?,?,?,?,?,?)", [
    (r["role"], r["stage"], r["soc_code"], float(r["annual_openings_2025_35_thousands"]) if r["annual_openings_2025_35_thousands"] else None,
     float(r["growth_2025_35_pct"]) if r["growth_2025_35_pct"] else None,
     r["mapping_quality"], float(r["simulation_feasibility_assumption_0_to_1"]))
    for r in roles
])
db.executemany("INSERT INTO requirement VALUES (?,?,?)", [
    (r["role"], r["skill_or_task"], r["category"]) for r in skills
])
query = """
SELECT o.role, o.openings_k, o.growth_pct, o.quality, o.feasibility,
       COUNT(r.skill) AS curated_examples
FROM occupation AS o
LEFT JOIN requirement AS r ON o.role = r.role
WHERE o.stage = 'candidate'
GROUP BY o.role, o.openings_k, o.growth_pct, o.quality, o.feasibility
ORDER BY o.openings_k DESC
"""
query_results = db.execute(query).fetchall()
assert len(query_results) == 7

max_openings = max(row[1] for row in query_results)
max_growth = max(row[2] for row in query_results)
def rank_for(w_openings, w_growth):
    w_feasibility = 1 - w_openings - w_growth
    scored = []
    for role, openings, growth, quality, feasibility, _ in query_results:
        metric_openings = math.log1p(openings) / math.log1p(max_openings)
        metric_growth = growth / max_growth
        score = 100 * (w_openings * metric_openings + w_growth * metric_growth +
                       w_feasibility * feasibility)
        scored.append((role, round(score, 1), quality))
    return sorted(scored, key=lambda z: (-z[1], z[0]))

base = rank_for(.40, .15)
sensitivity = {r[0]: [] for r in base}
for w_openings in (.25, .40, .55):
    for w_growth in (.10, .15, .25):
        for position, (role, _, _) in enumerate(rank_for(w_openings, w_growth), start=1):
            sensitivity[role].append(position)

with (DATA / "candidate_sensitivity_recomputed.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["role", "index_score", "min_rank", "max_rank", "mapping_quality"])
    for role, score, quality in base:
        writer.writerow([role, score, min(sensitivity[role]), max(sensitivity[role]), quality])

print("Read", len(roles), "BLS role mappings and", len(skills), "junior skill examples")
print("Verified SQL JOIN and GROUP BY for", len(query_results), "candidate professions")
for role, score, quality in base:
    print(f"{role}: scenario={score:.1f}, rank={min(sensitivity[role])}-{max(sensitivity[role])}, mapping={quality}")
print("WARNING: unobserved RU internships and student interest; this is NOT the final product ranking")
