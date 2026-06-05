"""
Fiscal alignment scorer for York Region 2026 Municipal Election.

Scores candidates 0-10 based on their alignment with the "growth pays for growth"
philosophy — i.e., maintaining DC rates to fund infrastructure vs. supporting
housing-affordability-driven DC reductions.

10 = fully aligned with YR Finance perspective (support full DC rates)
 0 = strongly misaligned (support DC cuts)
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Signals that increase the score (aligned with YR Finance / "growth pays for growth")
ALIGNED_SIGNALS = [
    ("growth pays for growth", 2),
    ("infrastructure funding", 1),
    ("development charges must reflect costs", 2),
    ("oppose provincial downloading", 2),
    ("restore dc rates", 2),
    ("restore development charge", 2),
    ("fiscal responsibility", 1),
    ("infrastructure first", 1),
    ("full cost recovery", 2),
    ("taxpayers should not subsidize", 1),
    ("municipalities should not subsidize", 1),
    ("dc revenue", 1),
    ("oppose dc reduction", 2),
    ("oppose development charge reduction", 2),
    ("infrastructure gap", 1),
    ("unfunded infrastructure", 1),
]

# Signals that decrease the score (misaligned — support DC cuts)
MISALIGNED_SIGNALS = [
    ("cut development charges", -2),
    ("reduce development charges", -2),
    ("lower development charges", -2),
    ("reduce fees for builders", -2),
    ("housing affordability through dc", -2),
    ("housing affordability through development charge", -2),
    ("support provincial housing mandate", -1),
    ("eliminate development charges", -3),
    ("waive development charges", -2),
    ("dc reduction", -1),
    ("development charge reduction", -1),
    ("defer development charges", -1),
    ("freeze development charges", -1),
    ("streamline development charges", -1),
    ("pro-housing", -1),
    ("more homes built faster", -1),
    ("provincial housing targets", -1),
    ("builder-friendly", -1),
]

# Incumbents who voted FOR DC Bylaw 2026-20 get a small negative adjustment
# The bylaw passed May 21, 2026 at York Region Council. Regional and local
# mayors sitting on York Region Council who supported it are noted here.
# This list represents those who are known to have voted in favour.
DC_BYLAW_YES_VOTERS = {
    # Regional councillors / mayors who attend YR Council and approved cuts
    # Without confirmed individual votes we apply a general incumbent adjustment
    # for all mayors (they attend/influence regional decisions) — small penalty
}


def score_from_text(text: str) -> int:
    """
    Compute a raw alignment delta from article/bio text.
    Positive = aligned, negative = misaligned.
    """
    text_lower = text.lower()
    delta = 0

    for phrase, weight in ALIGNED_SIGNALS:
        if phrase in text_lower:
            delta += weight

    for phrase, weight in MISALIGNED_SIGNALS:
        if phrase in text_lower:
            delta += weight  # weight is already negative

    return delta


def label_from_score(score: int) -> str:
    """Convert numeric score to label."""
    if score >= 8:
        return "strongly_aligned"
    elif score >= 6:
        return "aligned"
    elif score >= 4:
        return "neutral"
    elif score >= 2:
        return "misaligned"
    else:
        return "strongly_misaligned"


def clamp(value: int, lo: int = 0, hi: int = 10) -> int:
    return max(lo, min(hi, value))


def score_candidate(candidate: dict, news_articles: list[dict]) -> dict:
    """
    Re-score a candidate based on news articles mentioning their name.
    Returns an updated candidate dict.
    """
    name = candidate["name"].lower()
    # Also match last name only for common references
    name_parts = candidate["name"].split()
    last_name = name_parts[-1].lower() if name_parts else name

    relevant_articles = []
    for article in news_articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        if name in text or (len(last_name) > 3 and last_name in text):
            relevant_articles.append(article)

    if not relevant_articles:
        # No news — preserve existing score, just update mention count
        updated = dict(candidate)
        updated["news_mentions"] = 0
        return updated

    # Compute delta from all relevant articles
    total_delta = 0
    latest_date = None

    for article in relevant_articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        total_delta += score_from_text(text)

        pub = article.get("published_at")
        if pub:
            if latest_date is None or pub > latest_date:
                latest_date = pub

    # Start from baseline 5, apply delta
    base_score = 5
    new_score = clamp(base_score + total_delta)
    new_label = label_from_score(new_score)

    # Incumbent adjustment: incumbents who participated in YR Council
    # when DC Bylaw 2026-20 passed get a slight negative signal (-0.5 → round down)
    # We apply -1 if incumbent and no strong positive signals detected
    if candidate.get("status") == "incumbent" and total_delta == 0:
        new_score = clamp(new_score - 1)
        new_label = label_from_score(new_score)
        fiscal_notes = (
            f"Incumbent; DC Bylaw 2026-20 slight negative adjustment. "
            f"{len(relevant_articles)} news article(s) reviewed."
        )
    else:
        fiscal_notes = (
            f"Scored from {len(relevant_articles)} news article(s). "
            f"Raw delta: {total_delta:+d}."
        )

    updated = dict(candidate)
    updated["fiscal_alignment_score"] = new_score
    updated["fiscal_alignment_label"] = new_label
    updated["fiscal_notes"] = fiscal_notes
    updated["news_mentions"] = len(relevant_articles)
    if latest_date:
        updated["last_news_date"] = latest_date

    return updated


def score_all_candidates(candidates: list[dict], news_articles: list[dict]) -> list[dict]:
    """Score all candidates based on news mentions."""
    scored = []
    for candidate in candidates:
        try:
            updated = score_candidate(candidate, news_articles)
            scored.append(updated)
        except Exception as exc:
            logger.error("Error scoring candidate %s: %s", candidate.get("name"), exc)
            scored.append(candidate)
    return scored
