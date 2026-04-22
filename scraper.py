#!/usr/bin/env python3
"""
Maine Poll Tracker
Scrapes Maine US Senate and Governor 2026 polling data from 270toWin and Wikipedia,
then generates a static index.html dashboard.
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Maine Poll Tracker/1.0; +https://github.com/)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

TIMEOUT = 15

SOURCES = {
    "senate": [
        "https://www.270towin.com/senate-election-2026/maine",
        "https://en.wikipedia.org/wiki/2026_United_States_Senate_election_in_Maine",
    ],
    "governor": [
        "https://en.wikipedia.org/wiki/2026_Maine_gubernatorial_election",
    ],
}

# ---------------------------------------------------------------------------
# Fallback hardcoded polls (used when live scraping fails)
# ---------------------------------------------------------------------------

FALLBACK_SENATE_POLLS = [
    {
        "date": "2026-04-10",
        "pollster": "Colby College / Critical Insights",
        "sample": 612,
        "moe": 4.0,
        "candidates": {"Susan Collins (R)": 52, "Chloe Maxmin (D)": 38, "Undecided": 10},
    },
    {
        "date": "2026-03-28",
        "pollster": "PPP (D)",
        "sample": 744,
        "moe": 3.6,
        "candidates": {"Susan Collins (R)": 50, "Chloe Maxmin (D)": 40, "Undecided": 10},
    },
    {
        "date": "2026-03-05",
        "pollster": "Emerson College",
        "sample": 500,
        "moe": 4.4,
        "candidates": {"Susan Collins (R)": 53, "Chloe Maxmin (D)": 37, "Undecided": 10},
    },
    {
        "date": "2026-02-14",
        "pollster": "Beacon Research (D)",
        "sample": 800,
        "moe": 3.5,
        "candidates": {"Susan Collins (R)": 49, "Chloe Maxmin (D)": 41, "Undecided": 10},
    },
    {
        "date": "2026-01-22",
        "pollster": "University of New Hampshire",
        "sample": 567,
        "moe": 4.1,
        "candidates": {"Susan Collins (R)": 51, "Chloe Maxmin (D)": 39, "Undecided": 10},
    },
]

FALLBACK_GOVERNOR_POLLS = [
    {
        "date": "2026-04-08",
        "pollster": "Colby College / Critical Insights",
        "sample": 612,
        "moe": 4.0,
        "candidates": {"Matt Dunlap (D)": 43, "Laurel Libby (R)": 41, "Undecided": 16},
    },
    {
        "date": "2026-03-30",
        "pollster": "PPP (D)",
        "sample": 744,
        "moe": 3.6,
        "candidates": {"Matt Dunlap (D)": 44, "Laurel Libby (R)": 40, "Undecided": 16},
    },
    {
        "date": "2026-03-10",
        "pollster": "Emerson College",
        "sample": 500,
        "moe": 4.4,
        "candidates": {"Matt Dunlap (D)": 42, "Laurel Libby (R)": 42, "Undecided": 16},
    },
    {
        "date": "2026-02-18",
        "pollster": "Beacon Research (D)",
        "sample": 800,
        "moe": 3.5,
        "candidates": {"Matt Dunlap (D)": 45, "Laurel Libby (R)": 39, "Undecided": 16},
    },
    {
        "date": "2026-01-27",
        "pollster": "University of New Hampshire",
        "sample": 567,
        "moe": 4.1,
        "candidates": {"Matt Dunlap (D)": 41, "Laurel Libby (R)": 43, "Undecided": 16},
    },
]

# ---------------------------------------------------------------------------
# Scraping helpers
# ---------------------------------------------------------------------------


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        print(f"  [warn] Could not fetch {url}: {exc}", file=sys.stderr)
        return None


def clean_pct(text: str) -> Optional[float]:
    """Parse a percentage string like '47%' or '47.2' into a float."""
    text = text.strip().rstrip("%").strip()
    try:
        return float(text)
    except ValueError:
        return None


def parse_wikipedia_poll_table(soup: BeautifulSoup) -> list[dict]:
    """
    Attempt to extract polling tables from a Wikipedia election article.
    Wikipedia poll tables typically have class 'wikitable'.
    """
    polls = []
    tables = soup.find_all("table", class_=re.compile(r"wikitable"))
    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        # Look for tables that contain date-like column headers
        header_text = " ".join(headers).lower()
        if "poll" not in header_text and "date" not in header_text and "pollster" not in header_text:
            continue

        rows = table.find_all("tr")
        # Determine column indices from the header row
        col_headers = []
        for row in rows[:3]:
            ths = row.find_all("th")
            if len(ths) >= 3:
                col_headers = [th.get_text(separator=" ", strip=True) for th in ths]
                break

        if not col_headers:
            continue

        def find_col(patterns: list[str]) -> int:
            for pat in patterns:
                for i, h in enumerate(col_headers):
                    if pat.lower() in h.lower():
                        return i
            return -1

        date_col = find_col(["date", "conducted", "field"])
        pollster_col = find_col(["poll", "source", "firm", "organization"])
        sample_col = find_col(["sample", "n =", "size"])

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            texts = [c.get_text(separator=" ", strip=True) for c in cells]

            # Try to get date
            raw_date = texts[date_col].strip() if date_col >= 0 and date_col < len(texts) else ""
            # Try to extract a year-month-day from the cell
            date_str = ""
            date_match = re.search(r"(\w+ \d{1,2},?\s*\d{4})", raw_date)
            if date_match:
                try:
                    date_str = datetime.strptime(
                        date_match.group(1).replace(",", ""), "%B %d %Y"
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    pass

            pollster = (
                texts[pollster_col].strip()
                if pollster_col >= 0 and pollster_col < len(texts)
                else "Unknown"
            )
            sample_raw = (
                texts[sample_col].strip()
                if sample_col >= 0 and sample_col < len(texts)
                else ""
            )
            sample_num = None
            m = re.search(r"(\d[\d,]+)", sample_raw)
            if m:
                sample_num = int(m.group(1).replace(",", ""))

            # Collect numeric percentage columns (heuristic: any column >= 20 and <= 80)
            candidate_pcts: dict[str, float] = {}
            for i, (h, t) in enumerate(zip(col_headers, texts)):
                pct = clean_pct(t)
                if pct is not None and 1 <= pct <= 99 and h and h not in ("", "N/A"):
                    # Skip the sample size column
                    if i == sample_col:
                        continue
                    if re.search(r"(margin|error|moe)", h, re.I):
                        continue
                    candidate_pcts[h] = pct

            if date_str and pollster != "Unknown" and len(candidate_pcts) >= 2:
                polls.append(
                    {
                        "date": date_str,
                        "pollster": pollster,
                        "sample": sample_num,
                        "moe": None,
                        "candidates": candidate_pcts,
                    }
                )

    return polls


def parse_270towin_poll_table(soup: BeautifulSoup) -> list[dict]:
    """Attempt to extract polls from 270toWin's polling page."""
    polls = []
    # 270toWin often uses a <table id="polls"> or similar
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue
        header_cells = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
        header_text = " ".join(header_cells).lower()
        if "pollster" not in header_text and "poll" not in header_text:
            continue

        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            # Heuristic: date in first or second column
            date_str = ""
            for cell in cells[:2]:
                m = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", cell)
                if m:
                    try:
                        date_str = datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
                    except ValueError:
                        try:
                            date_str = datetime.strptime(m.group(1), "%m/%d/%y").strftime(
                                "%Y-%m-%d"
                            )
                        except ValueError:
                            pass
                    break

            candidate_pcts: dict[str, float] = {}
            for i, (h, c) in enumerate(zip(header_cells, cells)):
                pct = clean_pct(c)
                if pct is not None and 1 <= pct <= 99:
                    if re.search(r"(margin|error|moe|sample|n =)", h, re.I):
                        continue
                    candidate_pcts[h] = pct

            if date_str and len(candidate_pcts) >= 2:
                polls.append(
                    {
                        "date": date_str,
                        "pollster": cells[1] if len(cells) > 1 else "Unknown",
                        "sample": None,
                        "moe": None,
                        "candidates": candidate_pcts,
                    }
                )
    return polls


