# York Region 2026 Municipal Election Dashboard

## What This Is
An automated election intelligence dashboard for the York Region 2026 municipal elections (October 26, 2026). Built for a York Region Finance Department audience, because the makeup of the incoming Council directly affects the Region's budget, fiscal strategy, and Development Charges policy.

**Repo:** mandyjmoore/munielection2026
**Live URL:** https://yrmuni2026.wordi.ca (custom domain on wordi.ca; the old https://mandyjmoore.github.io/munielection2026 now 301-redirects here. Domain is pinned by the root `CNAME` file + the Pages API)
**Local clone:** iCloud Drive `Projects/York Region Municipal Election Dashboard` (keep local + GitHub in sync — standing rule)

## Public-Repo Policy (2026-07-22 — binding)
Everything committed here is public: the repo, the Pages site, and every `data/*.json` file it serves. Therefore:
- **No personal names, personal email addresses, or personally attributed judgments** anywhere in tracked files — including commit messages and commit author identities. Repo-local git identity is set to `YR Dashboard <dashboard@yrmuni2026.wordi.ca>` — don't commit with a personal identity.
- **Editorial assessments** (e.g. `likely_to_run_again_override`) are recorded de-attributed: `source: "editorial"`, dated basis strings, no reasoning that identifies who assessed or how they know. The display treats them as an editorial tier; the private reasoning stays out of the repo.
- **Candidate research, motive analysis, and qualitative reads on named people live ONLY in `research/`** (git-ignored). Never commit, never surface on the dashboard, never hint at in tracked files. See `research/private-notes.md` (local only) for the private context behind public editorial entries.
- **The feedback form endpoint must be a FormSubmit privacy alias, never a raw email address.**
- Git history was rewritten 2026-07-22 (sensitive strings replaced, `data/chair_outlook.json` purged, author identities remapped) — old commit SHAs in notes/issues predating this are invalid; don't reference them.

## The Three Core Requirements (in priority order)
1. **Candidate registration detection is the main function.** The maintainer's words: "Otherwise I'd just build an Excel file and update it myself." The scraper pulls each municipal clerk's official registered-candidates page every 2 hours. New filings must be visible at a glance.
2. **Lame-duck status at a glance.** Under Municipal Act s.275, York Regional Council becomes "lame duck" (restricted from major decisions: senior staff changes, $50k+ unbudgeted spending, asset sales) if fewer than 3/4 of its members continue to the new council. **Council has 22 voting members** (9 Mayors + 12 Regional Councillors + the appointed Chair): 3/4 of 22 = 16.5 → **17 required** (maintainer decision 2026-07-07 — straight ceiling math; an earlier "Chair continues automatically so 16 suffices" framing was overruled). The Chair cannot file, so the 17 must come from the 21 elected members, by nomination day (**Aug 21, 2026, 2 p.m.**). The banner displays filings out of 22 with the percentage.
3. **Fiscal alignment weighted toward actual voting record** (DCs and reserves especially), not just news keywords — see Scoring below.

## Design Philosophy (learned the hard way)
Distinguish visibly between **confirmed** (official clerk filing, documented recorded vote), **inferred** (news keywords, incumbency heuristics), and **unknown**. Never let absence of data become a plausible-looking fabricated value. Predecessor failure: a generic scraper fallback once recorded 330 nav-menu links ("Report A Problem", "Food Safety") as candidates. All estimates (likely-to-run-again, likely-to-win) are ordinal labels with visible `basis` reasons and dashed-border styling — never percentages, never solid badges.

**Visual style (maintainer rule, 2026-07-14): light mode only, Apple sensibility** — #f5f5f7 canvas, white cards, hairline borders, near-black text, Apple-blue #0071e3 accent, SF system font, text-safe muted status colors on light tinted fills, frosted sticky header. "Think Apple, not video games and PCs." Don't reintroduce dark backgrounds or neon accents.

