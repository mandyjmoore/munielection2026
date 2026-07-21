"""
Heuristic estimates for two questions the dashboard needs an "at a glance"
answer to, even though neither has a reliable ground-truth source for
Ontario municipal races (no public polling, no real-time fundraising
disclosure):

  1. likely_to_run_again — for incumbents who haven't yet confirmed a filing.
  2. likely_to_win — for any candidate, once a race has at least one filing.

Both are deliberately small ordinal labels with a visible `basis` array of
plain-language reasons, never a percentage or a normalized score — with only
1-2 real signals available per race (incumbency, news volume), a fake-precision
number would overstate what the data actually supports.
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


def _owner_run_override(candidate: dict, as_of: str) -> Optional[dict]:
    """Editorial assessments (set via manual_overrides.json as
    likely_to_run_again_override) beat the news heuristics — recorded assessments outrank headline keywords. Returned verbatim with a
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

    override = _owner_run_override(candidate, as_of)
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


def _at_large_acclamation(candidate, all_candidates, nomination_day_passed, as_of):
    """Multi-seat at-large arithmetic the news heuristic can't see: when the
    filed field is no larger than the number of seats, every filed candidate
    is (after nominations close) elected by acclamation under the Municipal
    Elections Act — no vote is held for the office. Before the close, the
    same arithmetic means everyone filed is on track for acclamation."""
    muni = candidate.get("municipality")
    office = candidate.get("office")
    incumbents = [
        c for c in all_candidates
        if c.get("status") == "incumbent"
        and c.get("municipality") == muni and c.get("office") == office
    ]
    seats_n = len(incumbents)  # every seat has a roster incumbent
    if seats_n < 2:
        return None
    filed_field = [
        c for c in all_candidates
        if c.get("municipality") == muni and c.get("office") == office
        and (c.get("status") == "incumbent" or c.get("at_large_pool"))
        and _is_filed(c)
    ]
    if len(filed_field) > seats_n:
        return None
    if nomination_day_passed:
        return {
            "label": "acclaimed",
            "basis": [f"Nominations closed with {len(filed_field)} candidates for {seats_n} at-large seats — every filed candidate is elected by acclamation (Municipal Elections Act)"],
            "confidence": "high",
            "as_of": as_of,
        }
    return {
        "label": "favored",
        "basis": [f"{len(filed_field)} candidates filed for {seats_n} at-large seats so far — on track for acclamation if the field holds to nomination day"],
        "confidence": "low",
        "as_of": as_of,
    }