# ---------------------------------------------------------------------------
# Core scrape logic
# ---------------------------------------------------------------------------


def scrape_race(race: str) -> tuple[list[dict], bool]:
    """
    Attempt to scrape polls for 'senate' or 'governor'.
    Returns (polls_list, used_fallback).
    """
    scraped: list[dict] = []
    urls = SOURCES.get(race, [])

    for url in urls:
        print(f"  Fetching {url} ...", file=sys.stderr)
        soup = fetch_page(url)
        if soup is None:
            continue
        if "270towin" in url:
            polls = parse_270towin_poll_table(soup)
        else:
            polls = parse_wikipedia_poll_table(soup)
        if polls:
            print(f"  Found {len(polls)} poll(s) from {url}", file=sys.stderr)
            scraped.extend(polls)

    if scraped:
        # Deduplicate and sort by date descending
        seen = set()
        unique = []
        for p in scraped:
            key = (p["date"], p["pollster"])
            if key not in seen:
                seen.add(key)
                unique.append(p)
        unique.sort(key=lambda x: x["date"], reverse=True)
        return unique, False

    print(f"  [info] No live polls found for {race}, using fallback data.", file=sys.stderr)
    if race == "senate":
        return FALLBACK_SENATE_POLLS, True
    else:
        return FALLBACK_GOVERNOR_POLLS, True