## Zero Manual Updates (with honest exceptions)
GitHub Action scrapes every 2 hours and commits; dashboard auto-refreshes every 30 minutes. Exceptions that are deliberately manual:
- `data/votes.json` — hand-curated scored votes (each fiscally classified with direction + weight; `match_snippet` links it to its motion in the voting record)
- `data/voting_record.json` — the full motion-level record of this council since the Nov 2022 inauguration (449 motions, 47 meetings, all 23 recorded votes with member breakdowns; routine procedural motions excluded per standing rule; `staff_recommended` inferred from motion structure). Refresh after new meetings with `python3 scraper/harvest_voting_record.py` (run manually — not part of the 2-hour pipeline), then review any NEW recorded votes for scoring candidacy and add fiscally relevant ones to `votes.json`
- `data/manual_overrides.json` — human-verified facts for what scrapers can't reach (primarily **Vaughan** filings) AND editorial assessments: a `likely_to_run_again_override` field ({label, basis, confidence, source:"editorial"}) beats the news heuristic in estimate_race_outlook.py and feeds the Post-Election Outlook's light-green "Aligned · likely to run" tier (Scarpitti/Taylor set likely, 2026-07-21). Applied by main.py after every fetch, so they always win. Each entry needs provenance (verified_by / verified_on / source) — worded neutrally, per the public-repo policy. Lesson from the Del Duca miss (showed "Not registered" for two months after he filed May 1): the news feed can't backfill events older than its collection start, so Vaughan corrections MUST come through this file when the maintainer checks vaughan.ca/council/elections/candidates

## Jurisdiction & Seats
York Region, Ontario — 9 lower-tier municipalities: Aurora, East Gwillimbury, Georgina, King, Markham, Newmarket, Richmond Hill, Vaughan, Whitchurch-Stouffville. **Regional Chair is provincially appointed** (Eric Jolliffe) — not on the ballot.

**21 seats total** in `data/seats.json`: 9 Mayors + 12 Regional Councillors (Markham 4, Vaughan 4, Richmond Hill 2, Georgina 1, Newmarket 1 — elected at-large). In the 6 municipalities without a separate regional seat, the Mayor is the sole regional representative. School board trustees are not tracked.

