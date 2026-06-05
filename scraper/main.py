"""
Main scraper orchestrator for York Region 2026 Municipal Election Dashboard.
Runs all scrapers, updates data files, commits are handled by GitHub Actions.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

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

    logger.info(
        "Loaded %d existing candidates, %d existing news articles",
        len(existing_candidates),
        len(existing_news),
    )

    # --- Step 1: Fetch news ---
    logger.info("--- Fetching news ---")
    try:
        updated_news = fetch_all_news(existing_news)
    except Exception as exc:
        logger.error("News fetch failed: %s", exc)
        updated_news = existing_news

    # --- Step 2: Fetch candidates ---
    logger.info("--- Fetching candidates ---")
    try:
        updated_candidates = fetch_all_candidates(existing_candidates)
    except Exception as exc:
        logger.error("Candidate fetch failed: %s", exc)
        updated_candidates = existing_candidates

    # --- Step 3: Score candidates ---
    logger.info("--- Scoring candidates ---")
    try:
        scored_candidates = score_all_candidates(updated_candidates, updated_news)
    except Exception as exc:
        logger.error("Scoring failed: %s", exc)
        scored_candidates = updated_candidates

    # --- Step 4: Update metadata ---
    metadata["last_updated"] = now_iso
    metadata["candidate_count"] = len(scored_candidates)
    metadata["news_count"] = len(updated_news)

    # Count new registrations in last 24h (based on scraped_at)
    from datetime import timedelta
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    new_registrations = [
        c for c in scored_candidates
        if c.get("scraped_at") and c["scraped_at"] > cutoff_24h
        and c.get("source") == "scraped"
    ]
    metadata["new_registrations_24h"] = len(new_registrations)

    # --- Step 5: Save ---
    save_json(CANDIDATES_FILE, scored_candidates)
    save_json(NEWS_FILE, updated_news)
    save_json(METADATA_FILE, metadata)

    logger.info("=== Scraper complete. %d candidates, %d news articles ===",
                len(scored_candidates), len(updated_news))


if __name__ == "__main__":
    main()
