"""
One per-candidate race field:

  likely_to_run_again — for incumbents who haven't yet confirmed a filing.
     An ordinal label with a visible `basis` array of plain-language reasons,
     never a percentage. The only label that actually drives a display tier
     ("likely") comes exclusively from a dated editorial override in
     manual_overrides.json; the news path can confirm a retirement
     announcement but never manufactures a "likely".
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


def estimate_all(
    candidates: list[dict],
    news_articles: list[dict],
    as_of: str,
    nomination_day_passed: bool = False,
) -> list[dict]:
    """Attach likely_to_run_again.

    No race outcome is produced — not a win estimate, and not acclamation
    either. The audience for this dashboard reads a seat with no registered
    challengers correctly without being told what it means. Values carried
    over from earlier runs are dropped here so they can't linger in
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
            new_candidate.pop("acclaimed", None)
            updated.append(new_candidate)
        except Exception as exc:
            logger.error("Error estimating outlook for %s: %s", candidate.get("name"), exc)
            updated.append(candidate)
    return updated
