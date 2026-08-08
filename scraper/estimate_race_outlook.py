"""
Two per-candidate race fields:

  1. likely_to_run_again — for incumbents who haven't yet confirmed a filing.
     An ordinal label with a visible `basis` array of plain-language reasons,
     never a percentage. The only label that actually drives a display tier
     ("likely") comes exclusively from a dated editorial override in
     manual_overrides.json; the news path can confirm a retirement
     announcement but never manufactures a "likely".
  2. acclaimed — a plain boolean, and a FACT, not a forecast: nominations
     closed with no more candidates than seats, so the Municipal Elections
     Act elects the filed field without a vote.

**There is deliberately no win estimate.** `likely_to_win` (favored /
competitive / long shot / acclaimed-on-track) was REMOVED 2026-08-08 at the
maintainer's direction. Ontario municipal races have no public polling and no
real-time fundraising disclosure, so the only available signal was counting a
regional news feed for a candidate's name — which turned out to measure
nothing: substring collisions inflated the counts, and even once corrected,
no candidate in the region cleared the visibility bar, so the labels were
being set by structural defaults rather than evidence. The maintainer's own
read of these races is far better informed than those inputs can support, and
an unreliable estimate published beside confirmed filings and documented
voting records devalues both. Do not reintroduce one.
"""

import logging
from typing import Optional

from score_alignment import find_relevant_articles

logger = logging.getLogger(__name__)

# High-precision phrases only — false positives here directly mislabel an
# incumbent as retiring, so keep this list narrow rather than clever.
RETIREMENT_KEYWORDS = [
    "will not seek re-election",
    "will not seek reelection",
    "won't seek re-election",
    "won't seek reelection",
    "not seeking re-election",
    "not seeking reelection",
    "will not be seeking re-election",
    "won't run again",
    "will not run again",
    "announced retirement",
    "announced her retirement",
    "announced his retirement",
    "retiring from council",
    "retiring from politics",
    "stepping down",
]


def _assessment_override(candidate: dict, as_of: str) -> Optional[dict]:
    """Editorial overrides (set via manual_overrides.json as
    likely_to_run_again_override) beat the news heuristics — recorded
    assessments outrank headline keywords. Returned verbatim with a
    fresh as_of so the override survives every 2-hour re-estimate."""
    ov = candidate.get("likely_to_run_again_override")
    if not ov or not ov.get("label"):
        return None
    return {**ov, "as_of": as_of}


def estimate_likely_to_run_again(
    candidate: dict, news_articles: list[dict], as_of: str
) -> Optional[dict]:
    """Only meaningful for incumbents with no confirmed filing status yet."""
    if candidate.get("status") != "incumbent":
        return None
    if candidate.get("filed_for_reelection") in ("confirmed", "declined"):
        return None  # moot — a known filing status (either way) supersedes this estimate

    override = _assessment_override(candidate, as_of)
    if override:
        return override

    articles = find_relevant_articles(candidate["name"], news_articles)
    hits = []
    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        for phrase in RETIREMENT_KEYWORDS:
            if phrase in text:
                hits.append(article.get("title", phrase))
                break

    if hits:
        return {
            "label": "unlikely",
            "basis": [f'News signal: "{title}"' for title in hits[:3]],
            "confidence": "low",
            "as_of": as_of,
        }

    if not articles:
        return {
            "label": "insufficient_data",
            "basis": ["No news coverage found mentioning this candidate."],
            "confidence": "low",
            "as_of": as_of,
        }

    # Deliberately not defaulting to "likely" just because most incumbents
    # usually do run again — that's an unverified inference, same failure
    # mode as the original scraper's fabricated candidate data.
    return {
        "label": "uncertain",
        "basis": [
            "No retirement or non-candidacy announcement found in news",
            f"{len(articles)} news article(s) reviewed, none signaling non-candidacy",
        ],
        "confidence": "low",
        "as_of": as_of,
    }


def _is_filed(candidate: dict) -> bool:
    return bool(candidate.get("registered")) or candidate.get("filed_for_reelection") == "confirmed"


def _seat_is_acclaimed(candidate: dict, all_candidates: list[dict]) -> bool:
    """True when this filed candidate has already won under the Municipal
    Elections Act because nominations closed with no more candidates than
    seats. This is arithmetic on the certified field, not a forecast — it is
    the one race outcome the dashboard still reports, and only ever AFTER the
    nomination deadline (callers gate on that).

    Two shapes: a single-seat race with no other filed candidate, and a
    multi-seat at-large race whose whole filed field fits the seat count.
    """
    if not _is_filed(candidate):
        return False

    muni = candidate.get("municipality")
    office = candidate.get("office")
    incumbents = [
        c for c in all_candidates
        if c.get("status") == "incumbent"
        and c.get("municipality") == muni and c.get("office") == office
    ]
    seats_n = len(incumbents)  # every seat has a roster incumbent

    if seats_n >= 2:
        filed_field = [
            c for c in all_candidates
            if c.get("municipality") == muni and c.get("office") == office
            and (c.get("status") == "incumbent" or c.get("at_large_pool"))
            and _is_filed(c)
        ]
        return len(filed_field) <= seats_n

    seat_id = candidate.get("seat_id")
    others = [
        c for c in all_candidates
        if c.get("seat_id") == seat_id and c["id"] != candidate["id"] and _is_filed(c)
    ]
    return not others


def estimate_all(
    candidates: list[dict],
    news_articles: list[dict],
    as_of: str,
    nomination_day_passed: bool = False,
) -> list[dict]:
    """Attach likely_to_run_again and, once nominations close, `acclaimed`.

    `likely_to_win` is deliberately no longer produced, and any value carried
    over from an earlier run is dropped here so it can't linger in
    candidates.json and quietly keep feeding the page.
    """
    updated = []
    for candidate in candidates:
        try:
            new_candidate = dict(candidate)
            new_candidate.pop("likely_to_win", None)
            new_candidate["likely_to_run_again"] = estimate_likely_to_run_again(
                candidate, news_articles, as_of
            )
            new_candidate["acclaimed"] = bool(
                nomination_day_passed and _seat_is_acclaimed(candidate, candidates)
            )
            updated.append(new_candidate)
        except Exception as exc:
            logger.error("Error estimating outlook for %s: %s", candidate.get("name"), exc)
            updated.append(candidate)
    return updated
