"""Analyse Wordstat top-20 phrase samples with SQLite, without double counting.

Time window 2026-09-08..2026-10-07; 'Все регионы' and all devices.
Do NOT sum phrase volumes: lists contain permutations and overlapping queries.
A ratio of ONE representative phrase to its broad seed is NOT a user share.
"""
from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VIS = ROOT / "visualizations"
VIS.mkdir(exist_ok=True)

with (DATA / "wordstat_top_queries_2026-10-26.csv").open(encoding="utf-8", newline="") as f:
    source = list(csv.DictReader(f))
assert len(source) == 180
assert len({r["seed_query"] for r in source}) == 9
assert len({r["role"] for r in source}) == 7
assert {r["region_label"] for r in source} == {"Все регионы"}
assert {(r["range_start"], r["range_end"]) for r in source} == {("2026-09-08","2026-10-07")}
assert {r["device_filter"] for r in source} == {"all three device types"}
groups = defaultdict(list)
for row in source:
    groups[row["seed_query"]].append(row)
for seed, entries in groups.items():
    assert len(entries) == 20, seed
    assert sorted(int(r["phrase_rank"]) for r in entries) == list(range(1,21)), seed
    assert len({r["seed_total_requests"] for r in entries}) == 1
    assert all(int(r["queries"]) >= 0 for r in entries)
    assert all(int(r["queries"]) <= int(r["seed_total_requests"]) for r in entries)

db = sqlite3.connect(":memory:")
db.executescript("""
CREATE TABLE phrase(
  role TEXT, seed TEXT, seed_total INTEGER,
  rank INTEGER, phrase TEXT, query_count INTEGER, intent TEXT,
  PRIMARY KEY(seed,rank)
);
""")
db.executemany("INSERT INTO phrase VALUES(?,?,?,?,?,?,?)",
  [(r["role"],r["seed_query"],int(r["seed_total_requests"]),
    int(r["phrase_rank"]),r["phrase"],int(r["queries"]),r["intent_class"])
   for r in source])

# Select ONE highest-volume example per intent within each seed.
# Summing different rows from the top-20 is invalid because queries overlap.
sql = """
WITH ranked AS (
  SELECT role, seed, seed_total, intent, phrase, query_count,
         ROW_NUMBER() OVER (
           PARTITION BY seed,intent ORDER BY query_count DESC,rank ASC
         ) AS rn
  FROM phrase
  WHERE intent NOT IN ('base','other','brand')
)
SELECT role,seed,seed_total,intent,phrase,query_count
FROM ranked WHERE rn=1 ORDER BY seed,intent
"""
items = db.execute(sql).fetchall()
by_seed = defaultdict(dict)
for role,seed,seed_total,intent,phrase,n in items:
    by_seed[seed][intent] = (phrase,n)
intent_types = ["learning","employment","internship","orientation","compensation"]
rows = []
for seed,src in groups.items():
    role=src[0]["role"]
    total=int(src[0]["seed_total_requests"])
    out={"role":role,"seed":seed,"seed_total":total}
    for typ in intent_types:
        best = by_seed[seed].get(typ)
        out[typ+"_phrase"] = best[0] if best else ""
        out[typ+"_count"] = best[1] if best else ""
        out[typ+"_pct"] = round(100*best[1]/total,2) if best else ""
    rows.append(out)
assert len(rows) == 9
assert next(r for r in rows if r["seed"]=="python разработчик")["learning_count"] == 864
assert next(r for r in rows if r["seed"]=="менеджер проектов")["learning_count"] == 831
assert next(r for r in rows if r["seed"]=="системный аналитик")["internship_count"] == 1028

header=["role","seed_query","total_requests"]
for typ in intent_types:
    header += [typ+"_phrase",typ+"_max_single_phrase_count",typ+"_pct_of_seed"]
path=DATA/"wordstat_intent_signals_2026-10-26.csv"
with path.open("w",encoding="utf-8",newline="") as f:
    w=csv.writer(f)
    w.writerow(header)
    for r in rows:
        values=[r["role"],r["seed"],r["seed_total"]]
        for typ in intent_types:
            values += [r[typ+"_phrase"],r[typ+"_count"],r[typ+"_pct"]]
        w.writerow(values)

# Show a single phrase's frequency relative to its broad query volume.
# Do not label these ratios as the fraction of students or users.
ordered=sorted(rows,key=lambda r:-r["learning_pct"])
W,H=1080,600
p=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
  '<rect width="100%" height="100%" fill="#fff"/>',
  '<text x="24" y="35" font-family="Arial" font-weight="bold" font-size="23" fill="#20304a">Сигнал интереса к обучению: выбранная фраза / общий запрос</text>',
  '<text x="24" y="61" font-family="Arial" font-size="14" fill="#526078">Один самый частотный запрос об обучении из топ-20; 08.09–07.10.2026, «Все регионы»</text>']
for i,r in enumerate(ordered):
    y=87+i*48
    n=r["learning_pct"]
    bw=610*n/15
    p.extend([
      f'<text x="24" y="{y+22}" font-family="Arial" font-size="15" fill="#283a51">{escape(r["seed"])}</text>',
      f'<rect x="275" y="{y+3}" width="{bw:.1f}" height="27" rx="5" fill="#41659a"/>',
      f'<text x="{275+bw+10:.1f}" y="{y+22}" font-family="Arial" font-size="15" fill="#273b55">{n:.2f}%</text>'
    ])
p += [
  '<text x="24" y="552" font-family="Arial" font-size="13" fill="#64748b">НЕ доля обучающихся; НЕ доля студентов; строки запросов могут перекрываться.</text>',
  '<text x="24" y="575" font-family="Arial" font-size="13" fill="#64748b">Синонимы Python/пайтон и frontend/фронтенд показаны раздельно, не суммируются.</text>',
  '</svg>'
]
(VIS/"wordstat_learning_signal_2026-10-26.svg").write_text("\n".join(p)+"\n",encoding="utf-8")
print("Validated",len(source),"visible rows across",len(groups),"searches;",len({r["role"] for r in source}),"roles")
print("Generated",len(rows),"non-additive intent summaries")
print("Learning ratios:",[(r["seed"],r["learning_pct"]) for r in ordered])
print("DO NOT interpret as the fraction of students or add nested search phrases.")
