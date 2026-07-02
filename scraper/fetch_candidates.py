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

# NOTE: There is no "York Region" candidate page to scrape — Regional Council
# has no separate election; its members are the 9 municipal mayors plus
# regional councillors elected as part of specific municipalities' local
# ballots. The old scraper had a "York Region" entry here pointing at a
# general york.ca info page, and it's what produced the 330 nav-menu-junk
# "candidates" this rebuild is cleaning up. Do not re-add it.
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
}

# Hard safeguards against the failure mode that produced 330 garbage records:
# any candidate extracted must have a real office and belong to a known
# municipality, and a single municipality producing an implausible number of
# "candidates" is treated as a scraper bug, not real data.
VALID_OFFICES = {"mayor", "regional councillor", "councillor"}
KNOWN_MUNICIPALITIES = set(MUNICIPALITY_URLS.keys())
MAX_CANDIDATES_PER_MUNICIPALITY = 20
# A candidate/nomination list page should contain at least one of these terms
# somewhere in its text; if it doesn't, this almost certainly isn't a real
# candidate list yet (e.g. a generic "how elections work" info page) and
# extraction should be skipped rather than run against the wrong content.
PAGE_MARKER_TERMS = ["candidate", "nomination", "nominee"]


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


def page_looks_like_candidate_list(soup: BeautifulSoup) -> bool:
    """
    Sanity check before extraction runs. The original scraper's fatal flaw was
    running extraction against a page that was never actually a candidate
    list (a general York Region info page), producing 330 nav-menu-junk
    "candidates". Require the page to actually mention candidates/nominations
    somewhere before trusting anything extracted from it.
    """
    text = soup.get_text(" ", strip=True).lower()
    return any(term in text for term in PAGE_MARKER_TERMS)


def _make_candidate_record(municipality: str, office: str, name: str, ward: Optional[str], now_iso: str, source_url: str) -> Optional[dict]:
    """Build a candidate record, or return None if it fails validation safeguards."""
    if not name or len(name) < 2:
        return None
    if municipality not in KNOWN_MUNICIPALITIES:
        return None
    if office.strip().lower() not in VALID_OFFICES:
        return None

    cid = make_candidate_id(municipality, office, name, ward)
    return {
        "id": cid,
        "seat_id": None,  # reconciled against seats.json separately, not guessed here
        "name": name,
        "municipality": municipality,
        "office": office,
        "ward": ward,
        "status": "unknown",
        "filed_for_reelection": "confirmed",  # appearing on an official clerk candidate list means they filed
        "filing_source": source_url,
        "registered": True,
        "registration_date": None,
        "fiscal_alignment_score": 5,
        "fiscal_alignment_label": "neutral",
        "fiscal_alignment_basis": "unscored",
        "fiscal_notes": "",
        "news_mentions": 0,
        "last_news_date": None,
        "likely_to_run_again": None,
        "likely_to_win": None,
        "source": "scraped",
        "scraped_at": now_iso,
    }


def extract_candidates_generic(soup: BeautifulSoup, municipality: str, source_url: str) -> list[dict]:
    """
    Table-based extraction only: looks for a table whose header row identifies
    a name column (plus optionally office/ward columns). Every extracted
    candidate is validated against VALID_OFFICES/KNOWN_MUNICIPALITIES before
    being kept.

    Deliberately no generic list-heading fallback here (removed — it was the
    source of all 330 garbage records from the previous scraper run, matching
    arbitrary <li> text as candidate names on pages that didn't actually list
    candidates). If a municipality's real candidate list isn't table-based,
    it needs its own targeted extraction function, not a looser heuristic.
    """
    if not page_looks_like_candidate_list(soup):
        logger.warning(
            "%s page doesn't appear to be a candidate/nomination list yet — skipping extraction", municipality
        )
        return []

    candidates = []
    now_iso = datetime.now(timezone.utc).isoformat()

    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        headers_row = rows[0] if rows else None
        if not headers_row:
            continue

        col_headers = [th.get_text(strip=True).lower() for th in headers_row.find_all(["th", "td"])]

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
            office = cells[office_idx].get_text(strip=True) if office_idx is not None and office_idx < len(cells) else ""
            ward = cells[ward_idx].get_text(strip=True) if ward_idx is not None and ward_idx < len(cells) else None

            record = _make_candidate_record(municipality, office, name, ward, now_iso, source_url)
            if record is not None:
                candidates.append(record)

    if len(candidates) > MAX_CANDIDATES_PER_MUNICIPALITY:
        logger.error(
            "%s scrape produced %d candidates (cap %d) — treating as a scraper bug, discarding this run's results",
            municipality, len(candidates), MAX_CANDIDATES_PER_MUNICIPALITY,
        )
        return []

    return candidates


# Every municipality currently routes through extract_candidates_generic
# (table-based extraction only, with the safeguards above). None of the 9
# municipality URLs have been manually verified yet to confirm they host a
# real, structured candidate table (see rebuild plan, phase 5.4/5.2) — until
# that verification happens per-municipality, a dedicated extraction function
# would just be guessing at a page structure nobody has looked at. Once a
# municipality is verified, give it its own function here (e.g. a real
# scrape_markham() targeting Elections Markham's actual table selectors)
# instead of relying on the generic fallback.


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

        try:
            scraped = extract_candidates_generic(soup, municipality, url)
            logger.info("Found %d candidates for %s", len(scraped), municipality)
            all_scraped.extend(scraped)
        except Exception as exc:
            logger.error("Scraper error for %s: %s", municipality, exc)

    merged = merge_candidates(existing_candidates, all_scraped)
    logger.info("Total candidates after merge: %d", len(merged))
    return merged
