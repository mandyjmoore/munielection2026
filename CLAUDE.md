# York Region 2026 Municipal Election Dashboard

## What This Is
An automated election intelligence dashboard for the York Region 2026 municipal elections (October 26, 2026). Built for the York Region Finance Department (its analysts) because the makeup of the incoming Council directly affects the Region's budget, fiscal strategy, and Development Charges policy.

**Owner:** [maintainer]
**Repo:** mandyjmoore/munielection2026
**Live URL:** https://yrmuni2026.wordi.ca (custom domain on the owner's wordi.ca; the old https://mandyjmoore.github.io/munielection2026 now 301-redirects here. Domain is pinned by the root `CNAME` file + the Pages API)
**Local clone:** iCloud Drive `Projects/York Region Municipal Election Dashboard` (keep local + GitHub in sync — standing rule)

## The Three Core Requirements (in priority order)
1. **Candidate registration detection is the main function.** The owner's words: "Otherwise I'd just build an Excel file and update it myself." The scraper pulls each municipal clerk's official registered-candidates page every 2 hours. New filings must be visible at a glance.
2. **Lame-duck status at a glance.** Under Municipal Act s.275, York Regional Council becomes "lame duck" (restricted from major decisions: senior staff changes, $50k+ unbudgeted spending, asset sales) if fewer than 3/4 of its members continue to the new council. **Council has 22 voting members** (9 Mayors + 12 Regional Councillors + the appointed Chair): 3/4 of 22 = 16.5 → **17 required** (owner decision 2026-07-07 — straight ceiling math; an earlier "Chair continues automatically so 16 suffices" framing was overruled). The Chair cannot file, so the 17 must come from the 21 elected members, by nomination day (**Aug 21, 2026, 2 p.m.**). The banner displays filings out of 22 with the percentage.
3. **Fiscal alignment weighted toward actual voting record** (DCs and reserves especially), not just news keywords — see Scoring below.

## Design Philosophy (learned the hard way)
Distinguish visibly between **confirmed** (official clerk filing, documented recorded vote), **inferred** (news keywords, incumbency heuristics), and **unknown**. Never let absence of data become a plausible-looking fabricated value. Predecessor failure: a generic scraper fallback once recorded 330 nav-menu links ("Report A Problem", "Food Safety") as candidates. All estimates (likely-to-run-again, likely-to-win) are ordinal labels with visible `basis` reasons and dashed-border styling — never percentages, never solid badges.

**Visual style (owner rule, 2026-07-14): light mode only, Apple sensibility** — #f5f5f7 canvas, white cards, hairline borders, near-black text, Apple-blue #0071e3 accent, SF system font, text-safe muted status colors on light tinted fills, frosted sticky header. "Think Apple, not video games and PCs." Don't reintroduce dark backgrounds or neon accents.

## Zero Manual Updates (with honest exceptions)
GitHub Action scrapes every 2 hours and commits; dashboard auto-refreshes every 30 minutes. Exceptions that are deliberately manual:
- `data/votes.json` — hand-curated scored votes (each fiscally classified with direction + weight; `match_snippet` links it to its motion in the voting record)
- `data/voting_record.json` — the full motion-level record of this council since the Nov 2022 inauguration (449 motions, 47 meetings, all 23 recorded votes with member breakdowns; routine procedural motions excluded per owner rule; `staff_recommended` inferred from motion structure). Refresh after new meetings with `python3 scraper/harvest_voting_record.py` (run manually — not part of the 2-hour pipeline), then review any NEW recorded votes for scoring candidacy and add fiscally relevant ones to `votes.json`
- `data/manual_overrides.json` — human-verified facts for what scrapers can't reach (primarily **Vaughan** filings). Applied by main.py after every fetch, so they always win. Each entry needs provenance (verified_by / verified_on / source). Lesson from the Del Duca miss (showed "Not registered" for two months after he filed May 1): the news feed can't backfill events older than its collection start, so Vaughan corrections MUST come through this file when the owner checks vaughan.ca/council/elections/candidates

## Jurisdiction & Seats
York Region, Ontario — 9 lower-tier municipalities: Aurora, East Gwillimbury, Georgina, King, Markham, Newmarket, Richmond Hill, Vaughan, Whitchurch-Stouffville. **Regional Chair is provincially appointed** (Eric Jolliffe) — not on the ballot.

