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

def find_relevant_articles(candidate_name: str, news_articles: list[dict]) -> list[dict]:
    """Find news articles mentioning a candidate by full or last name."""
    name = candidate_name.lower()
    name_parts = candidate_name.split()
    last_name = name_parts[-1].lower() if name_parts else name

    relevant = []
    for article in news_articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        if name in text or (len(last_name) > 3 and last_name in text):
            relevant.append(article)
    return relevant


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


DEFAULT_VOTE_WEIGHT = 3  # contested fiscal votes; consensus votes carry lower per-vote weight


def score_from_votes(candidate_id: str, votes: list[dict]) -> Optional[dict]:
    """
    Compute a weighted alignment position from recorded council votes.

    Each vote contributes sign(±1) × its weight (votes.json `weight`;
    contested fiscal votes default to 3, consensus votes like budget
    adoptions carry ~1 so they lend baseline alignment credit without
    drowning contested signals). The result is normalized by the total
    weight the candidate actually voted on, so the score reflects the
    *proportion* of their record that aligns rather than saturating at
    the extremes after a few votes — someone who opposed the majority on
    every DC question but supported the budget lands low, not at zero.

    Returns None if the candidate has no matching recorded ("yes"/"no")
    votes — absence of data must stay absence of data.
    """
    matches = []
    for vote in votes:
        for result in vote.get("results", []):
            if result.get("candidate_id") == candidate_id and result.get("vote") in ("yes", "no"):
                matches.append((vote, result["vote"]))

    if not matches:
        return None

    delta = 0.0
    weight_sum = 0.0
    contested_delta = 0.0
    contested_voted = 0.0
    notes_parts = []
    for vote, cast in matches:
        direction = vote.get("fiscal_alignment_direction")
        if direction == "yes_vote_is_misaligned":
            sign = -1 if cast == "yes" else 1
        elif direction == "yes_vote_is_aligned":
            sign = 1 if cast == "yes" else -1
        else:
            continue
        weight = vote.get("weight", DEFAULT_VOTE_WEIGHT)
        delta += sign * weight
        weight_sum += weight
        if weight > 1:
            contested_delta += sign * weight
            contested_voted += weight
        notes_parts.append(f'Voted {cast.upper()} on "{vote.get("title")}" ({vote.get("date")}).')

    if weight_sum == 0:
        return None

    # Contested-vote participation: which contested votes (weight > 1, with
    # member results) did this member NOT cast a yes/no in? Absence is honest
    # missing data, but the *extent* of it must be visible — a thin record
    # padded by unanimous consensus votes must not read as a measured lean.
    contested_available = 0.0
    missed_contested = []
    voted_ids = {v.get("id") for v, _ in matches}
    for vote in votes:
        if not vote.get("results") or vote.get("weight", DEFAULT_VOTE_WEIGHT) <= 1:
            continue
        contested_available += vote.get("weight", DEFAULT_VOTE_WEIGHT)
        if vote.get("id") not in voted_ids:
            missed_contested.append(f'{vote.get("title")} ({vote.get("date")})')

    return {
        "position": delta / weight_sum,  # -1.0 (fully misaligned) .. +1.0 (fully aligned)
        "contested_position": (contested_delta / contested_voted) if contested_voted else None,
        "contested_voted": contested_voted,
        "contested_available": contested_available,
        "missed_contested": missed_contested,
        "notes": " ".join(notes_parts),
        "n_votes": len(matches),
    }


