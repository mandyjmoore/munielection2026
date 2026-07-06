# York Region 2026 Municipal Election Dashboard

## What This Is
An automated election intelligence dashboard for the York Region 2026 municipal elections (October 26, 2026). Built for the York Region Finance Department (its analysts) because the makeup of the incoming Council directly affects the Region's budget, fiscal strategy, and Development Charges policy.

**Owner:** [maintainer]
**Repo:** mandyjmoore/munielection2026
**Live URL:** https://mandyjmoore.github.io/munielection2026
**Local clone:** iCloud Drive `Projects/York Region Municipal Election Dashboard` (keep local + GitHub in sync — standing rule)

## The Three Core Requirements (in priority order)
1. **Candidate registration detection is the main function.** The owner's words: "Otherwise I'd just build an Excel file and update it myself." The scraper pulls each municipal clerk's official registered-candidates page every 2 hours. New filings must be visible at a glance.
2. **Lame-duck status at a glance.** Under Municipal Act s.275, York Regional Council becomes "lame duck" (restricted from major decisions: senior staff changes, $50k+ unbudgeted spending, asset sales) if fewer than **16 of its 21 elected members** (9 Mayors + 12 Regional Councillors; the appointed Chair is excluded) file for re-election by nomination day (**Aug 21, 2026, 2 p.m.**). Same 3/4 rule computed per municipal council as a secondary metric.
3. **Fiscal alignment weighted toward actual voting record** (DCs and reserves especially), not just news keywords — see Scoring below.

## Design Philosophy (learned the hard way)
Distinguish visibly between **confirmed** (official clerk filing, documented recorded vote), **inferred** (news keywords, incumbency heuristics), and **unknown**. Never let absence of data become a plausible-looking fabricated value. Predecessor failure: a generic scraper fallback once recorded 330 nav-menu links ("Report A Problem", "Food Safety") as candidates. All estimates (likely-to-run-again, likely-to-win) are ordinal labels with visible `basis` reasons and dashed-border styling — never percentages, never solid badges.

## Zero Manual Updates (with honest exceptions)
GitHub Action scrapes every 2 hours and commits; dashboard auto-refreshes every 30 minutes. Exceptions that are deliberately manual:
- `data/votes.json` — hand-curated recorded council votes (small, high-signal set)
- Markham + Vaughan (bot-blocked) and Whitchurch-Stouffville (JS-rendered) can't be auto-scraped; their filings need periodic manual checks

## Jurisdiction & Seats
York Region, Ontario — 9 lower-tier municipalities: Aurora, East Gwillimbury, Georgina, King, Markham, Newmarket, Richmond Hill, Vaughan, Whitchurch-Stouffville. **Regional Chair is provincially appointed** (Eric Jolliffe) — not on the ballot.

**76 seats total** in `data/seats.json` (verified 2022 inventory): 9 Mayors + 12 Regional Councillors (Markham 4, Vaughan 4, Richmond Hill 2, Georgina 1, Newmarket 1 — elected at-large) + 55 Ward Councillors (East Gwillimbury elects 2 per ward). In the 6 municipalities without a separate regional seat, the Mayor is the sole regional representative. School board trustees are not tracked.

## The Central Issue: Development Charges
On May 21, 2026, Regional Council passed DC Bylaw No. 2026-20, cutting DC rates for the first time in York Region's 55-year history (~$1.4B fiscal pressure; provincially forced via Bill 17). **YR Finance perspective = "growth pays for growth"**: DCs must fund the infrastructure new development requires; downloading those costs to the property tax levy is fiscally irresponsible.

