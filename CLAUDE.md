# York Region 2026 Municipal Election Dashboard

## What This Is
An automated election intelligence dashboard for the York Region 2026 municipal elections (October 26, 2026). Built for the York Region Finance Department to track all races, candidates, news, and — critically — candidate alignment with YR Finance's perspective on fiscal management and Development Charges (DCs).

**Owner:** [maintainer]  
**Repo:** mandyjmoore/munielection2026  
**Live URL:** https://mandyjmoore.github.io/munielection2026 (requires GitHub Pages enabled in repo settings)

## Core Requirement
Zero manual updates. Everything is automated. The GitHub Action scrapes data every 2 hours and commits it to the repo. The dashboard auto-refreshes every 30 minutes.

## Jurisdiction
York Region, Ontario, Canada — the Region plus all 9 lower-tier municipalities:
Aurora, East Gwillimbury, Georgina, King, Markham, Newmarket, Richmond Hill, Vaughan, Whitchurch-Stouffville.

Note: **Regional Chair is provincially appointed** (Eric Jolliffe as of 2025) — not on the ballot.

## What the Dashboard Tracks
- All races: Mayor, Regional Councillor, Ward Councillors, School Board Trustees
- Incumbents vs. challengers (auto-updated as nominations come in)
- News and scandals (Google News RSS, per municipality + DC-specific)
- Fiscal alignment scores per candidate (0–10)
- DC Bylaw tracker
- Election countdown, nomination period progress

## The Central Issue: Development Charges
On May 21, 2026, Regional Council passed DC Bylaw No. 2026-20, cutting DC rates for the first time in York Region's 55-year history. This created ~$1.4B in fiscal pressure (deferrals + reductions). The province's housing legislation forced this.

**YR Finance perspective = "growth pays for growth"**: DCs must fund the infrastructure required by new development. Downloading infrastructure costs to the property tax levy is fiscally irresponsible.

## Fiscal Alignment Scoring (0–10)
Higher score = more aligned with YR Finance perspective.

**Aligned signals (score goes up):**
- "growth pays for growth"
- "infrastructure funding", "development charges must reflect costs"
- Opposition to provincial downloading of infrastructure costs
- Support for restoring/maintaining DC rates
- Fiscal responsibility, tax restraint

**Misaligned signals (score goes down):**
- "cut development charges", "reduce fees for builders"
- "housing affordability" framed as DC reduction
- Support for provincial housing mandate DC provisions
- "eliminate development charges"

Score labels: 8–10 = strongly_aligned (green), 6–7 = aligned, 4–5 = neutral (yellow), 2–3 = misaligned, 0–1 = strongly_misaligned (red)

## Architecture
```
index.html                          # Single-file dashboard, no build step
data/candidates.json                # Auto-updated every 2 hours
data/news.json                      # Auto-updated every 2 hours
data/metadata.json                  # Timestamps, stats
scraper/main.py                     # Orchestrator
scraper/fetch_candidates.py         # Scrapes all 9 municipality clerk pages
scraper/fetch_news.py               # Google News RSS feeds
scraper/score_alignment.py          # Keyword-based fiscal alignment scoring
.github/workflows/update_data.yml   # Scheduled scraper (every 2 hours)
.github/workflows/pages.yml         # GitHub Pages deployment
```

## Known Gaps / Future Work
- **Polling**: No public polling exists for York Region municipal races. News scraper will surface any that appears.
- **Odds assessment**: Currently heuristic (incumbent advantage + challenger count). Could be built out as a proper model.
- **Candidate alignment for challengers**: Starts at neutral (5) until news mentions provide signal. May need periodic review of candidates with no news coverage.
- GitHub Pages must be manually enabled once: repo Settings → Pages → Source: GitHub Actions.

## Seeded Incumbents (2022 elected, presumed running 2026)
| Municipality | Mayor |
|---|---|
| Aurora | Tom Mrakas |
| East Gwillimbury | Virginia Hackson |
| Georgina | Margaret Quirk |
| King | Steve Pellegrini |
| Markham | Frank Scarpitti |
| Newmarket | John Taylor |
| Richmond Hill | David West |
| Vaughan | Steven Del Duca |
| Whitchurch-Stouffville | Iain Lovatt |
