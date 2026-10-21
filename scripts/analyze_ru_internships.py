"""Reproduce a small manually captured Moscow internship-search audit.

Inputs: user-provided hh.ru screenshots dated 2026-10-21, transcribed to CSV.
Does not scrape or fetch vacancies. Counts are search matches, not unique jobs.
"""
from __future__ import annotations

import csv
import html
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHARTS = ROOT / "visualizations"
CHARTS.mkdir(exist_ok=True)

def load(name):
    with (DATA / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

snapshot = load("hh_internships_moscow_2026-10-21.csv")
sample = load("hh_internship_first_two_audit_2026-10-21.csv")
observed = [row for row in snapshot if row["search_matches"]]
missing = [row for row in snapshot if not row["search_matches"]]
assert len(snapshot) == 7
assert len(observed) == 7 and not missing
assert all(row["location"] == "Москва" and row["experience_filter"] == "Нет опыта" and row["internship_filter"] == "Стажировка" for row in snapshot)
assert all(row["snapshot_date"] == "2026-10-21" for row in snapshot)
assert all(int(row["visible_listings_audited"]) == 2 for row in observed)
assert len(sample) == 14
assert set(row["role"] for row in sample) == set(row["role"] for row in observed)
assert all(Counter(row["role"] for row in sample)[r["role"]] == 2 for r in observed)

labels = [
    ("exact_internship", "Точная стажировка"),
    ("adjacent_internship", "Смежная стажировка"),
    ("related_without_explicit_internship", "Сфера близкая, стажировка не указана"),
    ("irrelevant", "Нерелевантно"),
]
counts = Counter(row["relevance_class"] for row in sample)
assert sum(counts.values()) == 14 and set(counts) == {key for key, _ in labels}

observed_sorted = sorted(observed, key=lambda row: int(row["search_matches"]), reverse=True)
with (DATA / "hh_internship_search_aggregate_2026-10-21.csv").open("w", encoding="utf-8", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["role", "search_matches", "first_two_exact", "first_two_adjacent", "first_two_other"])
    for row in observed_sorted:
        grouped = Counter(x["relevance_class"] for x in sample if x["role"] == row["role"])
        wr.writerow([
            row["role"], int(row["search_matches"]), grouped["exact_internship"],
            grouped["adjacent_internship"], grouped["related_without_explicit_internship"] + grouped["irrelevant"],
        ])

def bar_svg(rows, title, subtitle, width=1020, bar_start=320):
    row_height = 42
    height = 150 + row_height * len(rows)
    max_value = max(value for _, value in rows)
    scale = (width - bar_start - 155) / max_value
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="25" y="42" font-family="Arial" font-size="24" font-weight="bold" fill="#172943">{html.escape(title)}</text>',
        f'<text x="25" y="67" font-family="Arial" font-size="14" fill="#56657a">{html.escape(subtitle)}</text>',
    ]
    for idx, (label, value) in enumerate(rows):
        y = 88 + idx * row_height
        vwidth = value * scale
        out += [
            f'<text x="25" y="{y+19}" font-family="Arial" font-size="15" fill="#23354d">{html.escape(str(label))}</text>',
            f'<rect x="{bar_start}" y="{y}" width="{vwidth:.1f}" height="26" rx="5" fill="#4267a8"/>',
            f'<text x="{bar_start+vwidth+12:.1f}" y="{y+19}" font-family="Arial" font-size="15" fill="#23354d">{value}</text>'
        ]
    out += [f'<text x="25" y="{height-16}" font-family="Arial" font-size="12" fill="#64748b">Скриншоты hh.ru, Москва, 21.10.2026. Не показатель числа уникальных стажировок.</text>', '</svg>']
    return "\n".join(out) + "\n"

(CHARTS / "ru_internship_search_matches_2026-10-21.svg").write_text(
    bar_svg([(row["role"], int(row["search_matches"])) for row in observed_sorted],
            "Поиск стажировок в Москве", "Фильтры: Нет опыта + Стажировка; совпадения без очистки"),
    encoding="utf-8",
)
(CHARTS / "ru_internship_sample_quality_2026-10-21.svg").write_text(
    bar_svg([(label, counts[key]) for key, label in labels],
            "Качество первых двух результатов", "14 объявлений: по 2 на каждую из 7 профессий", width=990, bar_start=380),
    encoding="utf-8",
)
assert sum(int(r["search_matches"]) for r in observed) == 167
assert counts == {"exact_internship": 6, "adjacent_internship": 4, "related_without_explicit_internship": 2, "irrelevant": 2}
print("Observed queries:", len(observed))
print("Unobserved:", ", ".join(row["role"] for row in missing) or "none")
print("Search matches, NOT unique jobs:", sum(int(r["search_matches"]) for r in observed))
print("Audit categories:", dict(counts))