## Fiscal Alignment Scoring (0–10, higher = more aligned with YR Finance)
Priority order of signal, recorded in each candidate's `fiscal_alignment_basis`:
1. **`voting_record`** — recorded votes in `data/votes.json` dominate (±3 per vote); news keywords become a minor secondary nudge
2. **`news_inferred`** — keyword deltas from news mentions (aligned: "growth pays for growth", "infrastructure funding", oppose DC cuts; misaligned: "cut development charges", "eliminate development charges", DC-framed affordability)
3. **`incumbency_default`** — no signal at all: incumbents get −1 (tacit association with DC Bylaw 2026-20), stated plainly in `fiscal_notes`
4. **`unscored`** — challengers with no signal stay neutral 5

Labels: 8–10 strongly_aligned, 6–7 aligned, 4–5 neutral, 2–3 misaligned, 0–1 strongly_misaligned.

**Open manual item:** whether the May 21, 2026 DC Bylaw vote was a recorded roll-call is unconfirmed. Decision doc (couldn't be fetched by tooling — SSL): https://yorkpublishing.escribemeetings.com/filestream.ashx?DocumentId=47492. If roll-call: transcribe into `votes.json` `results[]`, set `source_type: "recorded_vote"`. If consent: set `"consent_agenda_no_breakdown"`, leave `results` empty.

## Architecture
```
index.html                          # Single-file dashboard, no build step, vanilla JS + Chart.js
data/seats.json                     # 76-seat inventory (manual seed, static) — the backbone; everything joins on seat_id
data/candidates.json                # Auto-updated: incumbents + scraped filings, scores, outlook estimates
data/council_status.json            # Computed lame-duck math (regional + per-municipality)
data/votes.json                     # Hand-curated recorded council votes
data/news.json                      # Google News RSS, 90-day retention
data/metadata.json                  # Timestamps, counts, data_confidence block
scraper/main.py                     # Orchestrator (news → candidates → score → outlook → council status)
scraper/fetch_candidates.py         # Per-municipality extractors, verified against real clerk pages
scraper/fetch_news.py               # RSS feeds; word-boundary municipality matching; York-Region-relevance filter
scraper/score_alignment.py          # Voting-record-first scoring (score_from_votes + score_from_text)
scraper/compute_council_status.py   # s.275 lame-duck calculator (pure function; 21/16 hardcoded w/ assertion)
scraper/estimate_race_outlook.py    # likely_to_run_again / likely_to_win ordinal heuristics
.github/workflows/update_data.yml   # Cron every 2 hours
.github/workflows/pages.yml         # Pages deploy on push to index.html or data/**
```

## Scrape Coverage (verified 2026-07-02)
| Municipality | Status | Notes |
|---|---|---|
| Georgina, Richmond Hill, Newmarket, Aurora, East Gwillimbury, King | ✅ live | Real clerk pages, per-municipality extractors tested against snapshots |
| Markham | ❌ bot-blocked | electionsmarkham.ca returns Reblaze JS challenge (HTTP 247) |
| Vaughan | ❌ bot-blocked | vaughan.ca returns 403 to non-browser requests |
| Whitchurch-Stouffville | ❌ JS-rendered | stouffvillevotes.ca list renders client-side only |

Scraper safeguards (do not remove): office allowlist, municipality allowlist, per-municipality candidate cap, page-must-mention-candidates check, no generic list-extraction fallback. King's extractor maps tables to offices **by position** (page has no per-office headings) — re-verify if King results look wrong.

## Known Gaps / Future Work
- `votes.json` is empty pending the DC Bylaw roll-call research (see Open manual item above)
- Markham/Vaughan/W-S filings need manual entry or a browser-based scrape workaround
- No public polling exists for these races; likely-to-win stays a low-confidence ordinal
- Manual review cadence: check unscrapable clerk pages weekly through July, twice-weekly in August (nom close Aug 21)

## Current Incumbents (2022 elected; filing status tracked live in candidates.json)
Mayors: Mrakas (Aurora), Hackson (East Gwillimbury), Quirk (Georgina), Pellegrini (King), Scarpitti (Markham), Taylor (Newmarket), West (Richmond Hill), Del Duca (Vaughan), Lovatt (Whitchurch-Stouffville). Full 76-incumbent roster lives in `data/seats.json`.
