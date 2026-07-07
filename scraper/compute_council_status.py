"""
Lame-duck council status calculator (Municipal Act, 2001, s.275).

A council becomes "lame duck" — restricted from hiring/firing senior staff,
selling assets over $50k, or approving non-budgeted expenditures over $50k —
if fewer than three-quarters of its *current* elected members have been
nominated for re-election (to any office, any municipality) as of nomination
day. This module computes that status for York Regional Council (only — local
municipal councils are out of scope for this dashboard by owner decision).

Pure function: no network calls. Depends only on seats.json + candidates.json.
"""

import logging
import math

logger = logging.getLogger(__name__)

# York Regional Council's elected roster is fixed public record for this term
# (9 Mayors + 12 Regional Councillors; the Chair is appointed, not counted).
# Hardcoded with an assertion rather than derived at runtime, since a bad
# edit to seats.json should fail loudly rather than silently change the
# lame-duck threshold that drives this whole feature.
REGIONAL_COUNCIL_SIZE = 21
REGIONAL_THRESHOLD_FRACTION = 0.75
REGIONAL_THRESHOLD_COUNT = math.ceil(REGIONAL_COUNCIL_SIZE * REGIONAL_THRESHOLD_FRACTION)  # 16


def _candidates_by_id(candidates):
    return {c["id"]: c for c in candidates}


def _filed_counts(member_candidates):
    """Split a list of candidate records by filing status."""
    confirmed = [c for c in member_candidates if c.get("filed_for_reelection") == "confirmed"]
    declined = [c for c in member_candidates if c.get("filed_for_reelection") == "declined"]
    not_yet = [c for c in member_candidates if c.get("filed_for_reelection") == "not_yet"]
    unknown = [c for c in member_candidates if c.get("filed_for_reelection") not in ("confirmed", "declined", "not_yet")]
    return confirmed, declined, not_yet, unknown


def _status_for_roster(member_candidates, total_seats, threshold_count, nomination_day_passed):
    """
    Apply the s.275 threshold to a roster of current-term members.
    Returns (status, status_basis) where status is one of:
      "on_track" | "at_risk" | "lame_duck_confirmed" | "unknown"
    """
    confirmed, declined, not_yet, unknown = _filed_counts(member_candidates)
    confirmed_n, declined_n, not_yet_n, unknown_n = len(confirmed), len(declined), len(not_yet), len(unknown)

    # Best case: everyone except those who've explicitly declined could still
    # file before nomination day. "not_yet" means "hasn't filed as of this
    # check" — same as "unknown" for this purpose, not the same as "declined".
    best_case_remaining = confirmed_n + not_yet_n + unknown_n

    if confirmed_n == 0 and declined_n == 0:
        return "unknown", (
            f"No filing data yet for any of the {total_seats} current members. "
            f"Need {threshold_count} of {total_seats} to file for re-election by nomination day to avoid lame-duck status."
        )

    if confirmed_n >= threshold_count:
        return "on_track", (
            f"{confirmed_n} of {total_seats} current members have confirmed re-election filings — "
            f"already meets the {threshold_count}-of-{total_seats} threshold."
        )

    if best_case_remaining < threshold_count:
        if nomination_day_passed:
            return "lame_duck_confirmed", (
                f"Nomination day has passed. Only {confirmed_n} of {total_seats} current members filed for "
                f"re-election ({declined_n} declined, {not_yet_n} did not file) — below the "
                f"{threshold_count}-of-{total_seats} threshold. Council is lame duck under Municipal Act s.275."
            )
        return "lame_duck_confirmed", (
            f"{confirmed_n} confirmed + {unknown_n} unknown = {best_case_remaining} best-case filers, which "
            f"cannot reach the {threshold_count}-of-{total_seats} threshold even if every remaining unknown "
            f"member files. Lame-duck status is mathematically locked in for nomination day."
        )

    return "at_risk", (
        f"{confirmed_n} of {total_seats} current members confirmed filing so far ({declined_n} declined, "
        f"{unknown_n} still unknown). Threshold is {threshold_count} of {total_seats} — outcome is not yet decided."
    )


def compute_regional_status(seats, candidates, nomination_day_passed=False):
    regional_seats = [s for s in seats if s.get("is_regional_seat")]
    assert len(regional_seats) == REGIONAL_COUNCIL_SIZE, (
        f"Expected {REGIONAL_COUNCIL_SIZE} regional-council seats in seats.json, found {len(regional_seats)}. "
        "seats.json may have drifted from the confirmed roster (9 Mayors + 12 Regional Councillors)."
    )

    cand_by_id = _candidates_by_id(candidates)
    members = []
    for seat in regional_seats:
        cand = cand_by_id.get(seat.get("incumbent_candidate_id"))
        members.append({
            "seat_id": seat["id"],
            "name": cand["name"] if cand else None,
            "municipality": seat["municipality"],
            "office": seat["office"],
            "filed_for_reelection": cand.get("filed_for_reelection", "unknown") if cand else "unknown",
        })

    member_candidates = [cand_by_id[s["incumbent_candidate_id"]] for s in regional_seats
                          if s.get("incumbent_candidate_id") in cand_by_id]

    status, basis = _status_for_roster(
        member_candidates, REGIONAL_COUNCIL_SIZE, REGIONAL_THRESHOLD_COUNT, nomination_day_passed
    )
    confirmed, declined, not_yet, unknown = _filed_counts(member_candidates)

    return {
        "total_current_elected_members": REGIONAL_COUNCIL_SIZE,
        # Council has 22 voting members: 21 elected + the appointed Chair.
        # 3/4 of 22 = 16.5 -> 17 members must continue to avoid lame duck;
        # the appointed Chair continues automatically (not on the ballot),
        # so 16 elected re-election filings satisfy the requirement. The
        # dashboard displays x/22; the threshold on elected filings stays 16.
        "total_voting_members": REGIONAL_COUNCIL_SIZE + 1,
        "chair_note": "Eric Jolliffe (appointed voting member; continues automatically, cannot file)",
        "threshold_fraction": REGIONAL_THRESHOLD_FRACTION,
        "threshold_count": REGIONAL_THRESHOLD_COUNT,
        "confirmed_filed_count": len(confirmed),
        "declined_count": len(declined),
        "not_yet_filed_count": len(not_yet),
        "unknown_count": len(unknown),
        "status": status,
        "status_basis": basis,
        "members": members,
    }


def compute_council_status(seats, candidates, now_iso, nomination_day, nomination_day_passed=False):
    # Regional Council only. Per-municipality lame-duck status was removed
    # with the ward-councillor data (owner decision, 2026-07-06) — local
    # council rosters are no longer tracked, so the s.275 math can only be
    # computed for the 21-member Regional Council.
    logger.info("Computing regional lame-duck status")
    regional = compute_regional_status(seats, candidates, nomination_day_passed)

    return {
        "computed_at": now_iso,
        "nomination_day": nomination_day,
        "regional_council": regional,
    }