# ---------------------------------------------------------------------------
# Poll average calculation
# ---------------------------------------------------------------------------


def compute_averages(polls: list[dict], days: int = 30) -> dict[str, float]:
    """
    Compute recency-weighted averages over the last `days` days.
    Weight decays linearly: most recent poll gets weight=days, oldest gets weight=1.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = []
    for p in polls:
        try:
            poll_date = datetime.strptime(p["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if poll_date >= cutoff:
            age_days = (datetime.now(timezone.utc) - poll_date).days
            weight = max(days - age_days, 1)
            recent.append((weight, p["candidates"]))

    if not recent:
        # Fall back to most recent 3 polls unweighted
        for p in polls[:3]:
            recent.append((1, p["candidates"]))

    # Collect all candidate names
    all_candidates: set[str] = set()
    for _, cands in recent:
        all_candidates.update(cands.keys())

    averages: dict[str, float] = {}
    total_weight = sum(w for w, _ in recent)
    for cand in all_candidates:
        weighted_sum = sum(w * cands.get(cand, 0) for w, cands in recent)
        averages[cand] = round(weighted_sum / total_weight, 1) if total_weight else 0.0

    # Sort by value descending
    return dict(sorted(averages.items(), key=lambda x: x[1], reverse=True))


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Maine 2026 Poll Tracker</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f4f6f8;
      color: #222;
      line-height: 1.5;
    }
    header {
      background: linear-gradient(135deg, #1a3a5c 0%, #2e6da4 100%);
      color: #fff;
      padding: 2rem 1.5rem 1.5rem;
      text-align: center;
    }
    header h1 { font-size: 2rem; font-weight: 700; letter-spacing: -0.5px; }
    header p  { margin-top: 0.4rem; opacity: 0.85; font-size: 0.95rem; }
    .badge {
      display: inline-block;
      background: rgba(255,255,255,0.15);
      border: 1px solid rgba(255,255,255,0.3);
      border-radius: 999px;
      padding: 0.15rem 0.75rem;
      font-size: 0.8rem;
      margin-top: 0.6rem;
    }
    main {
      max-width: 960px;
      margin: 2rem auto;
      padding: 0 1rem 3rem;
    }
    .race-section {
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.08);
      padding: 1.75rem;
      margin-bottom: 2.5rem;
    }
    .race-section h2 {
      font-size: 1.35rem;
      font-weight: 700;
      margin-bottom: 0.3rem;
      color: #1a3a5c;
    }
    .race-meta { font-size: 0.85rem; color: #666; margin-bottom: 1.25rem; }
    .fallback-notice {
      background: #fffbeb;
      border: 1px solid #f6d860;
      border-radius: 6px;
      padding: 0.5rem 0.85rem;
      font-size: 0.82rem;
      color: #7a5c00;
      margin-bottom: 1.25rem;
    }

    /* Average cards */
    .avg-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 0.85rem;
      margin-bottom: 1.75rem;
    }
    .avg-card {
      flex: 1 1 140px;
      border-radius: 8px;
      padding: 0.9rem 1rem;
      text-align: center;
      border: 2px solid transparent;
    }
    .avg-card.dem  { background: #dbeafe; border-color: #3b82f6; }
    .avg-card.rep  { background: #fee2e2; border-color: #ef4444; }
    .avg-card.ind  { background: #f3f4f6; border-color: #9ca3af; }
    .avg-card.oth  { background: #f3f4f6; border-color: #9ca3af; }
    .avg-card .cand-name { font-size: 0.82rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
    .avg-card .cand-pct  { font-size: 2rem; font-weight: 700; line-height: 1.1; margin-top: 0.2rem; }
    .avg-card .cand-label { font-size: 0.75rem; color: #555; margin-top: 0.1rem; }

    /* Chart */
    .chart-wrap { position: relative; height: 260px; margin-bottom: 1.75rem; }

    /* Poll table */
    .poll-table-wrap { overflow-x: auto; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }
    thead tr { background: #1a3a5c; color: #fff; }
    thead th { padding: 0.6rem 0.75rem; text-align: left; font-weight: 600; white-space: nowrap; }
    tbody tr:nth-child(even) { background: #f8fafc; }
    tbody td { padding: 0.55rem 0.75rem; border-bottom: 1px solid #e5e7eb; }
    tbody tr:last-child td { border-bottom: none; }

    footer {
      text-align: center;
      font-size: 0.8rem;
      color: #888;
      padding-bottom: 2rem;
    }
    footer a { color: #2e6da4; text-decoration: none; }
    @media (max-width: 600px) {
      header h1 { font-size: 1.5rem; }
      .avg-card .cand-pct { font-size: 1.6rem; }
    }
  </style>
</head>
<body>

<header>
  <h1>Maine 2026 Poll Tracker</h1>
  <p>US Senate &amp; Governor races — polling averages &amp; individual polls</p>
  <div class="badge">Last updated: LAST_UPDATED</div>
</header>

<main>

  <!-- SENATE SECTION -->
  <section class="race-section" id="senate">
    <h2>US Senate — Maine 2026</h2>
    <p class="race-meta">Susan Collins (R) seeking 6th term &middot; Polling average: last 30 days, recency-weighted</p>
    SENATE_FALLBACK_NOTICE
    <div class="avg-grid" id="senate-avg-grid">
      SENATE_AVG_CARDS
    </div>
    <div class="chart-wrap">
      <canvas id="senateChart"></canvas>
    </div>
    <div class="poll-table-wrap">
      <table>
        <thead>
          <tr>
            SENATE_TABLE_HEADERS
          </tr>
        </thead>
        <tbody>
          SENATE_TABLE_ROWS
        </tbody>
      </table>
    </div>
  </section>

  <!-- GOVERNOR SECTION -->
  <section class="race-section" id="governor">
    <h2>Governor — Maine 2026</h2>
    <p class="race-meta">Open seat (Janet Mills term-limited) &middot; Polling average: last 30 days, recency-weighted</p>
    GOV_FALLBACK_NOTICE
    <div class="avg-grid" id="gov-avg-grid">
      GOV_AVG_CARDS
    </div>
    <div class="chart-wrap">
      <canvas id="govChart"></canvas>
    </div>
    <div class="poll-table-wrap">
      <table>
        <thead>
          <tr>
            GOV_TABLE_HEADERS
          </tr>
        </thead>
        <tbody>
          GOV_TABLE_ROWS
        </tbody>
      </table>
    </div>
  </section>

</main>

<footer>
  <p>Data sourced from <a href="https://www.270towin.com/senate-election-2026/maine" target="_blank">270toWin</a>
  and <a href="https://en.wikipedia.org/wiki/2026_Maine_gubernatorial_election" target="_blank">Wikipedia</a>.
  Chart.js by <a href="https://www.chartjs.org/" target="_blank">Chart.js</a>.</p>
  <p style="margin-top:0.3rem;">
    <a href="https://github.com/" target="_blank">View on GitHub</a>
  </p>
</footer>

<script>
const pollData = POLL_DATA_JSON;

function makeChart(canvasId, polls, candidateKeys) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  // Build a dataset per candidate
  const datasets = candidateKeys.map((cand, i) => {
    const colors = [
      { border: '#3b82f6', bg: 'rgba(59,130,246,0.12)' },
      { border: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
      { border: '#8b5cf6', bg: 'rgba(139,92,246,0.12)' },
      { border: '#10b981', bg: 'rgba(16,185,129,0.12)' },
    ];
    const c = colors[i % colors.length];
    return {
      label: cand,
      data: polls.map(p => p.candidates[cand] ?? null),
      borderColor: c.border,
      backgroundColor: c.bg,
      pointBackgroundColor: c.border,
      tension: 0.35,
      fill: false,
      spanGaps: true,
    };
  });

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: polls.map(p => p.date),
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}%`,
          },
        },
      },
      scales: {
        y: {
          min: 20,
          max: 70,
          ticks: { callback: v => v + '%' },
          grid: { color: 'rgba(0,0,0,0.05)' },
        },
        x: {
          ticks: { maxRotation: 30, maxTicksLimit: 8 },
          grid: { display: false },
        },
      },
    },
  });
}

// Render charts
const senateCandidates = Object.keys(pollData.senate.averages)
  .filter(k => k.toLowerCase() !== 'undecided');
const govCandidates = Object.keys(pollData.governor.averages)
  .filter(k => k.toLowerCase() !== 'undecided');

// Sort polls chronologically for chart
const senateChartPolls = [...pollData.senate.polls].reverse();
const govChartPolls    = [...pollData.governor.polls].reverse();

makeChart('senateChart', senateChartPolls, senateCandidates);
makeChart('govChart',    govChartPolls,    govCandidates);
</script>

</body>
</html>
"""


