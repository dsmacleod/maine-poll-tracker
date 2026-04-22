#!/usr/bin/env python3
"""
Maine 2026 Poll Tracker
Covers: US Senate, Governor, CD-1, CD-2 — primaries and general election matchups.
Hardcoded data reflects verified polls through April 2026; Wikipedia scraping supplements.
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Maine Poll Tracker/1.0; +https://github.com/)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
TIMEOUT = 15

# ---------------------------------------------------------------------------
# Verified poll data (sourced from Emerson, UNH, Pan Atlantic, Punchbowl, RCP)
# ---------------------------------------------------------------------------

POLL_DATA = {
    # ── US SENATE ────────────────────────────────────────────────────────────
    "senate_dem_primary": {
        "race": "US Senate",
        "section": "Democratic Primary",
        "note": "Primary: June 9, 2026",
        "polls": [
            {
                "date": "2026-04-07",
                "pollster": "Maine Beacon / Aggregate",
                "sample": None, "moe": None,
                "candidates": {"Graham Platner (D)": 61, "Janet Mills (D)": 28, "Undecided": 11},
            },
            {
                "date": "2026-03-21",
                "pollster": "Emerson College",
                "sample": None, "moe": None,
                "candidates": {"Graham Platner (D)": 55, "Janet Mills (D)": 28, "Undecided": 13},
            },
            {
                "date": "2026-02-16",
                "pollster": "UNH Survey Center",
                "sample": 462, "moe": None,
                "candidates": {"Graham Platner (D)": 64, "Janet Mills (D)": 26, "Undecided": 10},
            },
        ],
    },
    "senate_gen_platner": {
        "race": "US Senate",
        "section": "General Election: Collins vs. Platner",
        "note": "RCP avg: Platner +7.6 (47.6% vs 40.0%)",
        "polls": [
            {
                "date": "2026-04-09",
                "pollster": "Decision Desk HQ",
                "sample": 157, "moe": None,
                "candidates": {"Graham Platner (D)": 44, "Susan Collins (R)": 44, "Other/Undecided": 12},
            },
            {
                "date": "2026-04-09",
                "pollster": "Race to the WH",
                "sample": 500, "moe": None,
                "candidates": {"Graham Platner (D)": 48, "Susan Collins (R)": 41, "Other/Undecided": 11},
            },
            {
                "date": "2026-03-21",
                "pollster": "Emerson College",
                "sample": None, "moe": None,
                "candidates": {"Graham Platner (D)": 48, "Susan Collins (R)": 41, "Other/Undecided": 11},
            },
            {
                "date": "2026-02-16",
                "pollster": "UNH Survey Center",
                "sample": 462, "moe": None,
                "candidates": {"Graham Platner (D)": 49, "Susan Collins (R)": 38, "Other/Undecided": 13},
            },
        ],
    },
    "senate_gen_mills": {
        "race": "US Senate",
        "section": "General Election: Collins vs. Mills",
        "note": "Alternate matchup if Mills wins primary",
        "polls": [
            {
                "date": "2026-04-09",
                "pollster": "270toWin Aggregate",
                "sample": 138, "moe": None,
                "candidates": {"Janet Mills (D)": 45, "Susan Collins (R)": 45, "Other/Undecided": 10},
            },
            {
                "date": "2026-03-21",
                "pollster": "Emerson College",
                "sample": None, "moe": None,
                "candidates": {"Janet Mills (D)": 46, "Susan Collins (R)": 43, "Other/Undecided": 11},
            },
            {
                "date": "2026-02-16",
                "pollster": "UNH Survey Center",
                "sample": 462, "moe": None,
                "candidates": {"Janet Mills (D)": 41, "Susan Collins (R)": 40, "Other/Undecided": 19},
            },
        ],
    },
    # ── GOVERNOR ─────────────────────────────────────────────────────────────
    "gov_dem_primary": {
        "race": "Governor",
        "section": "Democratic Primary",
        "note": "Primary: June 9, 2026. No general-election matchup polls yet.",
        "polls": [
            {
                "date": "2026-03-05",
                "pollster": "Pan Atlantic Research",
                "sample": None, "moe": None,
                "candidates": {
                    "Nirav Shah (D)": 24,
                    "Angus King III (D)": 24,
                    "Hannah Pingree (D)": 18,
                    "Shenna Bellows (D)": 16,
                    "Troy Jackson (D)": 10,
                    "Undecided": 8,
                },
            },
            {
                "date": "2025-12-11",
                "pollster": "Pan Atlantic Research",
                "sample": None, "moe": None,
                "candidates": {
                    "Nirav Shah (D)": 24,
                    "Angus King III (D)": 19,
                    "Hannah Pingree (D)": 18,
                    "Shenna Bellows (D)": 16,
                    "Troy Jackson (D)": 8,
                    "Undecided": 15,
                },
            },
        ],
    },
    "gov_rep_primary": {
        "race": "Governor",
        "section": "Republican Primary",
        "note": "Primary: June 9, 2026. 44% of R voters not yet familiar with all candidates.",
        "polls": [
            {
                "date": "2026-03-05",
                "pollster": "Pan Atlantic Research",
                "sample": None, "moe": None,
                "candidates": {
                    "Bobby Charles (R)": 26,
                    "Garrett Mason (R)": 11,
                    "Jim Libby (R)": 8,
                    "Undecided/Other": 55,
                },
            },
        ],
    },
    # ── CD-1 ─────────────────────────────────────────────────────────────────
    "cd1_gen": {
        "race": "CD-1 (House)",
        "section": "General Election",
        "note": "Incumbent Chellie Pingree (D) won 58.1% in 2024. No public polling available yet.",
        "polls": [],
    },
    # ── CD-2 ─────────────────────────────────────────────────────────────────
    "cd2_dem_primary": {
        "race": "CD-2 (House)",
        "section": "Democratic Primary",
        "note": "Primary: June 9, 2026. Open seat after Jared Golden withdrew Nov. 2025.",
        "polls": [
            {
                "date": "2026-03-05",
                "pollster": "Pan Atlantic Research",
                "sample": None, "moe": None,
                "candidates": {
                    "Joe Baldacci (D)": 36,
                    "Matt Dunlap (D)": 14,
                    "Jordan Wood (D)": 12,
                    "Undecided": 38,
                },
            },
        ],
    },
    "cd2_gen_baldacci": {
        "race": "CD-2 (House)",
        "section": "General: LePage vs. Baldacci",
        "note": "Trump won CD-2 53.5%–44.5% in 2024.",
        "polls": [
            {
                "date": "2026-02-16",
                "pollster": "UNH Survey Center",
                "sample": 462, "moe": 5.1,
                "candidates": {"Paul LePage (R)": 48, "Joe Baldacci (D)": 47, "Other/Undecided": 5},
            },
            {
                "date": "2026-02-01",
                "pollster": "Punchbowl News / Internal",
                "sample": None, "moe": 5.1,
                "candidates": {"Paul LePage (R)": 44, "Joe Baldacci (D)": 43, "Other/Undecided": 13},
            },
        ],
    },
    "cd2_gen_dunlap": {
        "race": "CD-2 (House)",
        "section": "General: LePage vs. Dunlap",
        "note": "Alternate matchup if Dunlap wins primary.",
        "polls": [
            {
                "date": "2026-02-16",
                "pollster": "UNH Survey Center",
                "sample": 462, "moe": 5.1,
                "candidates": {"Paul LePage (R)": 47, "Matt Dunlap (D)": 46, "Other/Undecided": 7},
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Wikipedia scraper (supplements hardcoded data for Senate general)
# ---------------------------------------------------------------------------

WIKI_SOURCES = {
    "senate_gen_platner": "https://en.wikipedia.org/wiki/2026_United_States_Senate_election_in_Maine",
}

SENATE_GEN_REPUBLICANS = ["Susan Collins"]
SENATE_GEN_DEMOCRATS = ["Graham Platner", "Janet Mills"]


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        print(f"  [warn] Could not fetch {url}: {exc}", file=sys.stderr)
        return None


def clean_pct(text: str) -> Optional[float]:
    text = text.strip().rstrip("%").strip()
    try:
        v = float(text)
        return v if 1 <= v <= 99 else None
    except ValueError:
        return None


def parse_wikipedia_polls(soup: BeautifulSoup, require_r_names: list[str]) -> list[dict]:
    polls = []
    for table in soup.find_all("table", class_=re.compile(r"wikitable")):
        headers = [th.get_text(separator=" ", strip=True) for th in table.find_all("th")]
        header_text = " ".join(headers).lower()
        if not any(k in header_text for k in ["poll", "date", "pollster"]):
            continue

        col_headers: list[str] = []
        for row in table.find_all("tr")[:3]:
            ths = row.find_all("th")
            if len(ths) >= 3:
                col_headers = [th.get_text(separator=" ", strip=True) for th in ths]
                break
        if not col_headers:
            continue

        def find_col(patterns):
            for pat in patterns:
                for i, h in enumerate(col_headers):
                    if pat.lower() in h.lower():
                        return i
            return -1

        date_col = find_col(["date", "conducted", "field"])
        pollster_col = find_col(["poll", "source", "firm", "organization"])
        sample_col = find_col(["sample", "n =", "size"])

        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            texts = [c.get_text(separator=" ", strip=True) for c in cells]

            raw_date = texts[date_col] if date_col >= 0 and date_col < len(texts) else ""
            date_str = ""
            m = re.search(r"(\w+ \d{1,2},?\s*\d{4})", raw_date)
            if m:
                try:
                    date_str = datetime.strptime(m.group(1).replace(",", ""), "%B %d %Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass

            pollster = texts[pollster_col] if pollster_col >= 0 and pollster_col < len(texts) else "Unknown"
            sample_raw = texts[sample_col] if sample_col >= 0 and sample_col < len(texts) else ""
            sample_num = None
            sm = re.search(r"(\d[\d,]+)", sample_raw)
            if sm:
                sample_num = int(sm.group(1).replace(",", ""))

            cand_pcts: dict[str, float] = {}
            for i, (h, t) in enumerate(zip(col_headers, texts)):
                if i == sample_col:
                    continue
                if re.search(r"(margin|error|moe)", h, re.I):
                    continue
                pct = clean_pct(t)
                if pct is not None and h:
                    cand_pcts[h] = pct

            if not date_str or len(cand_pcts) < 2:
                continue

            # Only keep polls that include at least one known Republican
            cand_keys_lower = " ".join(cand_pcts.keys()).lower()
            if not any(r.lower() in cand_keys_lower for r in require_r_names):
                continue

            polls.append({
                "date": date_str,
                "pollster": pollster.strip(),
                "sample": sample_num,
                "moe": None,
                "candidates": cand_pcts,
            })

    return polls


def try_supplement_from_wiki(key: str, existing_polls: list[dict]) -> list[dict]:
    url = WIKI_SOURCES.get(key)
    if not url:
        return existing_polls

    print(f"  Fetching Wikipedia for {key}...", file=sys.stderr)
    soup = fetch_page(url)
    if not soup:
        return existing_polls

    wiki_polls = parse_wikipedia_polls(soup, require_r_names=SENATE_GEN_REPUBLICANS)
    if not wiki_polls:
        return existing_polls

    # Merge: add any Wikipedia poll not already in hardcoded data
    existing_keys = {(p["date"], p["pollster"]) for p in existing_polls}
    new = [p for p in wiki_polls if (p["date"], p["pollster"]) not in existing_keys]
    if new:
        print(f"  Added {len(new)} supplemental poll(s) from Wikipedia.", file=sys.stderr)
    return sorted(existing_polls + new, key=lambda x: x["date"], reverse=True)


# ---------------------------------------------------------------------------
# Poll average
# ---------------------------------------------------------------------------

def compute_averages(polls: list[dict], days: int = 60) -> dict[str, float]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    weighted: list[tuple[float, dict]] = []
    for p in polls:
        try:
            poll_date = datetime.strptime(p["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if poll_date >= cutoff:
            age = (datetime.now(timezone.utc) - poll_date).days
            weight = max(days - age, 1)
            weighted.append((weight, p["candidates"]))

    if not weighted:
        weighted = [(1, p["candidates"]) for p in polls[:3]]

    all_cands: set[str] = set()
    for _, cands in weighted:
        all_cands.update(cands.keys())

    total_w = sum(w for w, _ in weighted)
    avgs = {}
    for cand in all_cands:
        avgs[cand] = round(sum(w * c.get(cand, 0) for w, c in weighted) / total_w, 1)
    return dict(sorted(avgs.items(), key=lambda x: x[1], reverse=True))


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def party_class(name: str) -> str:
    n = name.lower()
    if "(r)" in n:
        return "rep"
    if "(d)" in n:
        return "dem"
    if "undecided" in n or "unsure" in n or "other" in n:
        return "und"
    return "oth"


CHART_COLORS = {
    "dem": {"border": "#3b82f6", "bg": "rgba(59,130,246,0.12)"},
    "rep": {"border": "#ef4444", "bg": "rgba(239,68,68,0.12)"},
    "und": {"border": "#9ca3af", "bg": "rgba(156,163,175,0.08)"},
    "oth": {"border": "#8b5cf6", "bg": "rgba(139,92,246,0.12)"},
}


def build_section_html(key: str, data: dict) -> str:
    polls = data["polls"]
    avgs = compute_averages(polls) if polls else {}
    note = data.get("note", "")
    section_title = data["section"]
    race = data["race"]

    # Avg cards
    avg_cards = ""
    for name, pct in avgs.items():
        css = party_class(name)
        avg_cards += (
            f'<div class="avg-card {css}">'
            f'<div class="cand-name">{name}</div>'
            f'<div class="cand-pct">{pct}%</div>'
            f'<div class="cand-label">avg</div>'
            f"</div>\n"
        )

    if not polls:
        chart_html = ""
        table_html = '<p class="no-data">No public polling available yet.</p>'
    else:
        # Chart
        all_cands = list(avgs.keys())
        chart_labels = json.dumps([p["date"] for p in reversed(polls)])
        datasets = []
        for i, cand in enumerate(all_cands):
            if "undecided" in cand.lower() or "other" in cand.lower():
                continue
            css = party_class(cand)
            c = CHART_COLORS.get(css, CHART_COLORS["oth"])
            vals = json.dumps([p["candidates"].get(cand) for p in reversed(polls)])
            datasets.append(
                f'{{"label":{json.dumps(cand)},"data":{vals},'
                f'"borderColor":"{c["border"]}","backgroundColor":"{c["bg"]}",'
                f'"pointBackgroundColor":"{c["border"]}","tension":0.35,"fill":false,"spanGaps":true}}'
            )
        chart_id = re.sub(r"[^a-z0-9]", "_", key)
        chart_html = (
            f'<div class="chart-wrap"><canvas id="chart_{chart_id}"></canvas></div>\n'
            f'<script>makeChart("chart_{chart_id}",[{",".join(datasets)}],{chart_labels});</script>'
        )

        # Table
        all_poll_cands: list[str] = []
        seen: set[str] = set()
        for p in polls:
            for c in p["candidates"]:
                if c not in seen:
                    seen.add(c)
                    all_poll_cands.append(c)
        headers_html = "".join(f"<th>{h}</th>" for h in ["Date", "Pollster", "Sample", "MoE"] + all_poll_cands)
        rows_html = ""
        for p in polls:
            cells = (
                f"<td>{p['date']}</td>"
                f"<td>{p['pollster']}</td>"
                f"<td>{p['sample'] or 'N/A'}</td>"
                f"<td>{'±' + str(p['moe']) + '%' if p.get('moe') else 'N/A'}</td>"
            )
            for c in all_poll_cands:
                v = p["candidates"].get(c)
                cells += f"<td>{v}%</td>" if v is not None else "<td>—</td>"
            rows_html += f"<tr>{cells}</tr>\n"
        table_html = (
            f'<div class="poll-table-wrap"><table>'
            f"<thead><tr>{headers_html}</tr></thead>"
            f"<tbody>{rows_html}</tbody></table></div>"
        )

    note_html = f'<p class="race-note">{note}</p>' if note else ""
    return f"""
  <section class="subsection">
    <h3>{section_title}</h3>
    {note_html}
    <div class="avg-grid">{avg_cards}</div>
    {chart_html}
    {table_html}
  </section>
