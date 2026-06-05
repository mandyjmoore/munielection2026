"""
News scraper for York Region 2026 Municipal Election.
Fetches RSS feeds from Google News for election and DC-related stories.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import feedparser

logger = logging.getLogger(__name__)

MUNICIPALITIES = [
    "Aurora",
    "East Gwillimbury",
    "Georgina",
    "King",
    "Markham",
    "Newmarket",
    "Richmond Hill",
    "Vaughan",
    "Whitchurch-Stouffville",
]

DC_KEYWORDS = [
    "development charge",
    "development charges",
    "DC bylaw",
    "DC rates",
    "growth pays for growth",
    "infrastructure funding",
    "fiscal pressure",
    "2026-20",
]

ALIGNED_KEYWORDS = [
    "growth pays for growth",
    "infrastructure funding",
    "development charges must reflect costs",
    "oppose provincial downloading",
    "restore dc rates",
    "fiscal responsibility",
    "infrastructure first",
]

MISALIGNED_KEYWORDS = [
    "cut development charges",
    "reduce fees for builders",
    "housing affordability through dc",
    "support provincial housing mandate",
    "eliminate development charges",
    "lower development charges",
]


def build_rss_urls() -> list[tuple[str, str, Optional[str]]]:
    """
    Returns list of (feed_url, category, municipality_tag) tuples.
    """
    feeds = []

    # General election feed
    feeds.append((
        "https://news.google.com/rss/search?q=York+Region+municipal+election+2026&hl=en-CA&gl=CA&ceid=CA:en",
        "election",
        None,
    ))

    # DC-specific feed
    feeds.append((
        "https://news.google.com/rss/search?q=York+Region+development+charges+2026&hl=en-CA&gl=CA&ceid=CA:en",
        "development_charges",
        None,
    ))

    # Per-municipality feeds
    for muni in MUNICIPALITIES:
        query = f"{muni}+Ontario+municipal+election+2026"
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-CA&gl=CA&ceid=CA:en"
        feeds.append((url, "election", muni))

    return feeds


def article_id(url: str, title: str) -> str:
    """Generate a stable ID for a news article."""
    key = f"{url}|{title}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def detect_municipalities(text: str) -> list[str]:
    """Detect which municipalities are mentioned in article text."""
    text_lower = text.lower()
    found = []
    for muni in MUNICIPALITIES:
        if muni.lower() in text_lower:
            found.append(muni)
    return found


def is_dc_related(text: str) -> bool:
    """Check if article is related to development charges."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in DC_KEYWORDS)


def parse_feed(feed_url: str, category: str, municipality_tag: Optional[str]) -> list[dict]:
    """Parse a single RSS feed and return list of article dicts."""
    articles = []
    try:
        parsed = feedparser.parse(feed_url)
        if parsed.bozo and not parsed.entries:
            logger.warning("Feed parse error for %s: %s", feed_url, parsed.bozo_exception)
            return []

        for entry in parsed.entries[:30]:  # Max 30 per feed
            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary = getattr(entry, "summary", "") or ""

            # Parse published date
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                except Exception:
                    pass

            full_text = f"{title} {summary}".lower()
            dc_related = is_dc_related(full_text)

            # Detect municipalities from text
            detected_munis = detect_municipalities(full_text)
            if municipality_tag and municipality_tag not in detected_munis:
                detected_munis.insert(0, municipality_tag)

            aid = article_id(link, title)

            articles.append({
                "id": aid,
                "title": title,
                "url": link,
                "summary": re.sub(r"<[^>]+>", "", summary)[:500],  # strip HTML
                "published_at": pub_date,
                "category": category,
                "municipalities": detected_munis,
                "dc_related": dc_related,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })

    except Exception as exc:
        logger.error("Failed to fetch feed %s: %s", feed_url, exc)

    return articles


def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by ID, keeping first occurrence."""
    seen = set()
    unique = []
    for art in articles:
        if art["id"] not in seen:
            seen.add(art["id"])
            unique.append(art)
    return unique


def fetch_all_news(existing_news: list[dict], max_age_days: int = 90) -> list[dict]:
    """
    Fetch all news feeds, merge with existing, deduplicate, and trim old articles.
    Returns merged list sorted by published_at descending.
    """
    feeds = build_rss_urls()
    new_articles = []

    for feed_url, category, muni in feeds:
        logger.info("Fetching feed: %s", feed_url)
        articles = parse_feed(feed_url, category, muni)
        logger.info("Got %d articles from %s", len(articles), feed_url)
        new_articles.extend(articles)

    # Merge with existing
    all_articles = existing_news + new_articles
    all_articles = deduplicate_articles(all_articles)

    # Remove articles older than max_age_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    filtered = []
    for art in all_articles:
        if art.get("published_at"):
            try:
                pub = datetime.fromisoformat(art["published_at"].replace("Z", "+00:00"))
                if pub < cutoff:
                    continue
            except Exception:
                pass
        filtered.append(art)

    # Sort by published_at descending
    def sort_key(a: dict):
        dt = a.get("published_at") or ""
        return dt

    filtered.sort(key=sort_key, reverse=True)

    logger.info("Total news articles after merge/dedup: %d", len(filtered))
    return filtered
