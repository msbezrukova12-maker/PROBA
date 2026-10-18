"""Recompute historic search snapshot summaries; no network calls."""
from pathlib import Path
import pandas as pd
from html import escape

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
V = ROOT / "visualizations"
V.mkdir(exist_ok=True)

jobs = pd.read_csv(D / "hh_search_snapshot_2026-10-17.csv")
audit = pd.read_csv(D / "listing_quality_audit_2026-10-17.csv")
assert len(jobs) == 12 and jobs.role.nunique() == 12
assert len(audit) == 24 and all(audit.groupby("role").size() == 2)
assert set(audit.relevance) <= {"Да", "Смежная", "Нет"}
assert jobs.search_matches.ge(0).all()

ranked = jobs.sort_values("search_matches", ascending=False)
ranked.to_csv(D / "search_ranked_2026-10-17.csv", index=False)
counts = audit.relevance.value_counts().reindex(["Да", "Смежная", "Нет"], fill_value=0)
pd.DataFrame({"classification": counts.index, "count": counts.values}).to_csv(
    D / "relevance_summary_2026-10-17.csv", index=False
)

def chart(rows, title, subtitle, name_width=230, w=990):
    row_h = 40
    height = 122 + len(rows) * row_h + 48
    vmax = max(value for _, value in rows)
    scale = (w-name_width-145) / vmax
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" viewBox="0 0 {w} {height}">',
              '<rect width="100%" height="100%" fill="#ffffff"/>',
              f'<text x="28" y="37" font-size="24" font-family="Arial" font-weight="bold" fill="#18243b">{escape(title)}</text>',
              f'<text x="28" y="65" font-size="14" font-family="Arial" fill="#657186">{escape(subtitle)}</text>']
    for idx, (label, value) in enumerate(rows):
        y = 93 + idx * row_h
        pieces.extend([
            f'<text x="28" y="{y+17}" font-size="14" font-family="Arial" fill="#26334d">{escape(str(label))}</text>',
            f'<rect x="{name_width}" y="{y}" width="{round(value*scale,2)}" height="24" rx="4" fill="#4567a9"/>',
            f'<text x="{name_width+value*scale+10:.1f}" y="{y+18}" font-size="14" font-family="Arial" fill="#26334d">{value:,}</text>'
        ])
    pieces.extend([f'<text x="28" y="{height-15}" font-size="12" font-family="Arial" fill="#647084">Источник: сохранённый срез 17.10.2026; см. data/README.md</text>', '</svg>'])
    return "\n".join(pieces)

(V / "search_matches.svg").write_text(chart(
    list(zip(ranked.role, ranked.search_matches)),
    "Поисковые совпадения hh.ru: 12 направлений",
    "НЕ число уникальных вакансий. Не рейтинг перспективности профессий.",
    name_width=245), encoding="utf-8")

(V / "relevance_audit.svg").write_text(chart(
    [(k, int(v)) for k, v in counts.items()],
    "Аудит первых двух объявлений на запрос",
    "24 неслучайных наблюдения; нельзя экстраполировать доли на рынок.",
    name_width=180, w=800), encoding="utf-8")

print("Rows:", len(jobs), "audit:", len(audit), "relevance:", counts.to_dict())