**21 seats total** in `data/seats.json`: 9 Mayors + 12 Regional Councillors (Markham 4, Vaughan 4, Richmond Hill 2, Georgina 1, Newmarket 1 — elected at-large). In the 6 municipalities without a separate regional seat, the Mayor is the sole regional representative. School board trustees are not tracked.

**Scope (owner decision, final form 2026-07-06): Regional Council races ONLY — data and display.** Ward councillor candidates are not collected, stored, or shown anywhere (the scraper's `VALID_OFFICES` rejects them at extraction). This also removed the per-municipality lame-duck calculation (it needed local rosters); only the Regional Council s.275 math remains (22 voting members / 17 threshold, see requirement 2). An earlier iteration kept ward data for that municipal math — both were removed together at the owner's direction, so don't reintroduce either.

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

**`votes.json` holds 7 scored votes** (6 with member results + the DC Bylaw 2026-20 passage recorded as `carried_no_recorded_vote` with empty results — no per-member breakdown exists for the bylaw itself). Transcribed from official minutes; all 22 sitting members have voting-record scores:
1. **2023-02-23** Pandemic/Recovery Reserve Fund restructuring — carried 22–0 (yes = aligned, **weight 1** consensus)
2. **2024-11-28** 2025–2026 Regional Budget main adoption — carried 21–0 (yes = aligned, **weight 1** consensus; the police/health conflict carve-out votes from the same item are deliberately not scored separately)
3. **2025-04-03** immediate DC deferrals for all residential — carried 12–8 (yes = misaligned, weight 3)
4. **2025-06-26** overrule Chair to allow extending DC deferrals — defeated 8–11 (yes = misaligned, weight 3)
5. **2025-09-25** demand full provincial reimbursement of ASE cancellation costs — carried 17–1 (yes = aligned, weight 3)
6. **2026-05-21** cap DC rates at prevailing rate at occupancy — defeated 4–13 (yes = misaligned, weight 3)

Deliberately excluded, with reasons: reconsideration/deferral-of-consideration procedural votes (members voted "reconsider" with opposite intents — direction not attributable); the Nov 2025 roll call (it was Del Duca's $25M medical-school amendment, direction ambiguous — the 2026 budget itself passed by voice, unattributable; an earlier mistranscription of this as "budget adoption" was caught and corrected); the asylum-seekers vote (social policy, direction contestable both ways); the Vaughan forestry download and Milani/OLT votes (not fiscal). Each scored vote carries a `match_snippet` linking it to its motion in `voting_record.json`, which powers the ⚖ scored badges and the member vote-history modals.

## Architecture
```
index.html                          # Single-file dashboard, no build step, pure vanilla JS (zero external JS deps)
data/seats.json                     # 21-seat regional inventory (manual seed, static) — everything joins on seat_id
data/candidates.json                # Auto-updated: 22 sitting members (incl. appointed Chair) + scraped challengers
data/council_status.json            # Computed lame-duck math (Regional Council only; 17-of-22 threshold)
data/votes.json                     # Hand-curated SCORED votes (direction + weight + match_snippet)
data/voting_record.json             # Full motion-level record since Nov 2022 (manual refresh, see above)
data/manual_overrides.json          # Owner-verified facts (Vaughan filings) — always win, applied every run
data/news.json                      # Google News RSS, 90-day retention
data/metadata.json                  # Timestamps, counts, data_confidence + scrape_coverage
scraper/main.py                     # Orchestrator (news → candidates → overrides → score → outlook → council status)
scraper/fetch_candidates.py         # Per-municipality extractors, verified against real clerk pages
scraper/fetch_news.py               # RSS feeds; word-boundary municipality matching; York-Region-relevance filter
scraper/score_alignment.py          # Weighted-average voting-record scoring (sitting members only)
scraper/compute_council_status.py   # s.275 lame-duck calculator (22 voting members / 17 threshold, asserted)
scraper/estimate_race_outlook.py    # likely_to_run_again / likely_to_win ordinal heuristics
scraper/harvest_voting_record.py    # Manual-run minutes harvester → data/voting_record.json
.github/workflows/update_data.yml   # Cron every 2 hours
.github/workflows/pages.yml         # Pages deploy on push to index.html or data/**
```

**Page layout (top to bottom):** lame-duck banner (16/22 fraction + % + the two countdown tiles) → Council Chamber grid (one colour-dotted block per municipality, Vaughan/Markham dominant, Chair beside Whitchurch-Stouffville on the last row; tiles carry filing status, win outlook, fiscal score) → Fiscal Alignment Overview (stacked bar + name columns; **clicking a name opens that member's full recorded-vote history modal**) → Council Voting Record (collapsible per-meeting motion record with recorded-vote breakdowns and ⚖ scored badges) → Recent Candidate Registrations.

## Scrape Coverage (verified 2026-07-06)
| Municipality | Status | Notes |
|---|---|---|
| Georgina, Richmond Hill, Newmarket, Aurora, East Gwillimbury, King | ✅ live | Real clerk pages, per-municipality extractors tested against snapshots |
| Whitchurch-Stouffville | ✅ live | Data IS in static HTML (earlier "JS-rendered" diagnosis was wrong — the site's malformed markup broke the first parser). Pod-div structure, no filing dates published → registration_date stays null |
| Markham | 🕐 archive-delayed | Live site bot-blocks (Reblaze, HTTP 247) including archive.org's on-demand crawler — but regular Wayback crawls get through. Scraper fetches the newest *verified-content* snapshot via the CDX API (`filter=statuscode:200`, content-checked — the newest raw snapshot may be a captured challenge page) and pings Save Page Now for freshness. Data lags by days-to-weeks; snapshot date is visible in filing_source |
| Vaughan | ❌ no automated path | 403 to every non-browser client tried (browser UAs, server-side fetchers, and the Wayback crawler are all blocked). Needs manual checks; the Vaughan tab shows a registration-news review queue (gleaned from the news feed by candidacy phrases) to prompt them. Vaughan Chamber of Commerce's candidate page is stale (still 2022) — don't use it |

Scraper safeguards (do not remove): office allowlist, municipality allowlist, per-municipality candidate cap, page-must-mention-candidates check, no generic list-extraction fallback. King's extractor maps tables to offices **by position** (page has no per-office headings) — re-verify if King results look wrong.

## Known Gaps / Future Work
- **Vaughan filings are checked by a scheduled local Claude task** (`vaughan-candidate-check`, Mon+Thu 9 a.m., in `~/.claude/scheduled-tasks/`): it reads the official list through the Claude-in-Chrome extension (the only client Vaughan's WAF lets through — via the elections *landing* page, whose #tab-1 embeds the candidate list; the /candidates URL 403s even in a browser tab) and writes changes through `data/manual_overrides.json` (which supports `new_candidate: true` inserts). Requires the desktop app + Chrome open on the owner's Mac; on failure it notifies rather than guessing. The Vaughan tab's candidacy-news queue remains as a backstop.
- **Markham data lags** by the age of the newest good Wayback snapshot — check the snapshot date in `filing_source` when precision matters. Its RC incumbents Scarpitti/M. Chan showing "Not registered" may just be snapshot lag.
- **Refresh the voting record after each new council meeting**: `python3 scraper/harvest_voting_record.py`, then review new recorded votes and add fiscally relevant ones to `votes.json`.
- No public polling exists; likely-to-win stays a low-confidence ordinal.
- **Chamber seat layout is illustrative** (blocks grouped by municipality, sized by contingent). Owner planned to walk to chambers for the real chair map — when supplied, it drops into `CHAMBER_MUNI_ORDER`/`MUNI_COLORS` in index.html (block-based now, not the old horseshoe).

## Current Status (2026-07-07)
16 of 22 registered (73%), **at risk** — needs 17. Five outstanding: Scarpitti + M. Chan (Markham, likely snapshot lag), Hackson (East Gwillimbury), Taylor + Vegh (Newmarket, scraped live so genuinely not yet filed). Full 21-incumbent roster + Chair in `data/seats.json`/`candidates.json`; filing status tracked live.

## Working notes for the next session
- **Every push waits on a flaky GitHub Pages deploy API** — it fails transiently ~1 in 3 times with "Deployment failed, try again later" (not our content). Standard move: `gh run rerun <id>` up to 3× until it goes green. GitHub status is otherwise operational.
- The **auto-update bot commits every ~2 hours**, so `git push` often rejects → `git pull --rebase`, then on data-file conflicts `git checkout --theirs data/*.json` (bot data is fresher for news; our schema-carrying commits win on structure — validate JSON after) and `git rebase --continue`.
- Git commits use an auto-detected local identity (`YR Dashboard <dashboard@...local>`), not the gmail — cosmetic, GitHub attributes via login. Owner can `git config --global user.email` if she wants it fixed.
- See owner memory `feedback_recompute_consequences.md`: when she corrects a computation input, recompute + surface ALL downstream effects (incl. unfavorable) before shipping.
