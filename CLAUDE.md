# York Region 2026 Municipal Election Dashboard

## What This Is
An automated election intelligence dashboard for the York Region 2026 municipal elections (October 26, 2026). Built for the York Region Finance Department (the owner and her boss) because the makeup of the incoming Council directly affects the Region's budget, fiscal strategy, and Development Charges policy.

**Owner:** Mandy Moore (mandyjmoore@gmail.com)
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
- `data/votes.json` — hand-curated scored votes (each fiscally classified with direction + weight; `match_snippet` links it to its motion in the voting record)
- `data/voting_record.json` — the full motion-level record of this council since the Nov 2022 inauguration (449 motions, 47 meetings, all 23 recorded votes with member breakdowns; routine procedural motions excluded per owner rule; `staff_recommended` inferred from motion structure). Refresh after new meetings with `python3 scraper/harvest_voting_record.py` (run manually — not part of the 2-hour pipeline), then review any NEW recorded votes for scoring candidacy and add fiscally relevant ones to `votes.json`
- `data/manual_overrides.json` — human-verified facts for what scrapers can't reach (primarily **Vaughan** filings). Applied by main.py after every fetch, so they always win. Each entry needs provenance (verified_by / verified_on / source). Lesson from the Del Duca miss (showed "Not registered" for two months after he filed May 1): the news feed can't backfill events older than its collection start, so Vaughan corrections MUST come through this file when the owner checks vaughan.ca/council/elections/candidates

## Jurisdiction & Seats
York Region, Ontario — 9 lower-tier municipalities: Aurora, East Gwillimbury, Georgina, King, Markham, Newmarket, Richmond Hill, Vaughan, Whitchurch-Stouffville. **Regional Chair is provincially appointed** (Eric Jolliffe) — not on the ballot.

**21 seats total** in `data/seats.json`: 9 Mayors + 12 Regional Councillors (Markham 4, Vaughan 4, Richmond Hill 2, Georgina 1, Newmarket 1 — elected at-large). In the 6 municipalities without a separate regional seat, the Mayor is the sole regional representative. School board trustees are not tracked.