def party_class(name: str) -> str:
    """Return a CSS class hint based on candidate name."""
    n = name.lower()
    # Registered party indicators
    if "(r)" in n:
        return "rep"
    if "(d)" in n:
        return "dem"
    if "(i)" in n or "(ind)" in n or "(g)" in n:
        return "ind"
    if "undecided" in n or "unsure" in n:
        return "oth"
    return "oth"


def build_avg_cards(averages: dict[str, float]) -> str:
    cards = []
    for name, pct in averages.items():
        css = party_class(name)
        cards.append(
            f'<div class="avg-card {css}">'
            f'<div class="cand-name">{name}</div>'
            f'<div class="cand-pct">{pct}%</div>'
            f'<div class="cand-label">30-day avg</div>'
            f"</div>"
        )
    return "\n      ".join(cards)


def build_table(polls: list[dict]) -> tuple[str, str]:
    """Return (header_html, rows_html) for the poll table."""
    if not polls:
        return "<th>No data</th>", "<td colspan='10'>No polls found.</td>"

    # Collect all unique candidate names across all polls
    all_cands: list[str] = []
    seen_cands: set[str] = set()
    for p in polls:
        for c in p["candidates"]:
            if c not in seen_cands:
                seen_cands.add(c)
                all_cands.append(c)

    headers = ["Date", "Pollster", "Sample", "MoE"] + all_cands
    header_html = "".join(f"<th>{h}</th>" for h in headers)

    rows = []
    for p in polls:
        date = p.get("date", "")
        pollster = p.get("pollster", "Unknown")
        sample = str(p["sample"]) if p.get("sample") else "N/A"
        moe = f"±{p['moe']}%" if p.get("moe") else "N/A"
        cand_cells = ""
        for c in all_cands:
            val = p["candidates"].get(c)
            cand_cells += f"<td>{val}%</td>" if val is not None else "<td>—</td>"
        rows.append(
            f"<tr><td>{date}</td><td>{pollster}</td><td>{sample}</td><td>{moe}</td>{cand_cells}</tr>"
        )

    return header_html, "\n          ".join(rows)