"""


def generate_html(poll_data: dict, last_updated: str) -> str:
    # Group sections by race
    race_order = ["US Senate", "Governor", "CD-2 (House)", "CD-1 (House)"]
    by_race: dict[str, list[tuple[str, dict]]] = {r: [] for r in race_order}
    for key, data in poll_data.items():
        race = data["race"]
        if race in by_race:
            by_race[race].append((key, data))

    race_html = ""
    for race in race_order:
        sections = by_race.get(race, [])
        if not sections:
            continue
        inner = "".join(build_section_html(k, d) for k, d in sections)
        race_html += f'<div class="race-card"><h2>{race}</h2>{inner}</div>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Maine 2026 Poll Tracker</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f4f6f8;color:#222;line-height:1.5}}
    header{{background:linear-gradient(135deg,#1a3a5c 0%,#2e6da4 100%);color:#fff;padding:2rem 1.5rem 1.5rem;text-align:center}}
    header h1{{font-size:2rem;font-weight:700}}
    header p{{margin-top:0.4rem;opacity:0.85;font-size:0.95rem}}
    .badge{{display:inline-block;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);border-radius:999px;padding:0.15rem 0.75rem;font-size:0.8rem;margin-top:0.6rem}}
    main{{max-width:980px;margin:2rem auto;padding:0 1rem 3rem}}
    .race-card{{background:#fff;border-radius:12px;box-shadow:0 1px 6px rgba(0,0,0,0.08);padding:1.75rem;margin-bottom:2.5rem}}
    .race-card h2{{font-size:1.4rem;font-weight:700;color:#1a3a5c;border-bottom:2px solid #e5e7eb;padding-bottom:0.6rem;margin-bottom:1.25rem}}
    .subsection{{margin-bottom:2rem;padding-bottom:1.5rem;border-bottom:1px solid #f0f0f0}}
    .subsection:last-child{{border-bottom:none;margin-bottom:0;padding-bottom:0}}
    .subsection h3{{font-size:1.05rem;font-weight:600;color:#374151;margin-bottom:0.4rem}}
    .race-note{{font-size:0.82rem;color:#6b7280;margin-bottom:0.9rem}}
    .avg-grid{{display:flex;flex-wrap:wrap;gap:0.75rem;margin-bottom:1.25rem}}
    .avg-card{{flex:1 1 130px;border-radius:8px;padding:0.8rem 0.9rem;text-align:center;border:2px solid transparent}}
    .avg-card.dem{{background:#dbeafe;border-color:#3b82f6}}
    .avg-card.rep{{background:#fee2e2;border-color:#ef4444}}
    .avg-card.und,.avg-card.oth{{background:#f3f4f6;border-color:#d1d5db}}
    .avg-card .cand-name{{font-size:0.78rem;font-weight:600;text-transform:uppercase;letter-spacing:0.04em}}
    .avg-card .cand-pct{{font-size:1.85rem;font-weight:700;line-height:1.1;margin-top:0.15rem}}
    .avg-card .cand-label{{font-size:0.72rem;color:#555;margin-top:0.1rem}}
    .chart-wrap{{position:relative;height:230px;margin-bottom:1.25rem}}
    .poll-table-wrap{{overflow-x:auto}}
    table{{width:100%;border-collapse:collapse;font-size:0.86rem}}
    thead tr{{background:#1a3a5c;color:#fff}}
    thead th{{padding:0.55rem 0.7rem;text-align:left;font-weight:600;white-space:nowrap}}
    tbody tr:nth-child(even){{background:#f8fafc}}
    tbody td{{padding:0.5rem 0.7rem;border-bottom:1px solid #e5e7eb}}
    tbody tr:last-child td{{border-bottom:none}}
    .no-data{{font-size:0.88rem;color:#9ca3af;font-style:italic;padding:0.5rem 0}}
    footer{{text-align:center;font-size:0.8rem;color:#888;padding-bottom:2rem}}
    footer a{{color:#2e6da4;text-decoration:none}}
    @media(max-width:600px){{header h1{{font-size:1.5rem}}.avg-card .cand-pct{{font-size:1.5rem}}}}
  </style>
</head>
<body>
<header>
  <h1>Maine 2026 Poll Tracker</h1>
  <p>Senate &bull; Governor &bull; CD-1 &bull; CD-2 &mdash; primaries &amp; general election matchups</p>
  <div class="badge">Last updated: {last_updated}</div>
</header>
<main>
{race_html}
</main>
<footer>
  <p>Sources: <a href="https://emersoncollegepolling.com" target="_blank">Emerson College</a> &bull;
  <a href="https://scholars.unh.edu/survey_center_polls/" target="_blank">UNH Survey Center</a> &bull;
  <a href="https://www.realclearpolling.com" target="_blank">RealClearPolling</a> &bull;
  <a href="https://en.wikipedia.org/wiki/2026_United_States_Senate_election_in_Maine" target="_blank">Wikipedia</a></p>
  <p style="margin-top:0.3rem"><a href="https://github.com/sloftus-lab/maine-poll-tracker" target="_blank">View on GitHub</a></p>
</footer>
<script>
function makeChart(canvasId, datasets, labels) {{
  const ctx = document.getElementById(canvasId);
  if (!ctx || !datasets.length) return;
  new Chart(ctx, {{
    type: 'line',
    data: {{ labels, datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ position: 'top' }},
        tooltip: {{ callbacks: {{ label: c => c.dataset.label + ': ' + c.parsed.y + '%' }} }},
      }},
      scales: {{
        y: {{ min: 10, max: 75, ticks: {{ callback: v => v + '%' }}, grid: {{ color: 'rgba(0,0,0,0.05)' }} }},
        x: {{ ticks: {{ maxRotation: 30, maxTicksLimit: 6 }}, grid: {{ display: false }} }},
      }},
    }},
  }});
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Maine 2026 Poll Tracker — building...", file=sys.stderr)

    poll_data = dict(POLL_DATA)

    # Try to supplement Senate general with live Wikipedia data
    poll_data["senate_gen_platner"]["polls"] = try_supplement_from_wiki(
        "senate_gen_platner", poll_data["senate_gen_platner"]["polls"]
    )

    last_updated = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    html = generate_html(poll_data, last_updated)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Done — index.html written.", file=sys.stderr)


if __name__ == "__main__":
    main()
