"""
Candidate scraper for York Region 2026 Municipal Election.
Scrapes each municipality's elections page for registered candidates.
Falls back gracefully on errors and preserves seeded data.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; YRElectionBot/1.0; "
        "+https://github.com/yr-election-dashboard)"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
}

MUNICIPALITY_URLS = {
    "Markham": "https://www.electionsmarkham.ca/en/candidates/list-of-candidates/",
    "Vaughan": "https://www.vaughan.ca/government/elections/candidates",
    "Richmond Hill": "https://www.richmondhill.ca/en/find-council/elections.aspx",
    "Newmarket": "https://www.newmarket.ca/en/town-hall/elections.aspx",
    "Aurora": "https://www.aurora.ca/en/town-services/elections.aspx",
    "East Gwillimbury": "https://www.eastgwillimbury.ca/en/town-services/elections.aspx",
    "Georgina": "https://www.georgina.ca/en/town-services/2026-election.aspx",
    "King": "https://www.king.ca/en/local-government/elections.aspx",
    "Whitchurch-Stouffville": "https://www.townofws.ca/en/town-hall/elections.aspx",
    "York Region": "https://www.york.ca/york-region/municipal-election",
}


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text


def make_candidate_id(municipality: str, office: str, name: str, ward: Optional[str] = None) -> str:
    parts = [slugify(municipality), slugify(office)]
    if ward:
        parts.append(slugify(ward))
    parts.append(slugify(name))
    return "-".join(parts)


def fetch_page(url: str, timeout: int = 15) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def extract_candidates_generic(soup: BeautifulSoup, municipality: str) -> list[dict]:
    """
    Generic extraction: looks for tables or lists that contain candidate names
    alongside office/ward information. Returns a list of partial candidate dicts.
    """
    candidates = []
    now_iso = datetime.now(timezone.utc).isoformat()

    # Try tables first (most municipal pages use tables)
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        headers_row = rows[0] if rows else None
        if not headers_row:
            continue

        col_headers = [th.get_text(strip=True).lower() for th in headers_row.find_all(["th", "td"])]

        # Find relevant column indices
        name_idx = next((i for i, h in enumerate(col_headers) if "name" in h or "candidate" in h), None)
        office_idx = next((i for i, h in enumerate(col_headers) if "office" in h or "position" in h or "race" in h), None)
        ward_idx = next((i for i, h in enumerate(col_headers) if "ward" in h or "district" in h), None)

        if name_idx is None:
            continue

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= name_idx:
                continue

            name = cells[name_idx].get_text(strip=True)
            if not name or len(name) < 2:
                continue

            office = cells[office_idx].get_text(strip=True) if office_idx and office_idx < len(cells) else "Unknown"
            ward = cells[ward_idx].get_text(strip=True) if ward_idx and ward_idx < len(cells) else None

            cid = make_candidate_id(municipality, office, name, ward)
            candidates.append({
                "id": cid,
                "name": name,
                "municipality": municipality,
                "office": office,
                "ward": ward,
                "status": "unknown",
                "registered": True,
                "registration_date": None,
                "fiscal_alignment_score": 5,
                "fiscal_alignment_label": "neutral",
                "fiscal_notes": "",
                "news_mentions": 0,
                "last_news_date": None,
                "source": "scraped",
                "scraped_at": now_iso,
            })

    # If no tables found, try list-based extraction
    if not candidates:
        # Look for headings that might indicate office, then lists of names
        current_office = "Unknown"
        current_ward = None
        for elem in soup.find_all(["h1", "h2", "h3", "h4", "li", "p"]):
            text = elem.get_text(strip=True)
            if not text:
                continue

            # Detect office headings
            if elem.name in ["h2", "h3", "h4"]:
                text_lower = text.lower()
                if "mayor" in text_lower:
                    current_office = "Mayor"
                    current_ward = None
                elif "regional councillor" in text_lower:
                    current_office = "Regional Councillor"
                    m = re.search(r"ward\s+(\w+)", text_lower)
                    current_ward = m.group(1).capitalize() if m else None
                elif "councillor" in text_lower or "council" in text_lower:
                    current_office = "Councillor"
                    m = re.search(r"ward\s+(\w+)", text_lower)
                    current_ward = m.group(1).capitalize() if m else None
                continue

            if elem.name == "li":
                # Simple name heuristic: 2+ words, title case, not too long
                if 2 <= len(text.split()) <= 6 and text[0].isupper() and len(text) < 60:
                    cid = make_candidate_id(municipality, current_office, text, current_ward)
                    candidates.append({
                        "id": cid,
                        "name": text,
                        "municipality": municipality,
                        "office": current_office,
                        "ward": current_ward,
                        "status": "unknown",
                        "registered": True,
                        "registration_date": None,
                        "fiscal_alignment_score": 5,
                        "fiscal_alignment_label": "neutral",
                        "fiscal_notes": "",
                        "news_mentions": 0,
                        "last_news_date": None,
                        "source": "scraped",
                        "scraped_at": now_iso,
                    })

    return candidates


def scrape_markham(soup: BeautifulSoup) -> list[dict]:
    """Scrape Elections Markham candidate list."""
    return extract_candidates_generic(soup, "Markham")


def scrape_vaughan(soup: BeautifulSoup) -> list[dict]:
    """Scrape Vaughan candidate list."""
    return extract_candidates_generic(soup, "Vaughan")


def scrape_richmond_hill(soup: BeautifulSoup) -> list[dict]:
    return extract_candidates_generic(soup, "Richmond Hill")


def scrape_newmarket(soup: BeautifulSoup) -> list[dict]:
    return extract_candidates_generic(soup, "Newmarket")


def scrape_aurora(soup: BeautifulSoup) -> list[dict]:
    return extract_candidates_generic(soup, "Aurora")


def scrape_east_gwillimbury(soup: BeautifulSoup) -> list[dict]:
    return extract_candidates_generic(soup, "East Gwillimbury")


def scrape_georgina(soup: BeautifulSoup) -> list[dict]:
    return extract_candidates_generic(soup, "Georgina")


def scrape_king(soup: BeautifulSoup) -> list[dict]:
    return extract_candidates_generic(soup, "King")


def scrape_whitchurch_stouffville(soup: BeautifulSoup) -> list[dict]:
    return extract_candidates_generic(soup, "Whitchurch-Stouffville")


def scrape_york_region(soup: BeautifulSoup) -> list[dict]:
    """Scrape York Region page for regional councillor candidates."""
    return extract_candidates_generic(soup, "York Region")


SCRAPERS = {
    "Markham": scrape_markham,
    "Vaughan": scrape_vaughan,
    "Richmond Hill": scrape_richmond_hill,
    "Newmarket": scrape_newmarket,
    "Aurora": scrape_aurora,
    "East Gwillimbury": scrape_east_gwillimbury,
    "Georgina": scrape_georgina,
    "King": scrape_king,
    "Whitchurch-Stouffville": scrape_whitchurch_stouffville,
    "York Region": scrape_york_region,
}


def merge_candidates(existing: list[dict], scraped: list[dict]) -> list[dict]:
    """
    Merge scraped candidates into existing list.
    - Existing seeded/manually-set records are preserved.
    - New scraped candidates are appended.
    - Scraped data updates non-manual fields for matching IDs.
    """
    existing_by_id = {c["id"]: c for c in existing}

    for sc in scraped:
        cid = sc["id"]
        if cid in existing_by_id:
            # Update only automated fields
            existing_by_id[cid]["scraped_at"] = sc["scraped_at"]
            existing_by_id[cid]["registered"] = sc["registered"]
            # Don't overwrite manually set scores/notes
            if existing_by_id[cid]["source"] == "seeded":
                existing_by_id[cid]["source"] = "scraped"
        else:
            existing_by_id[cid] = sc

    return list(existing_by_id.values())


def fetch_all_candidates(existing_candidates: list[dict]) -> list[dict]:
    """
    Main entry point: scrape all municipalities and merge with existing data.
    Returns the merged candidate list.
    """
    all_scraped = []

    for municipality, url in MUNICIPALITY_URLS.items():
        logger.info("Scraping %s from %s", municipality, url)
        soup = fetch_page(url)
        if soup is None:
            logger.warning("Skipping %s — page fetch failed", municipality)
            continue

        scraper_fn = SCRAPERS.get(municipality)
        if scraper_fn is None:
            logger.warning("No scraper for %s", municipality)
            continue

        try:
            scraped = scraper_fn(soup)
            logger.info("Found %d candidates for %s", len(scraped), municipality)
            all_scraped.extend(scraped)
        except Exception as exc:
            logger.error("Scraper error for %s: %s", municipality, exc)

    merged = merge_candidates(existing_candidates, all_scraped)
    logger.info("Total candidates after merge: %d", len(merged))
    return merged