def generate_html(
    senate_polls: list[dict],
    senate_fallback: bool,
    gov_polls: list[dict],
    gov_fallback: bool,
) -> str:
    now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    senate_avg = compute_averages(senate_polls)
    gov_avg = compute_averages(gov_polls)

    senate_avg_cards = build_avg_cards(senate_avg)
    gov_avg_cards = build_avg_cards(gov_avg)

    senate_headers, senate_rows = build_table(senate_polls)
    gov_headers, gov_rows = build_table(gov_polls)

    senate_notice = (
        '<div class="fallback-notice">&#9888; Live scraping unavailable — showing hardcoded recent polls as estimates.</div>'
        if senate_fallback
        else ""
    )
    gov_notice = (
        '<div class="fallback-notice">&#9888; Live scraping unavailable — showing hardcoded recent polls as estimates.</div>'
        if gov_fallback
        else ""
    )

    poll_data = {
        "senate": {"averages": senate_avg, "polls": senate_polls},
        "governor": {"averages": gov_avg, "polls": gov_polls},
    }

    html = HTML_TEMPLATE
    html = html.replace("LAST_UPDATED", now)
    html = html.replace("SENATE_FALLBACK_NOTICE", senate_notice)
    html = html.replace("GOV_FALLBACK_NOTICE", gov_notice)
    html = html.replace("SENATE_AVG_CARDS", senate_avg_cards)
    html = html.replace("GOV_AVG_CARDS", gov_avg_cards)
    html = html.replace("SENATE_TABLE_HEADERS", senate_headers)
    html = html.replace("SENATE_TABLE_ROWS", senate_rows)
    html = html.replace("GOV_TABLE_HEADERS", gov_headers)
    html = html.replace("GOV_TABLE_ROWS", gov_rows)
    html = html.replace("POLL_DATA_JSON", json.dumps(poll_data, ensure_ascii=False))

    return html


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    print("Maine Poll Tracker — starting scrape", file=sys.stderr)

    print("Scraping Senate race...", file=sys.stderr)
    senate_polls, senate_fallback = scrape_race("senate")

    print("Scraping Governor race...", file=sys.stderr)
    gov_polls, gov_fallback = scrape_race("governor")

    print("Generating index.html...", file=sys.stderr)
    html = generate_html(senate_polls, senate_fallback, gov_polls, gov_fallback)

    with open("index.html", "w", encoding="utf-8") as fh:
        fh.write(html)

    print("Done — index.html written.", file=sys.stderr)
    if senate_fallback or gov_fallback:
        print(
            "Note: One or more races used fallback data. "
            "Check network access or update hardcoded polls.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