def score_candidate(candidate: dict, news_articles: list[dict], votes: Optional[list[dict]] = None) -> dict:
    """
    Re-score a candidate. Voting-record signal (if any) is primary; news-keyword
    signal is secondary/minor when a voting record exists, and the sole signal
    otherwise. `fiscal_alignment_basis` always records which path was used.

    Alignment scores apply only to sitting members of Regional Council
    (incumbents and the appointed Chair) — challengers have no council voting
    record, so they stay unscored (owner decision, 2026-07-07).
    """
    votes = votes or []
    relevant_articles = find_relevant_articles(candidate["name"], news_articles)

    if candidate.get("status") not in ("incumbent", "appointed"):
        updated = dict(candidate)
        updated["news_mentions"] = len(relevant_articles)
        updated["fiscal_alignment_score"] = 5
        updated["fiscal_alignment_label"] = "neutral"
        updated["fiscal_alignment_basis"] = "unscored"
        updated["fiscal_notes"] = "Not scored — no Regional Council voting record (challenger)."
        return updated

    news_delta = 0
    latest_date = None
    for article in relevant_articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        news_delta += score_from_text(text)
        pub = article.get("published_at")
        if pub and (latest_date is None or pub > latest_date):
            latest_date = pub

    vote_result = score_from_votes(candidate["id"], votes)

    updated = dict(candidate)
    updated["news_mentions"] = len(relevant_articles)
    if latest_date:
        updated["last_news_date"] = latest_date

    if vote_result is not None:
        # Voting record is ground truth: it dominates. The normalized position
        # (-1..+1) maps onto the 0-10 scale around the neutral baseline of 5;
        # news delta only nudges within it, deliberately down-weighted so a
        # handful of keyword hits can't override a documented vote.
        new_score = clamp(round(5 + 5 * vote_result["position"]) + news_delta // 3)
        new_label = label_from_score(new_score)
        notes = vote_result["notes"]
        if relevant_articles:
            notes += f" Plus {len(relevant_articles)} news article(s) as minor secondary signal."

        # D (owner decision 2026-07-22): contested participation is always
        # stated, so a thin record is visible wherever the notes surface.
        cav, cvw = vote_result["contested_available"], vote_result["contested_voted"]
        if cav:
            notes += f" Contested-vote participation: {int(cvw)} of {int(cav)} weight"
            if vote_result["missed_contested"]:
                notes += " — did not vote on: " + "; ".join(vote_result["missed_contested"])
            notes += "."

        # A (owner decision 2026-07-22): thin-record guard. A member who
        # missed a substantial share of the contested votes cannot earn a
        # non-neutral label from consensus credit alone — if their contested
        # votes alone read neutral (or don't exist), the label stays neutral.
        if cav and cvw / cav < 0.75 and new_label != "neutral":
            c_pos = vote_result["contested_position"]
            c_label = label_from_score(clamp(round(5 + 5 * c_pos))) if c_pos is not None else "neutral"
            if c_label == "neutral":
                new_score = 5
                new_label = "neutral"
                notes = ("Thin contested record — non-neutral label withheld: contested votes "
                         "alone read neutral, and consensus-vote credit is not sufficient "
                         "evidence at this participation level. ") + notes

        updated["fiscal_alignment_score"] = new_score
        updated["fiscal_alignment_label"] = new_label
        updated["fiscal_alignment_basis"] = "voting_record"
        updated["fiscal_notes"] = notes

    elif relevant_articles:
        new_score = clamp(5 + news_delta)
        updated["fiscal_alignment_score"] = new_score
        updated["fiscal_alignment_label"] = label_from_score(new_score)

        if candidate.get("status") == "incumbent" and news_delta == 0:
            new_score = clamp(new_score - 1)
            updated["fiscal_alignment_score"] = new_score
            updated["fiscal_alignment_label"] = label_from_score(new_score)
            updated["fiscal_alignment_basis"] = "incumbency_default"
            updated["fiscal_notes"] = (
                f"Incumbent; no clear DC-related signal in {len(relevant_articles)} news article(s) reviewed. "
                f"Default incumbency adjustment applied (tacit association with DC Bylaw 2026-20)."
            )
        else:
            updated["fiscal_alignment_basis"] = "news_inferred"
            updated["fiscal_notes"] = (
                f"Scored from {len(relevant_articles)} news article(s). Raw delta: {news_delta:+d}."
            )

    elif candidate.get("status") == "incumbent":
        new_score = clamp(5 - 1)
        updated["fiscal_alignment_score"] = new_score
        updated["fiscal_alignment_label"] = label_from_score(new_score)
        updated["fiscal_alignment_basis"] = "incumbency_default"
        updated["fiscal_notes"] = (
            "No recorded vote or news signal found. Default incumbency adjustment applied "
            "(tacit association with DC Bylaw 2026-20)."
        )

    else:
        # No votes, no news, not an incumbent — nothing to score from. Leave
        # score/label as-is (default neutral 5) rather than fabricate a basis.
        updated["fiscal_alignment_basis"] = "unscored"
        updated["fiscal_notes"] = ""

    return updated


def score_all_candidates(
    candidates: list[dict], news_articles: list[dict], votes: Optional[list[dict]] = None
) -> list[dict]:
    """Score all candidates based on recorded votes (primary) and news mentions (secondary/fallback)."""
    scored = []
    for candidate in candidates:
        try:
            updated = score_candidate(candidate, news_articles, votes)
            scored.append(updated)
        except Exception as exc:
            logger.error("Error scoring candidate %s: %s", candidate.get("name"), exc)
            scored.append(candidate)
    return scored