def estimate_likely_to_win(
    candidate: dict,
    all_candidates: list[dict],
    news_articles: list[dict],
    nomination_day_passed: bool,
    as_of: str,
) -> dict:
    # At-large challengers compete against the incumbents across all of a
    # municipality's regional seats, not for one numbered slot, so the
    # single-seat heuristics below (and their "open seat — no incumbent"
    # branch) would misread them. Grade them on the same ordinal evidence a
    # single-seat challenger gets — news visibility against sitting
    # incumbents — with the multi-winner structure stated in the basis
    # (owner request 2026-07-14; supersedes the earlier "not modelled" stance).
    if candidate.get("at_large_pool"):
        acclaim = _at_large_acclamation(candidate, all_candidates, nomination_day_passed, as_of)
        if acclaim and _is_filed(candidate):
            return acclaim
        incumbents_in_pool = [
            c for c in all_candidates
            if c.get("status") == "incumbent"
            and c.get("municipality") == candidate.get("municipality")
            and c.get("office") == candidate.get("office")
        ]
        own_mentions = len(find_relevant_articles(candidate["name"], news_articles))
        race = f"At-large race — challenging {len(incumbents_in_pool)} incumbents for {len(incumbents_in_pool)} seats"
        if own_mentions >= 3:
            return {
                "label": "competitive",
                "basis": [race, f"{own_mentions} news mention(s) — meaningful visibility"],
                "confidence": "low",
                "as_of": as_of,
            }
        return {
            "label": "long_shot",
            "basis": [race, f"{own_mentions} news mention(s) — limited visibility"],
            "confidence": "low",
            "as_of": as_of,
        }

    seat_id = candidate.get("seat_id")
    seat_candidates = [c for c in all_candidates if c.get("seat_id") == seat_id]
    other_filed = [c for c in seat_candidates if c["id"] != candidate["id"] and _is_filed(c)]

    # A regional-councillor incumbent holds a numbered slot, but the race is
    # at-large: the municipality's at-large challenger pool (a separate pool
    # seat_id) is running against them too. Fold those challengers in so the
    # incumbent isn't wrongly reported as "acclaimed" or facing no challengers.
    if candidate.get("status") == "incumbent" and candidate.get("office") == "Regional Councillor":
        other_filed = other_filed + [
            c for c in all_candidates
            if c.get("at_large_pool")
            and c.get("municipality") == candidate.get("municipality")
            and c["id"] != candidate["id"]
            and _is_filed(c)
        ]
        # Field ≤ seats beats challenger-visibility grading: a filed at-large
        # incumbent in that situation is acclaimed (or on track to be).
        if _is_filed(candidate):
            acclaim = _at_large_acclamation(candidate, all_candidates, nomination_day_passed, as_of)
            if acclaim:
                return acclaim

    if not _is_filed(candidate) and not other_filed:
        return {
            "label": "insufficient_data",
            "basis": ["No filings recorded yet for this seat."],
            "confidence": "low",
            "as_of": as_of,
        }

    if nomination_day_passed and _is_filed(candidate) and not other_filed:
        return {
            "label": "acclaimed",
            "basis": ["No other candidates filed for this seat by nomination close."],
            "confidence": "medium",
            "as_of": as_of,
        }

    is_incumbent = candidate.get("status") == "incumbent"

    if is_incumbent and not _is_filed(candidate):
        # Don't call an incumbent "favored" to win a race they haven't
        # actually entered — that's a stronger claim than the data supports,
        # especially once challengers have already filed against the seat.
        return {
            "label": "insufficient_data",
            "basis": ["Incumbent has not yet filed for re-election" + (
                f" — {len(other_filed)} other candidate(s) already have" if other_filed else ""
            )],
            "confidence": "low",
            "as_of": as_of,
        }

    if is_incumbent:
        if not other_filed:
            return {
                "label": "favored",
                "basis": ["Incumbent", "No challengers filed yet"],
                "confidence": "low",
                "as_of": as_of,
            }
        challenger_mention_counts = [
            len(find_relevant_articles(c["name"], news_articles)) for c in other_filed
        ]
        max_mentions = max(challenger_mention_counts, default=0)
        if max_mentions >= 3:
            return {
                "label": "competitive",
                "basis": [
                    "Incumbent",
                    f"{len(other_filed)} challenger(s) filed",
                    f"Highest challenger news volume: {max_mentions} mention(s)",
                ],
                "confidence": "low",
                "as_of": as_of,
            }
        return {
            "label": "favored",
            "basis": [
                "Incumbent",
                f"{len(other_filed)} challenger(s) filed with limited news visibility (max {max_mentions} mention(s))",
            ],
            "confidence": "low",
            "as_of": as_of,
        }

    # Candidate is a challenger, or this is an open seat with no incumbent filed.
    incumbent_in_race = any(c.get("status") == "incumbent" for c in other_filed)
    if not incumbent_in_race:
        return {
            "label": "competitive",
            "basis": ["Open seat — no incumbent in the race", f"{len(seat_candidates)} candidate(s) filed"],
            "confidence": "low",
            "as_of": as_of,
        }

    own_mentions = len(find_relevant_articles(candidate["name"], news_articles))
    if own_mentions >= 3:
        return {
            "label": "competitive",
            "basis": ["Challenging an incumbent", f"{own_mentions} news mention(s) — meaningful visibility"],
            "confidence": "low",
            "as_of": as_of,
        }
    return {
        "label": "long_shot",
        "basis": ["Challenging an incumbent", f"{own_mentions} news mention(s) — limited visibility"],
        "confidence": "low",
        "as_of": as_of,
    }


def estimate_all(
    candidates: list[dict],
    news_articles: list[dict],
    as_of: str,
    nomination_day_passed: bool = False,
) -> list[dict]:
    """Attach likely_to_run_again and likely_to_win estimates to every candidate."""
    updated = []
    for candidate in candidates:
        try:
            new_candidate = dict(candidate)
            new_candidate["likely_to_run_again"] = estimate_likely_to_run_again(
                candidate, news_articles, as_of
            )
            new_candidate["likely_to_win"] = estimate_likely_to_win(
                candidate, candidates, news_articles, nomination_day_passed, as_of
            )
            updated.append(new_candidate)
        except Exception as exc:
            logger.error("Error estimating outlook for %s: %s", candidate.get("name"), exc)
            updated.append(candidate)
    return updated