**Scope (owner decision, final form 2026-07-06): Regional Council races ONLY — data and display.** Ward councillor candidates are not collected, stored, or shown anywhere (the scraper's `VALID_OFFICES` rejects them at extraction). This also removed the per-municipality lame-duck calculation (it needed local rosters); only the 21-member Regional Council s.275 math remains. An earlier iteration kept ward data for that municipal math — both were removed together at the owner's direction, so don't reintroduce either.

## The Central Issue: Development Charges
On May 21, 2026, Regional Council passed DC Bylaw No. 2026-20, cutting DC rates for the first time in York Region's 55-year history (~$1.4B fiscal pressure; provincially forced via Bill 17). **YR Finance perspective = "growth pays for growth"**: DCs must fund the infrastructure new development requires; downloading those costs to the property tax levy is fiscally irresponsible.

## Fiscal Alignment Scoring (0–10, higher = more aligned with YR Finance)
**Scope (owner decision, 2026-07-07): scores apply only to sitting members of Regional Council** — the 21 elected incumbents plus appointed Chair Eric Jolliffe, who votes (candidate record `status: "appointed"`, id `york-region-chair-eric-jolliffe`; joined Dec 2024, so pre-appointment votes belong to former Chair Emmerson, who is not scored). Challengers have no council voting record and stay `unscored`.

Priority order of signal, recorded in each candidate's `fiscal_alignment_basis`:
1. **`voting_record`** — recorded votes in `data/votes.json` dominate. **Weighted-average model** (2026-07-07): each vote contributes sign × weight (contested fiscal votes weight 3; consensus fiscal votes like budget adoptions and staff-recommended reserve motions weight 1), normalized by total weight voted on, mapped onto 0–10 around neutral 5. Consensus votes lend baseline alignment credit so the scale grades rather than saturates — e.g. Del Duca (against the majority on every DC question, but supported both budgets) lands at 2/10, not 0. News keywords remain a minor secondary nudge
2. **`news_inferred`** — keyword deltas from news mentions (aligned: "growth pays for growth", "infrastructure funding", oppose DC cuts; misaligned: "cut development charges", "eliminate development charges", DC-framed affordability)
3. **`incumbency_default`** — no signal at all: incumbents get −1 (tacit association with DC Bylaw 2026-20), stated plainly in `fiscal_notes`
4. **`unscored`** — challengers with no signal stay neutral 5

Labels: 8–10 strongly_aligned, 6–7 aligned, 4–5 neutral, 2–3 misaligned, 0–1 strongly_misaligned.

**`votes.json` holds 4 recorded votes transcribed from official minutes (2026-07-06 harvest of all 2025–mid-2026 Regional Council + Committee of the Whole meetings — 37 meetings scanned, 10 recorded votes found, 4 fiscally scoreable).** All 21 incumbents now have a voting-record fiscal score:
1. **2025-04-03** (Special Meeting): immediate DC deferrals for all residential — carried 12–8 (yes = misaligned)
2. **2025-06-26**: overrule Chair to allow extending DC deferrals — defeated 8–11 (yes = misaligned)
3. **2025-09-25**: demand full provincial reimbursement of ASE cancellation costs — carried 17–1 (yes = aligned; opposing provincial downloading)
4. **2026-05-21**: cap DC rates at prevailing rate at occupancy — defeated 4–13 (yes = misaligned). The DC Bylaw 2026-20 passage itself carried **without** a recorded vote — no per-member breakdown exists for it.

Deliberately excluded: reconsideration/deferral-of-consideration procedural votes (members voted "reconsider" with opposite intents — direction not attributable), the unanimous Nov 2025 budget vote (no discriminating signal, declared conflicts), and the Vaughan forestry download (governance, not fiscal). To harvest future recorded votes: POST `{'calendarStartDate':...,'calendarEndDate':...}` to `/MeetingsCalendarView.aspx/GetCalendarMeetings` for meeting GUIDs, then grep the `Agenda=PostMinutes` page text for "recorded vote".

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

## Scrape Coverage (verified 2026-07-06)
| Municipality | Status | Notes |
|---|---|---|
| Georgina, Richmond Hill, Newmarket, Aurora, East Gwillimbury, King | ✅ live | Real clerk pages, per-municipality extractors tested against snapshots |
| Whitchurch-Stouffville | ✅ live | Data IS in static HTML (earlier "JS-rendered" diagnosis was wrong — the site's malformed markup broke the first parser). Pod-div structure, no filing dates published → registration_date stays null |
| Markham | 🕐 archive-delayed | Live site bot-blocks (Reblaze, HTTP 247) including archive.org's on-demand crawler — but regular Wayback crawls get through. Scraper fetches the newest *verified-content* snapshot via the CDX API (`filter=statuscode:200`, content-checked — the newest raw snapshot may be a captured challenge page) and pings Save Page Now for freshness. Data lags by days-to-weeks; snapshot date is visible in filing_source |
| Vaughan | ❌ no automated path | 403 to every non-browser client tried (browser UAs, server-side fetchers, and the Wayback crawler are all blocked). Needs manual checks; the Vaughan tab shows a registration-news review queue (gleaned from the news feed by candidacy phrases) to prompt them. Vaughan Chamber of Commerce's candidate page is stale (still 2022) — don't use it |

Scraper safeguards (do not remove): office allowlist, municipality allowlist, per-municipality candidate cap, page-must-mention-candidates check, no generic list-extraction fallback. King's extractor maps tables to offices **by position** (page has no per-office headings) — re-verify if King results look wrong.

## Known Gaps / Future Work
- `votes.json` is empty pending the DC Bylaw roll-call research (see Open manual item above)
- Vaughan filings need manual entry (weekly through July, twice-weekly in August; nom close Aug 21) — the Vaughan tab's news queue helps spot them
- Markham data lags by the age of the newest good Wayback snapshot — check the snapshot date in filing_source when precision matters
- No public polling exists for these races; likely-to-win stays a low-confidence ordinal
- Chamber view seat placement is illustrative (grouped by municipality); actual chair assignments aren't published — owner may supply the real order

## Current Incumbents (2022 elected; filing status tracked live in candidates.json)
Mayors: Mrakas (Aurora), Hackson (East Gwillimbury), Quirk (Georgina), Pellegrini (King), Scarpitti (Markham), Taylor (Newmarket), West (Richmond Hill), Del Duca (Vaughan), Lovatt (Whitchurch-Stouffville). Full 76-incumbent roster lives in `data/seats.json`.
