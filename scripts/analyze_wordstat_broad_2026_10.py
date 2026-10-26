"""Recalculate comparable 11-month Wordstat interest proxy from image-transcribed CSV.

Inputs are screenshot transcriptions, NOT an authenticated API export.
Never impute missing September 2026 or merge overlapping synonyms.
Uses only Python standard library (works in GitHub Actions).
"""
from __future__ import annotations
import csv
from collections import defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHARTS = ROOT / "visualizations"
CHARTS.mkdir(exist_ok=True)
SOURCE = DATA / "wordstat_broad_monthly_2026-10-26.csv"

with SOURCE.open(encoding="utf-8", newline="") as f:
    records = list(csv.DictReader(f))

assert len(records) == 96
assert len({r["phrase_as_shown"] for r in records}) == 8
assert {r["region_as_shown"] for r in records} == {"Все регионы"}
assert {r["devices"] for r in records} == {"desktop+smartphones+tablets"}
expected_months = [
    "2025-10","2025-11","2025-12","2026-01","2026-02","2026-03",
    "2026-04","2026-05","2026-06","2026-07","2026-08","2026-09",
]
series = defaultdict(list)
for row in records:
    series[row["phrase_as_shown"]].append(row)
assert all(len(entries) == 12 for entries in series.values())
for phrase, entries in series.items():
    ordered = sorted(entries, key=lambda x:x["month"])
    assert [x["month"] for x in ordered] == expected_months
    assert sum(x["value_status"] == "read_from_visible_table" for x in entries) == 11
    assert sum(x["value_status"] == "missing_row_cropped" for x in entries) == 1
    assert all(x["search_count"] and int(x["search_count"]) >= 0 for x in entries if x["month"] != "2026-09")
    sep = next(x for x in entries if x["month"] == "2026-09")
    assert sep["search_count"] == "" and sep["value_status"] == "missing_row_cropped"

assert sum(r["primary_comparison_phrase"] == "yes" for r in records) == 84
assert sum(bool(r["search_count"]) for r in records) == 88

summary = []
for phrase, entries in series.items():
    sample = sorted((r for r in entries if r["search_count"]), key=lambda r:r["month"])
    role = sample[0]["role"]
    is_primary = sample[0]["primary_comparison_phrase"] == "yes"
    counts = [int(r["search_count"]) for r in sample]
    total = sum(counts)
    summary.append({
        "role": role, "phrase": phrase, "primary": is_primary,
        "total": total, "avg": total / 11,
        "oct": counts[0], "aug": counts[-1],
        "delta_pct": 100 * (counts[-1] / counts[0] - 1),
        "n_months": 11
    })

main = sorted((s for s in summary if s["primary"]), key=lambda x:-x["total"])
assert len(main) == 7
assert [x["total"] for x in main] == [340806,339946,301612,88064,86708,84401,81309]
assert next(x for x in summary if not x["primary"])["total"] == 28477

path = DATA / "wordstat_broad_11m_summary_2026-10-26.csv"
with path.open("w", encoding="utf-8", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["role","phrase","region","months","total_search_requests","monthly_mean",
                 "oct_2025","aug_2026","oct_to_aug_pct","measurement_type"])
    for row in main:
        wr.writerow([
            row["role"],row["phrase"],"Все регионы",11,row["total"],f'{row["avg"]:.2f}',
            row["oct"],row["aug"],f'{row["delta_pct"]:.2f}',"broad_phrase_interest_proxy"
        ])

W,H=1100,520
x0=330
max_value=max(x["avg"] for x in main)
colors={"main":"#385b98"}
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       '<rect width="100%" height="100%" fill="#fff"/>',
       '<text x="28" y="42" font-family="Arial" font-weight="bold" font-size="25" fill="#1e293b">Wordstat: среднемесячная частота названий профессий</text>',
       '<text x="28" y="69" font-family="Arial" font-size="15" fill="#475569">11 полных видимых месяцев, октябрь 2025 — август 2026 · «Все регионы»</text>']
for i,row in enumerate(main):
    y=101+52*i
    width=610*row["avg"]/max_value
    parts += [
      f'<text x="28" y="{y+22}" font-family="Arial" font-size="16" fill="#1e293b">{escape(row["role"])}</text>',
      f'<rect x="{x0}" y="{y+3}" width="{width:.2f}" height="30" rx="5" fill="{colors["main"]}"/>',
      f'<text x="{x0+width+12:.2f}" y="{y+26}" font-family="Arial" font-size="16" fill="#1e293b">{row["avg"]:,.0f}</text>',
    ]
parts += [
 '<text x="28" y="505" font-family="Arial" font-size="13" fill="#64748b">Число запросов, не уникальных пользователей; варианты написания нельзя просто суммировать.</text>',
 '</svg>',
]
(CHARTS / "wordstat_occupation_popularity_11m_2026-10-26.svg").write_text("\n".join(parts)+"\n",encoding="utf-8")
print("VALIDATED:",len(series),"phrases,",len(main),"primary occupational phrases, 88 visible observations")
for i,row in enumerate(main,1):
    print(f'{i}. {row["role"]}: {row["total"]:,} in 11m, mean={row["avg"]:.2f}')
print("Alias excluded: пайтон разработчик, 28,477; synonyms are overlapping.")
print("CAUTION: All regions, not Russia-only; September is unavailable; demand is not student interest.")
