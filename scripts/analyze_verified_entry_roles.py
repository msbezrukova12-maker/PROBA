"""Reproducible qualitative audit of *selected* entry-level postings (2026-10-23).

Not a probability sample, API export, or estimate of the number of vacancies.
Uses Python standard library and in-memory SQLite; only source-linked rows from
data/verified_entry_roles_2026-10-23.csv. No network calls.
"""
from __future__ import annotations
import csv
import html
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VIS = ROOT / "visualizations"
VIS.mkdir(exist_ok=True)

with (DATA / "verified_entry_roles_2026-10-23.csv").open(encoding="utf-8", newline="") as f:
    records = list(csv.DictReader(f))
assert len(records) == 16, "Expected manually verified sample of 16 distinct postings"
assert len({r["source_id"] for r in records}) == 16
assert len({r["url"] for r in records}) == 16
assert {r["relevance"] for r in records} == {"exact", "adjacent"}
assert {r["entry_type"] for r in records} == {"internship", "junior"}
assert all(r["url"].startswith("https://") for r in records)

db = sqlite3.connect(":memory:")
db.executescript("""
CREATE TABLE posting(
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  employer TEXT NOT NULL,
  relevance TEXT NOT NULL CHECK(relevance IN ('exact','adjacent')),
  entry_type TEXT NOT NULL,
  source_class TEXT NOT NULL,
  source_url TEXT UNIQUE NOT NULL
);
CREATE TABLE posting_skill(
  posting_id TEXT NOT NULL,
  skill TEXT NOT NULL,
  PRIMARY KEY(posting_id,skill)
);
""")
for r in records:
    db.execute("INSERT INTO posting VALUES(?,?,?,?,?,?,?)",
        (r["source_id"],r["target_role"],r["employer"],r["relevance"],
         r["entry_type"],r["source_class"],r["url"]))
    for tag in set(r["skills_observed_normalized"].split(";")):
        if tag:
            db.execute("INSERT INTO posting_skill VALUES(?,?)", (r["source_id"], tag))
db.commit()
role_rows = db.execute("""
SELECT role,
  COUNT(*) AS curated_n,
  SUM(CASE WHEN relevance='exact' THEN 1 ELSE 0 END) AS exact_n,
  SUM(CASE WHEN relevance='adjacent' THEN 1 ELSE 0 END) AS adjacent_n,
  COUNT(DISTINCT employer) AS unique_employers,
  SUM(CASE WHEN source_class='official_employer' THEN 1 ELSE 0 END) AS official_n
FROM posting GROUP BY role ORDER BY curated_n DESC, role
""").fetchall()
assert sum(row[1] for row in role_rows) == 16
assert sum(row[2] for row in role_rows) == 14

skill_rows = db.execute("""
SELECT p.role, s.skill, COUNT(DISTINCT p.id) AS postings_with_skill,
       (SELECT COUNT(*) FROM posting d
        WHERE d.role=p.role AND d.relevance='exact') AS exact_role_n
FROM posting p JOIN posting_skill s ON s.posting_id=p.id
WHERE p.relevance='exact'
GROUP BY p.role,s.skill
ORDER BY p.role,postings_with_skill DESC,s.skill
""").fetchall()
# Each numerator counts unique postings, never keyword occurrences.
assert all(0 < n <= den for _,_,n,den in skill_rows)

def write_csv(filename, columns, rows):
    with (DATA / filename).open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(columns)
        wr.writerows(rows)
write_csv("verified_role_coverage_2026-10-23.csv",
    ["role","curated_postings","exact_role","adjacent_role","distinct_employers","official_employer_pages"],
    role_rows)
write_csv("verified_skill_frequency_2026-10-23.csv",
    ["role","skill","postings_with_skill","exact_role_sample_size"], skill_rows)

def bar_svg(rows, title, subtitle):
    w, bw, rh, x0 = 1050, 580, 44, 330
    h = 140 + len(rows)*rh
    top = max(v for _,v in rows)
    esc = html.escape
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         f'<text x="24" y="36" font-family="Arial" font-size="23" font-weight="bold" fill="#172943">{esc(title)}</text>',
         f'<text x="24" y="63" font-family="Arial" font-size="14" fill="#64748b">{esc(subtitle)}</text>']
    for i,(role,n) in enumerate(rows):
        y = 90 + rh*i
        length = n/top * bw
        p.extend([f'<text x="24" y="{y+20}" font-family="Arial" font-size="15" fill="#24364c">{esc(role)}</text>',
                  f'<rect x="{x0}" y="{y+3}" width="{length:.1f}" height="27" rx="4" fill="#4267a8"/>',
                  f'<text x="{x0+length+10:.1f}" y="{y+23}" font-family="Arial" font-size="15" fill="#24364c">{n}</text>'])
    p.extend([f'<text x="24" y="{h-13}" font-family="Arial" font-size="12" fill="#64748b">Отобранные ссылки, 23.10.2026. Это НЕ объём рынка и НЕ случайная выборка.</text>','</svg>'])
    return "\n".join(p) + "\n"
(VIS / "verified_entry_roles_sample_2026-10-23.svg").write_text(
    bar_svg([(r[0],r[2]) for r in sorted(role_rows,key=lambda r:-r[2])],
            "Прямые стажировки по профессиям в выборке",
            "Только проверенные URL, не сравнение абсолютного спроса"),
    encoding="utf-8")

employers = Counter(r["employer"] for r in records)
print("Curated:", len(records), "Exact:", sum(r[2] for r in role_rows),
      "Adjacent:", sum(r[3] for r in role_rows))
print("Distinct employers:", len(employers), "Ozon group share:",
      sum(1 for r in records if r["employer"].startswith("Ozon")), "/", len(records))
print("Role coverage:", role_rows)
print("Skill rows:", len(skill_rows))
print("CAUTION: skill frequencies are within selected postings only.")