**Scope (maintainer decision, final form 2026-07-06): Regional Council races ONLY — data and display.** Ward councillor candidates are not collected, stored, or shown anywhere (the scraper's `VALID_OFFICES` rejects them at extraction). This also removed the per-municipality lame-duck calculation (it needed local rosters); only the Regional Council s.275 math remains (22 voting members / 17 threshold, see requirement 2). An earlier iteration kept ward data for that municipal math — both were removed together at the maintainer's direction, so don't reintroduce either.

## The Central Issue: Development Charges
On May 21, 2026, Regional Council passed DC Bylaw No. 2026-20, cutting DC rates for the first time in York Region's 55-year history (~$1.4B fiscal pressure; provincially forced via Bill 17). **YR Finance perspective = "growth pays for growth"**: DCs must fund the infrastructure new development requires; downloading those costs to the property tax levy is fiscally irresponsible.

## Fiscal Alignment Scoring (0–10, higher = more aligned with YR Finance)
**Scope (maintainer decision, 2026-07-07): scores apply only to sitting members of Regional Council** — the 21 elected incumbents plus appointed Chair Eric Jolliffe, who votes (candidate record `status: "appointed"`, id `york-region-chair-eric-jolliffe`; joined Dec 2024, so pre-appointment votes belong to former Chair Emmerson, who is not scored). Challengers have no council voting record and stay `unscored`.

Priority order of signal, recorded in each candidate's `fiscal_alignment_basis`:
1. **`voting_record`** — recorded votes in `data/votes.json` dominate. **Weighted-average model** (2026-07-07): each vote contributes sign × weight (contested fiscal votes weight 3; consensus fiscal votes like budget adoptions and staff-recommended reserve motions weight 1), normalized by total weight voted on, mapped onto 0–10 around neutral 5. Consensus votes lend baseline alignment credit so the scale grades rather than saturates — e.g. Del Duca (against the majority on every DC question, but supported both budgets) lands at 2/10, not 0. News keywords remain a minor secondary nudge
2. **`news_inferred`** — keyword deltas from news mentions (aligned: "growth pays for growth", "infrastructure funding", oppose DC cuts; misaligned: "cut development charges", "eliminate development charges", DC-framed affordability)
3. **`incumbency_default`** — no signal at all: incumbents get −1 (tacit association with DC Bylaw 2026-20), stated plainly in `fiscal_notes`
4. **`unscored`** — challengers with no signal stay neutral 5

Labels: 8–10 strongly_aligned, 6–7 aligned, 4–5 neutral, 2–3 misaligned, 0–1 strongly_misaligned.

**Thin-record guard + participation transparency (maintainer decisions 2026-07-22, from the participation audit):** every voting-record fiscal_notes states contested-vote participation ("X of 12 weight — did not vote on: …"), and a member who voted <75% of contested weight cannot earn a non-neutral label when their contested votes alone read neutral — consensus credit (the two w1 unanimous votes) must not manufacture a lean (Jackson: contested record exactly split 1-1, absent for ASE + the 2026 DC-rate cap, was 6/aligned on consensus padding → now 5/neutral with the withholding stated). The guard deliberately does NOT touch members whose contested votes have uniform direction (Ferri 2/misaligned and Hackson 10/strongly_aligned keep their labels on the same 6/12 participation). Known limits: rhetoric is unscored by design; the excluded June 2025 reconsideration pair + OLT/planning votes are outside the scored set — qualitative reads on individuals belong in the editorial-assessment channel (once the challenger-alignment mechanism is built), not in tracked files.

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
data/manual_overrides.json          # Human-verified facts (Vaughan filings) — always win, applied every run
data/news.json                      # Google News RSS, 90-day retention
data/metadata.json                  # Timestamps, counts, data_confidence + scrape_coverage
scraper/main.py                     # Orchestrator (news → candidates → overrides → score → outlook → council status)
scraper/fetch_candidates.py         # Per-municipality extractors, verified against real clerk pages
scraper/fetch_news.py               # RSS feeds; word-boundary municipality matching; York-Region-relevance filter
scraper/score_alignment.py          # Weighted-average voting-record scoring (sitting members only)
scraper/compute_council_status.py   # s.275 lame-duck calculator (22 voting members / 17 threshold, asserted)
scraper/estimate_race_outlook.py    # likely_to_run_again / likely_to_win ordinal heuristics
scraper/harvest_voting_record.py    # Manual-run minutes harvester → data/voting_record.json
research/                           # GIT-IGNORED local research — never commit (see Public-Repo Policy)
.github/workflows/update_data.yml   # Cron every 2 hours
.github/workflows/pages.yml         # Pages deploy on push to index.html or data/**
```

**Page layout (top to bottom):** lame-duck banner (16/22 fraction + % + the two countdown tiles) → **Post-Election Outlook** (computed client-side in `renderOutlook()`: per-seat projection from filings × ordinal win estimates — filed incumbent favored/acclaimed = likely, competitive = lean, everything else honestly grey "uncertain" incl. the appointed Chair — the 2026-30 Chair appointee is listed as an uncertain seat only; a speculative chair-appointment analysis card was built 2026-07-14 and REMOVED at the maintainer's direction 2026-07-16: the dashboard's audience knows far more about the appointment than public sources can surface, so don't reintroduce public-info chair speculation. Rendered as the SAME stacked-bar + name-columns pattern as the Current Council section so the two read as siblings — each projected member listed under their bucket, uncertainty reasons in parentheses ("has not filed", "competitive race", Chair "appointee not yet named"), names click through to the vote-history modal; the method lives in the tooltip on the "estimates, not predictions" badge, not in on-page prose) → Council Chamber grid (one colour-dotted block per municipality, Vaughan/Markham dominant, Chair beside Whitchurch-Stouffville on the last row; tiles carry filing status, win outlook, fiscal score) → Current Council — Fiscal Alignment (stacked bar + name columns; **clicking a name opens that member's full recorded-vote history modal**) → Council Voting Record (whole section collapsed by default behind an arrow toggle in its title — maintainer call 2026-07-22; per-meeting entries inside are their own collapsibles). A Recent Candidate Registrations section existed and was REMOVED at the maintainer's direction 2026-07-22 ("doesn't add enough to take up that much space") — don't reintroduce; the alert banner + tile filing statuses carry new-filing visibility. **Print button** in the header (2026-07-22): **landscape, each of the three main sections zoom-scaled to fit exactly one page** (status banner + Outlook / Seat Races / Current Council alignment; voting record never prints). Mechanism: JS adds `body.printing` (print-layout rules live on that class, NOT inside `@media print`, so the on-screen measurement pass is honest), measures each section with getBoundingClientRect, and sets inline `zoom` + compensating width (zoom participates in layout, so page breaks track the scaled size; page 1's budget subtracts header+banner heights); `beforeprint`/`afterprint` handle Cmd+P and cleanup. Name columns fall back to flowing layout (the stagger-pack px layout is screen-width-specific).

## Scrape Coverage (verified 2026-07-06)
| Municipality | Status | Notes |
|---|---|---|
| Georgina, Richmond Hill, Newmarket, Aurora, East Gwillimbury, King | ✅ live | Real clerk pages, per-municipality extractors tested against snapshots |
| Whitchurch-Stouffville | ✅ live | Data IS in static HTML (earlier "JS-rendered" diagnosis was wrong — the site's malformed markup broke the first parser). Pod-div structure, no filing dates published → registration_date stays null |
| Markham | 🕐 archive-delayed | Live site bot-blocks (Reblaze, HTTP 247) including archive.org's on-demand crawler — but regular Wayback crawls get through. Scraper fetches the newest *verified-content* snapshot via the CDX API (`filter=statuscode:200`, content-checked — the newest raw snapshot may be a captured challenge page) and pings Save Page Now for freshness. Data lags by days-to-weeks; snapshot date is visible in filing_source |
| Vaughan | ❌ no server-side path (local browser task instead) | 403 to every non-browser client tried (browser UAs, server-side fetchers, the Wayback crawler) AND — probed 2026-07-14 — to real headless Chromium from GitHub CI: the WAF blocks datacenter IPs outright, so no CI path exists without evasion tactics we won't use. Coverage comes from the `vaughan-candidate-check` scheduled local task (see Known Gaps). The Vaughan tab's registration-news queue is the backstop. Vaughan Chamber of Commerce's candidate page is stale (still 2022) — don't use it |

Scraper safeguards (do not remove): office allowlist, municipality allowlist, per-municipality candidate cap, page-must-mention-candidates check, no generic list-extraction fallback. King's extractor maps tables to offices **by position** (page has no per-office headings) — re-verify if King results look wrong.

## Known Gaps / Future Work
- **Vaughan filings are checked by a scheduled local Claude task** (`vaughan-candidate-check`, every 2h Mon–Fri 8:30–18:30 — filings can only occur in person at the clerk's office during business hours, so this is within-2h of any possible filing; in `~/.claude/scheduled-tasks/`): it reads the official list through the Claude-in-Chrome extension (the only client Vaughan's WAF lets through — via the elections *landing* page, whose #tab-1 embeds the candidate list; the /candidates URL 403s even in a browser tab) and writes changes through `data/manual_overrides.json` (which supports `new_candidate: true` inserts). Requires the desktop app + Chrome open on the maintainer's Mac; on failure it notifies rather than guessing. The Vaughan tab's candidacy-news queue remains as a backstop.
- **Markham data lags** by the age of the newest good Wayback snapshot — check the snapshot date in `filing_source` when precision matters. Its RC incumbents Scarpitti/M. Chan showing "Not registered" may just be snapshot lag.
- **Refresh the voting record after each new council meeting**: `python3 scraper/harvest_voting_record.py`, then review new recorded votes and add fiscally relevant ones to `votes.json`.
- No public polling exists; likely-to-win stays a low-confidence ordinal.
- **Chamber seat layout is illustrative** (blocks grouped by municipality, sized by contingent). If a verified chair map is supplied later, it drops into `CHAMBER_MUNI_ORDER`/`MUNI_COLORS` in index.html (block-based now, not the old horseshoe).

## Current Status (2026-07-22)
16 of 22 registered (73%), **at risk** — needs 17 by Aug 21 2 p.m. Five unfiled: Scarpitti + Taylor (assessed likely to run, source "editorial" → outlook's light-green tier); Hackson, Vegh + M. Chan (no recorded assessment). Markham's at-large field is 4-for-4 → Jones/Li/Ho/Kristian Chan all "favored — on track for acclamation" on tiles, **but the projection does NOT seat a challenger until actual acclamation** (correction 2026-07-22: the field can grow until Aug 21, so M. Chan's seat stays in Outcome unknown; K. Chan would claim it — as "Registered · alignment unscored" — only when the estimator says `acclaimed`, i.e. post-close. Challenger alignment assessments are backlog; the challenger-alignment override mechanism is NOT built yet, only `likely_to_run_again_override` exists). Outlook bar: 8/2/2/3/2/1 + 4 unknown (M. Chan, Hackson, Vegh, Chair) of 22. **Two benchmark dots ABOVE the bar** (2026-07-22 — maintainer correction: static points on the 0–22 scale, NOT dividers inside the stacked bar; a segment can span either point): a solid dot at the estimated-aligned count ("Estimated aligned: 12" — strongly aligned + aligned, registered or assessed likely to run; counted CONSERVATIVELY per maintainer decision 2026-07-22 — neutral is no measured lean, not a reliable vote) and a hollow dot at the fixed 68.18% target ("⅔: 15"); the gap note reads "3 seats short of the ⅔ benchmark — 15 of 22 seats". **The ⅔ marker carries NO tooltip and the page states NO rationale for the 15-seat benchmark anywhere** (maintainer decision 2026-07-22, superseding the earlier tooltip-only compromise) — it is presented as a plain fraction on the scale; don't reintroduce an explanation.

## The page's visual-semantics system (maintainer-driven, 2026-07-21 — keep it consistent)
- **Solid tinted word-chip** ("Aligned") = measured fiscal alignment (voting record). Never numbers/gauges on tiles (both tried, rejected); the 0–10 number lives in tooltips + the vote-history modal.
- **Dashed inline text** ("favored to win", "competitive race", "long shot", "acclaimed") = race estimates. Never chip-shaped — estimates must not carry the visual authority of measurements.
- **Outlook tiers**: solid alignment buckets ("· registered") → light-green "Aligned · likely to run" (editorial assessment) → dark-grey "Registered · alignment unscored" (acclamation-track challengers) → grey "Outcome unknown" (reason in parentheses; alignment chips shown where measured — only the Chair is chip-less).
- Bars use stagger-packed name columns centred under segments with colour-matched drop-lines (gaps where they cross other columns' top-lines); header swatches repeat segment fills; header text is dark (colour lives in swatch/underline only).
- Estimates-methodology lives in tooltips (the "estimates, not predictions" badge; the win-est texts), never on-page prose. No per-item text labels ("FISCAL" prefix tried, rejected as brute force).

## Working notes for the next session
- **Every push waits on a flaky GitHub Pages deploy API** — it fails transiently ~1 in 3 times with "Deployment failed, try again later" (not our content). Standard move: `gh run rerun <id>` up to 3× until it goes green. GitHub status is otherwise operational.
- The **auto-update bot commits every ~2 hours**, so `git push` often rejects → `git pull --rebase`, then on data-file conflicts `git checkout --theirs data/*.json` (bot data is fresher for news; our schema-carrying commits win on structure — validate JSON after) and `git rebase --continue`.
- Git identity: repo-local `YR Dashboard <dashboard@yrmuni2026.wordi.ca>` (set 2026-07-22 per the Public-Repo Policy — do not commit with a personal identity).
- Standing rule: when a computation input is corrected, recompute + surface ALL downstream effects (incl. unfavorable ones) before shipping — never rationalize numbers into agreement.
- **Verification loop that works (2026-07-21):** headless jsdom test against a Bash-launched local server for logic, then the "YR 2026 Election" Safari Dock web app for visuals (computer-use grant, full tier: Cmd+Alt+R to hard-reload past the ~10-min Pages HTML cache, screenshot, zoom). The review window is ~1450px — narrower than dev defaults; test layout at that width.
- **Feedback form** (header button) posts via FormSubmit (AJAX) using the **privacy alias** endpoint (re-enabled + test-verified 2026-07-22; the endpoint must never be a raw email address — see Public-Repo Policy. The alias is in the 2026-07-21 FormSubmit activation email's HTML body if ever needed again). **GoatCounter analytics** live (wordi.goatcounter.com, host-prefixed paths; "visits" = daily uniques).
- **Scheduled**: `vaughan-candidate-check` every 2h Mon–Fri business hours (needs desktop app + Chrome open). Standing backlog: editorial alignment assessments for challengers (K. Chan first) — blocked on building the challenger-alignment override mechanism.
