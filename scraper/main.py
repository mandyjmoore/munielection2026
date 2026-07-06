"""
Main scraper orchestrator for York Region 2026 Municipal Election Dashboard.
Runs all scrapers, updates data files, commits are handled by GitHub Actions.
"""

import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from compute_council_status import compute_council_status
from estimate_race_outlook import estimate_all
from fetch_candidates import fetch_all_candidates
from fetch_news import fetch_all_news
from score_alignment import score_all_candidates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Paths relative to repo root
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
CANDIDATES_FILE = DATA_DIR / "candidates.json"
NEWS_FILE = DATA_DIR / "news.json"
METADATA_FILE = DATA_DIR / "metadata.json"
SEATS_FILE = DATA_DIR / "seats.json"
VOTES_FILE = DATA_DIR / "votes.json"
COUNCIL_STATUS_FILE = DATA_DIR / "council_status.json"

# Candidate scraping is live for the 6 municipalities with a verified,
# working extraction path (Georgina, Richmond Hill, Newmarket, Aurora, East
# Gwillimbury, King — see SCRAPABLE_MUNICIPALITIES in fetch_candidates.py).
# Markham/Vaughan (bot-blocked) and Whitchurch-Stouffville (JS-rendered) fall
# back to existing/seeded data until a workaround exists for those.
ENABLE_CANDIDATE_SCRAPE = True


def load_json(path: Path, default):
    """Load JSON from file, returning default if missing or invalid."""
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        logger.warning("Could not load %s: %s", path, exc)
    return default


def save_json(path: Path, data, indent: int = 2):
    """Save data as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.write("\n")
    logger.info("Saved %s", path)


def main():
    logger.info("=== York Region 2026 Election Scraper Starting ===")
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Load existing data
    existing_candidates = load_json(CANDIDATES_FILE, [])
    existing_news = load_json(NEWS_FILE, [])
    metadata = load_json(METADATA_FILE, {})
    seats = load_json(SEATS_FILE, [])
    votes = load_json(VOTES_FILE, {}).get("votes", [])

    logger.info(
        "Loaded %d existing candidates, %d existing news articles, %d seats, %d votes",
        len(existing_candidates), len(existing_news), len(seats), len(votes),
    )

    # --- Step 1: Fetch news ---
    logger.info("--- Fetching news ---")
    try:
        updated_news = fetch_all_news(existing_news)
    except Exception as exc:
        logger.error("News fetch failed: %s", exc)
        updated_news = existing_news

    # --- Step 2: Fetch candidates (see ENABLE_CANDIDATE_SCRAPE) ---
    if ENABLE_CANDIDATE_SCRAPE:
        logger.info("--- Fetching candidates ---")
        try:
            updated_candidates = fetch_all_candidates(existing_candidates, seats)
        except Exception as exc:
            logger.error("Candidate fetch failed: %s", exc)
            updated_candidates = existing_candidates
    else:
        logger.info("--- Candidate scraping disabled; using manually-seeded/reviewed data as-is ---")
        updated_candidates = existing_candidates

    # --- Step 3: Score candidates (voting record primary, news secondary) ---
    logger.info("--- Scoring candidates ---")
    try:
        scored_candidates = score_all_candidates(updated_candidates, updated_news, votes)
    except Exception as exc:
        logger.error("Scoring failed: %s", exc)
        scored_candidates = updated_candidates

    # --- Step 4: Estimate race outlook (likely to run again / likely to win) ---
    logger.info("--- Estimating race outlook ---")
    nomination_close = metadata.get("nomination_close")
    nomination_day_passed = bool(nomination_close and date.today().isoformat() > nomination_close)
    try:
        scored_candidates = estimate_all(
            scored_candidates, updated_news, now_iso, nomination_day_passed
        )
    except Exception as exc:
        logger.error("Race outlook estimation failed: %s", exc)

    # --- Step 5: Compute council lame-duck status ---
    council_status = None
    if seats:
        logger.info("--- Computing council lame-duck status ---")
        try:
            council_status = compute_council_status(
                seats, scored_candidates, now_iso,
                metadata.get("nomination_close"), nomination_day_passed,
            )
        except Exception as exc:
            logger.error("Council status computation failed: %s", exc)
    else:
        logger.warning("No seats.json data found — skipping council status computation")

    # --- Step 6: Update metadata ---
    metadata["last_updated"] = now_iso
    metadata["candidate_count"] = len(scored_candidates)
    metadata["news_count"] = len(updated_news)

    # New registrations in the last 24h, based on first_seen_at (stable across
    # re-scrapes — scraped_at refreshes every run, which previously made every
    # candidate count as "new" forever).
    from datetime import timedelta
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    new_registrations = [
        c for c in scored_candidates
        if c.get("source") == "scraped"
        and (c.get("first_seen_at") or c.get("scraped_at") or "") > cutoff_24h
    ]
    metadata["new_registrations_24h"] = len(new_registrations)

    # Filings in the last 7 days by the clerk-published date filed — the
    # real-world "timely" signal, independent of when we happened to scrape.
    def parse_filed(c):
        raw = c.get("registration_date")
        if not raw:
            return None
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
        return None

    cutoff_7d = (now - timedelta(days=7)).date()
    metadata["new_filings_7d"] = sum(
        1 for c in scored_candidates
        if c.get("registered") and (d := parse_filed(c)) and d >= cutoff_7d
    )

    from fetch_candidates import SCRAPABLE_MUNICIPALITIES, MUNICIPALITY_URLS
    metadata["data_confidence"] = {
        "candidates_confirmed_filed": sum(
            1 for c in scored_candidates if c.get("filed_for_reelection") == "confirmed"
        ),
        "candidates_unknown_filing_status": sum(
            1 for c in scored_candidates if c.get("filed_for_reelection") not in ("confirmed", "declined")
        ),
        "seats_total": len(seats),
        "candidate_scraper_enabled": ENABLE_CANDIDATE_SCRAPE,
        "scrape_coverage": {
            muni: ("live" if muni in SCRAPABLE_MUNICIPALITIES else "manual_check_required")
            for muni in MUNICIPALITY_URLS
        },
    }

    # --- Step 7: Save ---
    save_json(CANDIDATES_FILE, scored_candidates)
    save_json(NEWS_FILE, updated_news)
    save_json(METADATA_FILE, metadata)
    if council_status is not None:
        save_json(COUNCIL_STATUS_FILE, council_status)

    logger.info("=== Scraper complete. %d candidates, %d news articles ===",
                len(scored_candidates), len(updated_news))


if __name__ == "__main__":
    main()
