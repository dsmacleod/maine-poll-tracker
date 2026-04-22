# Maine 2026 Poll Tracker

A static dashboard that tracks polling for the 2026 Maine US Senate and Governor races.
It scrapes [270toWin](https://www.270towin.com/senate-election-2026/maine) and
[Wikipedia](https://en.wikipedia.org/wiki/2026_Maine_gubernatorial_election), generates
`index.html`, and publishes it to GitHub Pages — automatically every day at 8 AM ET.

## Races covered

| Race | Incumbent / Notes |
|------|-------------------|
| US Senate | Susan Collins (R) seeking a 6th term |
| Governor | Open seat — Janet Mills is term-limited |

---

## Setup instructions

### 1. Create the GitHub repository

1. Go to <https://github.com/new>.
2. Name it **maine-poll-tracker**.
3. Set visibility to **Public** (required for free GitHub Pages).
4. Do **not** initialise with a README — you will push files yourself.

### 2. Push files

```bash
cd /path/to/maine-poll-tracker
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/maine-poll-tracker.git
git push -u origin main
```

Replace `USERNAME` with your GitHub username.

### 3. Enable GitHub Pages

1. Open the repository on GitHub.
2. Go to **Settings → Pages**.
3. Under **Source**, select **Deploy from a branch**.
4. Set **Branch** to `main` and folder to `/ (root)`.
5. Click **Save**.

Your site will be live at `https://USERNAME.github.io/maine-poll-tracker` within a minute or two.

### 4. Allow the workflow to push changes

1. Go to **Settings → Actions → General**.
2. Scroll to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

### 5. Trigger the first run

1. Go to the **Actions** tab.
2. Click **Scrape and Publish Maine Poll Tracker** in the left sidebar.
3. Click **Run workflow → Run workflow**.

This generates `index.html` and commits it. Subsequent runs happen automatically every day at 8 AM ET.

---

## Local development

```bash
# Install dependencies
pip install requests beautifulsoup4 lxml

# Run the scraper (writes index.html to the current directory)
python scraper.py

# Open the result
open index.html   # macOS
xdg-open index.html  # Linux
```

### Fallback behaviour

If the scraper cannot reach 270toWin or Wikipedia (e.g. 403 / timeout in CI),
it falls back to hardcoded recent polls so the dashboard is never empty.
A yellow notice banner is shown on the page whenever fallback data is used.

---

## Project structure

```
maine-poll-tracker/
├── scraper.py                  # Scraper + HTML generator
├── index.html                  # Generated dashboard (committed by CI)
├── README.md
└── .github/
    └── workflows/
        └── scrape.yml          # Daily GitHub Actions workflow
```

---

## Live site

`https://USERNAME.github.io/maine-poll-tracker`
