"""
Candidate scraper for York Region 2026 Municipal Election.

Scrapes each municipality's official candidate-registration page. These are
the municipal clerks' own published lists — the authoritative source for
"who has filed to run." Each municipality publishes this differently (see
per-municipality functions below), so this deliberately does NOT use a
generic heuristic that guesses at page structure — that approach previously
produced 330 garbage "candidates" scraped off an unrelated nav menu. Every
extraction path here was built and verified against a real, current snapshot
of each municipality's actual page.

Markham and Vaughan block non-browser requests with bot-detection challenges
(Reblaze-style JS challenge / 403) and cannot be scraped this way currently —
they're left in MUNICIPALITY_URLS so failures are visible in logs, but no
extraction is attempted for them. Whitchurch-Stouffville's candidate list is
rendered client-side via JavaScript and is also not scrapable via a plain
HTTP fetch. All three fall back to whatever's already in candidates.json.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

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

# Verified 2026-07-02 by fetching each URL directly and inspecting real page
# content. There is no "York Region" candidate page — Regional Council has
# no separate election; its members are the 9 municipal mayors plus regional
# councillors elected as part of specific municipalities' local ballots. The
# old scraper had a "York Region" entry pointing at a general york.ca info
# page, which is what produced the original 330 nav-menu-junk "candidates".
MUNICIPALITY_URLS = {
    "Georgina": "https://www.georgina.ca/municipal-government/elections/2026-candidate-information",
    "Richmond Hill": "https://www.richmondhill.ca/en/living-here/election-candidates.aspx",
    "Newmarket": "https://newmarketvotes.ca/candidates/registered-candidates/",
    "Aurora": "https://www.aurora.ca/your-government/elections-2026/candidate-information/",
    # Also moved hosts (elections.eastgwillimbury.ca -> electionseg.ca, seen
    # 2026-08-08). That redirect still preserves the path and returns the
    # full list, so this was pre-emptive: pointing at the canonical address
    # rather than relying on a redirect that may later degrade the way
    # Markham's and Whitchurch-Stouffville's did.
    "East Gwillimbury": "https://www.electionseg.ca/candidates/registered-candidates/",
    "King": "https://www.king.ca/candidates",
    # Candidate names are in the static HTML inside "pod" divs (no tables,
    # no filing dates published) — parsed by scrape_whitchurch_stouffville.
    # Moved off stouffvillevotes.ca to townofws.ca (2026-08-08); the old host
    # 301s the candidate list to a contentless landing page, which the
    # scraper read as "0 candidates" without complaining. Same failure mode
    # as Markham's domain change — see the zero-yield guard below.
    "Whitchurch-Stouffville": "https://townofws.ca/candidates/list-of-candidates/",
    # Markham moved the list onto the City site (2026-08-08). The old
    # electionsmarkham.ca host is dead and was bot-blocked (Reblaze JS
    # challenge), which had forced an archive-snapshot route that went stale
    # and silently dropped live candidates. markham.ca answers a plain
    # server-side request with the full list, so it is scraped directly.
    # No filing dates are published, so registration_date stays null.
    "Markham": "https://www.markham.ca/elections/candidates-and-third-party-advertisers/whos-running",
    # Blocked (403 Forbidden — WAF rejects non-browser clients regardless of
    # user-agent; server-side fetchers AND the Wayback crawler are blocked
    # too, so there is no automated path; needs manual checks).
    "Vaughan": "https://www.vaughan.ca/council/elections/candidates",
}

# Municipalities with a working, verified extraction path.
SCRAPABLE_MUNICIPALITIES = {
    "Georgina", "Richmond Hill", "Newmarket", "Aurora", "East Gwillimbury", "King",
    "Whitchurch-Stouffville", "Markham",
}

# Populated per-run by fetch_all_candidates: municipalities that used to
# yield candidates and now yield none. Surfaced in metadata.json so a
# silently-broken extractor is visible instead of looking like an empty field.
SCRAPE_WARNINGS: list[dict] = []

# Hard safeguards against the failure mode that produced 330 garbage records:
# any candidate extracted must have a real office and belong to a known
# municipality, and a single municipality producing an implausible number of
# "candidates" is treated as a scraper bug, not real data.
# Ward councillor races are deliberately NOT collected (decision,
# 2026-07-06): the dashboard tracks only the 21 seats on York Regional
# Council — 9 Mayors + 12 Regional Councillors.
VALID_OFFICES = {"mayor", "regional councillor"}
KNOWN_MUNICIPALITIES = set(MUNICIPALITY_URLS.keys())
MAX_CANDIDATES_PER_MUNICIPALITY = 30
# A candidate/nomination list page should contain at least one of these terms
# somewhere in its text; if it doesn't, this almost certainly isn't a real
# candidate list yet (e.g. a generic "how elections work" info page) and
# extraction should be skipped rather than run against the wrong content.
PAGE_MARKER_TERMS = ["candidate", "nomination", "nominee"]

TRUSTEE_MARKERS = ("trustee", "school board", "conseil scolaire")
WARD_WORD_NUMBERS = {
    "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8",
}
# Rows whose "name" cell is actually placeholder text, not a person.
NON_CANDIDATE_NAME_MARKERS = ("no registered candidates", "no candidates", "tbd", "n/a")


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text


def normalize_name(raw: str) -> str:
    """Some municipalities list names as 'Last, First' — normalize to 'First Last'."""
    raw = re.sub(r"\s+", " ", raw).strip()
    if "," in raw:
        last, _, first = raw.partition(",")
        first, last = first.strip(), last.strip()
        if first and last:
            return f"{first} {last}"
    return raw


def parse_office_ward(heading: str) -> Optional[tuple[str, Optional[str]]]:
    """
    Map a page heading like "Ward 1 Councillor" or "Deputy Mayor and Regional
    Councillor" to (office, ward). Returns None for trustee/school-board
    headings or anything unrecognized — those aren't in our seat model and
    must not be guessed at.
    """
    text = heading.strip().lower()
    if any(marker in text for marker in TRUSTEE_MARKERS):
        return None

    if "mayor" in text and "regional" not in text and "deputy" not in text:
        return ("Mayor", None)

    if "regional" in text or "deputy mayor" in text:
        return ("Regional Councillor", None)

    m = re.search(r"ward[,\s]+([a-z0-9]+)", text) or re.search(r"([a-z0-9]+)[\s-]+ward", text)
    if m:
        raw = m.group(1)
        ward_num = WARD_WORD_NUMBERS.get(raw, raw if raw.isdigit() else None)
        if ward_num:
            return ("Ward Councillor", ward_num)

    if "councillor" in text:
        return ("Ward Councillor", None)

    return None


def fetch_page(url: str, timeout: int = 15) -> Optional[BeautifulSoup]:
    """
    Fetch a URL and return a BeautifulSoup object, or None on failure.

    Also reports cross-host redirects. Twice now (Markham, then
    Whitchurch-Stouffville) a municipality has moved its election site to a
    new domain and 301'd the old candidate-list URL to a contentless landing
    page — an HTTP 200 that yields zero candidates and no error. The
    redirect is the earliest visible symptom, so it is logged loudly.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        if urlparse(resp.url).netloc != urlparse(url).netloc:
            logger.error(
                "REDIRECTED OFF-HOST: %s -> %s. The municipality likely moved "
                "its election site; update MUNICIPALITY_URLS to the new address.",
                url, resp.url,
            )
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


def _is_plausible_name(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 60:
        return False
    lowered = name.lower()
    if any(marker in lowered for marker in NON_CANDIDATE_NAME_MARKERS):
        return False
    if len(name.split()) > 6:
        return False
    return True


def _find_column_indices(header_cells: list[str]) -> tuple[Optional[int], Optional[int]]:
    """Locate the name and filing-date columns from a table's header row text."""
    name_idx = next((i for i, h in enumerate(header_cells) if "name" in h), None)
    date_idx = next(
        (i for i, h in enumerate(header_cells) if "date" in h or "filed" in h or "registered" in h),
        None,
    )
    return name_idx, date_idx


_WITHDRAWN_SUFFIX = re.compile(r"\s*[-–—]\s*withdrawn\s*$", re.IGNORECASE)


def _build_record(
    municipality: str, office: str, ward: Optional[str], raw_name: str,
    date_filed: Optional[str], source_url: str, now_iso: str,
) -> Optional[dict]:
    withdrawn = bool(_WITHDRAWN_SUFFIX.search(raw_name))
    raw_name = _WITHDRAWN_SUFFIX.sub("", raw_name)

    name = normalize_name(raw_name)
    if not _is_plausible_name(name):
        return None
    if municipality not in KNOWN_MUNICIPALITIES or office.lower() not in VALID_OFFICES:
        return None

    return {
        "name": name,
        "municipality": municipality,
        "office": office,
        "ward": ward,
        "date_filed": date_filed,
        "filing_source": source_url,
        "scraped_at": now_iso,
        "withdrawn": withdrawn,
    }


def extract_from_heading_tables(soup: BeautifulSoup, municipality: str, source_url: str) -> list[dict]:
    """
    Shared extraction for municipalities that publish one heading (h1-h4)
    immediately followed by one flat table per office (Georgina, Newmarket,
    Aurora, East Gwillimbury) — column order/wording varies, so name/date
    columns are located dynamically from each table's own header row rather
    than assumed by position.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_candidates = []
    current_office_ward = None

    for el in soup.find_all(["h1", "h2", "h3", "h4", "table"]):
        if el.name == "table":
            if current_office_ward is None:
                continue
            office, ward = current_office_ward
            rows = el.find_all("tr")
            if not rows:
                continue
            header_cells = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
            name_idx, date_idx = _find_column_indices(header_cells)
            if name_idx is None:
                continue
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) <= name_idx:
                    continue
                raw_name = cells[name_idx].get_text(strip=True)
                date_filed = cells[date_idx].get_text(strip=True) if date_idx is not None and date_idx < len(cells) else None
                rec = _build_record(municipality, office, ward, raw_name, date_filed, source_url, now_iso)
                if rec:
                    raw_candidates.append(rec)
        else:
            heading_text = el.get_text(strip=True)
            if heading_text:
                current_office_ward = parse_office_ward(heading_text)

    return raw_candidates


def scrape_richmond_hill(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """
    Richmond Hill nests each office's real data table (class="datatable")
    inside an accordion structure: an outer table whose first row
    (td[data-name="accParent"]) holds the office name, and whose second row
    (td[data-name="accChild"]) contains the actual candidate table.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_candidates = []

    for datatable in soup.find_all("table", class_="datatable"):
        acc_row = datatable.find_parent("td", attrs={"data-name": "accChild"})
        if acc_row is None:
            continue
        parent_row_td = acc_row.find_parent("tr").find_previous_sibling("tr")
        if parent_row_td is None:
            continue
        heading_td = parent_row_td.find("td", attrs={"data-name": "accParent"})
        if heading_td is None:
            continue
        office_ward = parse_office_ward(heading_td.get_text(strip=True))
        if office_ward is None:
            continue
        office, ward = office_ward

        rows = datatable.find_all("tr")
        if not rows:
            continue
        header_cells = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
        name_idx, date_idx = _find_column_indices(header_cells)
        if name_idx is None:
            continue
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= name_idx:
                continue
            raw_name = cells[name_idx].get_text(strip=True)
            date_filed = cells[date_idx].get_text(strip=True) if date_idx is not None and date_idx < len(cells) else None
            rec = _build_record("Richmond Hill", office, ward, raw_name, date_filed, source_url, now_iso)
            if rec:
                raw_candidates.append(rec)

    return raw_candidates


# King's page groups all municipal-office tables under one shared heading
# ("Municipal Office Candidates") with no per-office label in the HTML — the
# office identity is only recoverable by position. Verified 2026-07-02 against
# King's real page: this order matched every known 2022 incumbent's ward
# (Pellegrini=Mayor, Cescolini=Ward1, Boyd=Ward2, Anstey=Ward3, Eek=Ward6).
# Fragile to King changing their page layout — re-verify if extraction ever
# starts producing implausible results for King.
KING_TABLE_OFFICE_ORDER = [
    ("Mayor", None), ("Ward Councillor", "1"), ("Ward Councillor", "2"),
    ("Ward Councillor", "3"), ("Ward Councillor", "4"), ("Ward Councillor", "5"),
    ("Ward Councillor", "6"),
]


def scrape_king(soup: BeautifulSoup, source_url: str) -> list[dict]:
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_candidates = []

    heading = soup.find(lambda tag: tag.name in ("h2", "h3") and "Municipal Office Candidates" in tag.get_text())
    if heading is None:
        return []
    container = heading.find_parent()
    if container is None:
        return []

    tables = container.find_all("table")[:len(KING_TABLE_OFFICE_ORDER)]
    for (office, ward), table in zip(KING_TABLE_OFFICE_ORDER, tables):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
        name_idx, date_idx = _find_column_indices(header_cells)
        if name_idx is None:
            continue
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= name_idx:
                continue
            raw_name = cells[name_idx].get_text(strip=True)
            date_filed = cells[date_idx].get_text(strip=True) if date_idx is not None and date_idx < len(cells) else None
            rec = _build_record("King", office, ward, raw_name, date_filed, source_url, now_iso)
            if rec:
                raw_candidates.append(rec)

    return raw_candidates


def scrape_whitchurch_stouffville(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """
    stouffvillevotes.ca publishes candidates in "pod" content blocks, not
    tables: each block has an office heading (h2.h5) followed by <p> elements
    with the candidate's name in <strong>. No filing dates are published on
    this page, so date_filed stays None (appearing on the official certified
    list still confirms the filing itself).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_candidates = []

    for pod in soup.find_all("div", class_="pod__text"):
        heading = pod.find(["h2", "h3"])
        if heading is None:
            continue
        office_ward = parse_office_ward(heading.get_text(strip=True))
        if office_ward is None:
            continue
        office, ward = office_ward

        for p in pod.find_all("p"):
            for strong in p.find_all("strong"):
                rec = _build_record(
                    "Whitchurch-Stouffville", office, ward,
                    strong.get_text(strip=True), None, source_url, now_iso,
                )
                if rec:
                    raw_candidates.append(rec)

    return raw_candidates


def scrape_markham(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """
    Markham's "Who's Running" page: one table per office, with the office name
    in a preceding accordion element (<dt>) rather than inside the table. No
    filing-date column is published, so registration_date stays None for every
    Markham candidate — that is the city's choice, not a scraper gap.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_candidates = []

    def is_office_label(tag):
        # markham.ca renders each office as a <dt> in a <dl class="ckeditor-accordion">
        # with the candidate table in the following <dd>; the older
        # electionsmarkham.ca layout used headings/buttons.
        if tag.name in ("h2", "h3", "h4", "button", "summary", "dt"):
            return True
        classes = tag.get("class") or []
        return tag.name == "div" and any(
            "accordion" in c.lower() or "title" in c.lower() or "header" in c.lower()
            for c in classes
        )

    for table in soup.find_all("table"):
        label_el = table.find_previous(is_office_label)
        if label_el is None:
            continue
        office_ward = parse_office_ward(label_el.get_text(strip=True))
        if office_ward is None:
            continue
        office, ward = office_ward

        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
        name_idx, date_idx = _find_column_indices(header_cells)
        if name_idx is None:
            continue
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= name_idx:
                continue
            raw_name = cells[name_idx].get_text(strip=True)
            date_filed = cells[date_idx].get_text(strip=True) if date_idx is not None and date_idx < len(cells) else None
            rec = _build_record("Markham", office, ward, raw_name, date_filed, source_url, now_iso)
            if rec:
                raw_candidates.append(rec)

    return raw_candidates


SCRAPERS = {
    "Georgina": extract_from_heading_tables,
    "Newmarket": extract_from_heading_tables,
    "Aurora": extract_from_heading_tables,
    "East Gwillimbury": extract_from_heading_tables,
    "Richmond Hill": lambda soup, muni, url: scrape_richmond_hill(soup, url),
    "King": lambda soup, muni, url: scrape_king(soup, url),
    "Whitchurch-Stouffville": lambda soup, muni, url: scrape_whitchurch_stouffville(soup, url),
    "Markham": lambda soup, muni, url: scrape_markham(soup, url),
}


def _seat_incumbent_names(seats: list[dict], candidates_by_id: dict[str, dict]) -> dict[str, str]:
    """Map seat_id -> current incumbent's name, for recognizing returning incumbents."""
    result = {}
    for seat in seats:
        cid = seat.get("incumbent_candidate_id")
        cand = candidates_by_id.get(cid)
        if cand:
            result[seat["id"]] = cand["name"]
    return result


def _match_seats(seats: list[dict], municipality: str, office: str, ward: Optional[str]) -> list[dict]:
    return [
        s for s in seats
        if s["municipality"] == municipality and s["office"] == office and s.get("ward") == ward
    ]


def reconcile_scraped_candidates(
    raw_candidates: list[dict], existing_candidates: list[dict], seats: list[dict],
    scraped_municipalities: Optional[set[str]] = None,
) -> list[dict]:
    """
    Turn raw (name, municipality, office, ward, date_filed) tuples into full
    candidate records, matched against seats.json:
      - Name matches a seat's current incumbent -> update that existing
        candidate record (filed_for_reelection=confirmed) rather than create
        a duplicate.
      - No match -> new challenger record, linked to the contested seat_id
        where determinable.
      - Previously-registered candidate who has VANISHED from a municipality
        we scraped successfully -> treated as a withdrawal (see below).

    scraped_municipalities is the set that returned candidates this run. Only
    those are eligible for withdrawal detection: a municipality that failed to
    fetch, or whose extractor broke and returned nothing, must never be read
    as "everybody withdrew".
    """
    candidates_by_id = {c["id"]: c for c in existing_candidates}
    incumbent_names_by_seat = _seat_incumbent_names(seats, candidates_by_id)

    updated = {c["id"]: dict(c) for c in existing_candidates}
    seat_taken_by_challenger: dict[str, int] = {}
    seen_ids: set[str] = set()

    for rc in raw_candidates:
        matched_seats = _match_seats(seats, rc["municipality"], rc["office"], rc["ward"])
        name_lower = rc["name"].strip().lower()

        incumbent_seat = next(
            (s for s in matched_seats if incumbent_names_by_seat.get(s["id"], "").strip().lower() == name_lower),
            None,
        )

        if incumbent_seat is not None:
            cid = incumbent_seat["incumbent_candidate_id"]
            existing = updated.get(cid, {})
            existing["filed_for_reelection"] = "declined" if rc["withdrawn"] else "confirmed"
            existing["filing_source"] = rc["filing_source"]
            existing["registered"] = not rc["withdrawn"]
            existing["registration_date"] = rc["date_filed"]
            existing["source"] = "scraped"
            existing["scraped_at"] = rc["scraped_at"]
            # first_seen_at must survive re-scrapes — it's what "newly
            # detected filing" alerts key off, unlike scraped_at (last seen).
            existing.setdefault("first_seen_at", rc["scraped_at"])
            if rc["withdrawn"]:
                existing["fiscal_notes"] = (existing.get("fiscal_notes") or "") + " Filed then withdrew nomination."
            else:
                existing.pop("withdrawal_basis", None)
                existing.pop("withdrawn_detected_at", None)
            existing.pop("absent_from_source_since", None)
            updated[cid] = existing
            seen_ids.add(cid)
            continue

        if rc["withdrawn"]:
            # A withdrawn filing from someone who wasn't a current incumbent
            # isn't worth creating a permanent candidate record for.
            continue

        cid = make_challenger_id(rc["municipality"], rc["office"], rc["ward"], rc["name"])
        seen_ids.add(cid)

        if cid in updated:
            # Known challenger re-observed on a later scrape: refresh only the
            # scrape-owned fields. Rebuilding the whole record here would reset
            # first_seen_at every run (making every candidate look "new"
            # forever) and would discard any manual edits.
            existing = updated[cid]
            existing["filing_source"] = rc["filing_source"]
            existing["registered"] = True
            # Back on the clerk's list: undo any withdrawal we had recorded.
            # Without this a candidate who was briefly missing (or genuinely
            # withdrew and re-filed before nomination day) would stay
            # "declined" while showing as registered — a contradictory record
            # that the lame-duck count reads on the wrong side.
            existing["filed_for_reelection"] = "confirmed"
            existing.pop("withdrawal_basis", None)
            existing.pop("withdrawn_detected_at", None)
            existing["registration_date"] = rc["date_filed"]
            existing["scraped_at"] = rc["scraped_at"]
            existing.setdefault("first_seen_at", rc["scraped_at"])
            continue

        # New challenger. Multi-seat Regional Councillor races (Markham 4,
        # Vaughan 4, Richmond Hill 2) are elected at-large — top-N vote-getters
        # win, so a challenger contests the whole pool, not any one incumbent's
        # numbered seat. Pool them under a synthetic <muni>-regional-at-large
        # id (the dashboard renders these under the municipality block, not on
        # a tile). Single-seat RC races (Georgina, Newmarket) are genuine
        # head-to-heads and keep a direct seat assignment, as do any other
        # multi-seat offices (round-robin spread).
        seat_id = None
        at_large_pool = False
        if rc["office"] == "Regional Councillor" and len(matched_seats) > 1:
            seat_id = f"{slugify(rc['municipality'])}-regional-at-large"
            at_large_pool = True
        elif matched_seats:
            idx = seat_taken_by_challenger.get(
                f"{rc['municipality']}|{rc['office']}|{rc['ward']}", 0
            ) % len(matched_seats)
            seat_id = matched_seats[idx]["id"]
            seat_taken_by_challenger[f"{rc['municipality']}|{rc['office']}|{rc['ward']}"] = idx + 1

        updated[cid] = {
            "id": cid,
            "seat_id": seat_id,
            "at_large_pool": at_large_pool,
            "name": rc["name"],
            "municipality": rc["municipality"],
            "office": rc["office"],
            "ward": rc["ward"],
            "status": "challenger",
            "filed_for_reelection": "confirmed",
            "filing_source": rc["filing_source"],
            "registered": True,
            "registration_date": rc["date_filed"],
            "fiscal_alignment_score": 5,
            "fiscal_alignment_label": "neutral",
            "fiscal_alignment_basis": "unscored",
            "fiscal_notes": "",
            "news_mentions": 0,
            "last_news_date": None,
            "likely_to_run_again": None,
            "likely_to_win": None,
            "source": "scraped",
            "scraped_at": rc["scraped_at"],
            "first_seen_at": rc["scraped_at"],
        }

    _mark_vanished_as_withdrawn(updated, seen_ids, scraped_municipalities or set())
    return list(updated.values())


def _mark_vanished_as_withdrawn(
    updated: dict[str, dict], seen_ids: set[str], scraped_municipalities: set[str],
) -> None:
    """
    Withdrawal detection. Most clerks do not annotate a withdrawal — they simply
    delete the candidate from the published list. Reconciliation carries every
    known record forward and only touches the ones it just scraped, so without
    this a withdrawn candidate would stay `registered: true` forever. That
    matters beyond cosmetics: the lame-duck calculation counts confirmed
    filings against a 17-of-22 threshold, so a missed withdrawal can report the
    council on the safe side of a statutory line it has actually crossed.

    Two-run confirmation, deliberately: a single absence can be a transient
    half-rendered page or a name the extractor briefly failed to parse, and
    silently deleting a real filing is worse than reporting it a couple of
    hours late. First absence only records `absent_from_source_since`; the
    second consecutive absence flips the record. Reappearing clears the mark.

    Only municipalities that actually returned candidates this run are
    eligible — a failed fetch or a broken extractor must never read as
    "everyone withdrew". Vaughan is therefore never touched here (it has no
    server-side scrape); its filings come from manual_overrides.json, which
    main.py applies after this and which always wins.
    """
    for cid, cand in updated.items():
        if cand.get("municipality") not in scraped_municipalities:
            continue
        if cid in seen_ids:
            cand.pop("absent_from_source_since", None)
            continue
        if not cand.get("registered"):
            continue

        first_absent = cand.get("absent_from_source_since")
        if not first_absent:
            cand["absent_from_source_since"] = datetime.now(timezone.utc).isoformat()
            logger.warning(
                "%s (%s) is registered but absent from %s's list this run — "
                "flagged; a second consecutive absence will mark it withdrawn.",
                cand.get("name"), cand.get("office"), cand.get("municipality"),
            )
            continue

        logger.error(
            "WITHDRAWAL DETECTED: %s (%s, %s) has been absent from the clerk's "
            "published list since %s — marking as withdrawn.",
            cand.get("name"), cand.get("municipality"), cand.get("office"), first_absent,
        )
        cand["registered"] = False
        cand["filed_for_reelection"] = "declined"
        cand["withdrawn_detected_at"] = datetime.now(timezone.utc).isoformat()
        cand["withdrawal_basis"] = (
            f"Removed from the clerk's published candidate list (first absent {first_absent[:10]})"
        )


def make_challenger_id(municipality: str, office: str, ward: Optional[str], name: str) -> str:
    parts = [slugify(municipality), slugify(office)]
    if ward:
        parts.append(slugify(ward))
    parts.append(slugify(name))
    return "-".join(parts)


def _municipalities_with_prior_filings(existing_candidates: list[dict]) -> set[str]:
    """
    Municipalities that a previous run already found registered candidates
    for. Used by the zero-yield guard: for these, extracting nothing is a
    regression, not an empty field.
    """
    return {
        c.get("municipality")
        for c in existing_candidates
        if c.get("registered") or c.get("filed_for_reelection") == "confirmed"
    }


def fetch_all_candidates(existing_candidates: list[dict], seats: list[dict]) -> list[dict]:
    """
    Main entry point: scrape all verified municipalities, reconcile against
    seats.json (recognizing returning incumbents vs. new challengers), and
    return the merged candidate list. Unscrapable municipalities (bot-blocked
    or JS-rendered) are left untouched — existing/seeded data for them is
    preserved as-is.

    Populates SCRAPE_WARNINGS with any municipality that silently stopped
    yielding candidates (see the zero-yield guard below); main.py records it
    in metadata.json so the failure is inspectable rather than invisible.
    """
    all_raw = []
    # Municipalities that actually produced candidates this run — the only ones
    # eligible for withdrawal detection (see _mark_vanished_as_withdrawn).
    scraped_ok: set[str] = set()
    SCRAPE_WARNINGS.clear()
    had_filings_before = _municipalities_with_prior_filings(existing_candidates)

    def warn(municipality: str, reason: str) -> None:
        """A scrapable municipality produced nothing this run — say so loudly."""
        if municipality in had_filings_before:
            logger.error(
                "ZERO-YIELD REGRESSION: %s previously had registered candidates but "
                "produced none this run (%s). Stale data is being served — check "
                "whether the clerk's page moved or changed structure.",
                municipality, reason,
            )
            SCRAPE_WARNINGS.append({"municipality": municipality, "reason": reason})
        else:
            logger.info("%s produced no candidates (%s)", municipality, reason)

    for municipality in SCRAPABLE_MUNICIPALITIES:
        url = MUNICIPALITY_URLS[municipality]
        source_url = url

        logger.info("Scraping %s from %s", municipality, url)
        soup = fetch_page(url)

        if soup is None:
            logger.warning("Skipping %s — page fetch failed", municipality)
            warn(municipality, "page fetch failed")
            continue
        if not page_looks_like_candidate_list(soup):
            logger.warning("%s page doesn't look like a candidate list — skipping", municipality)
            warn(municipality, "page no longer looks like a candidate list")
            continue

        scraper_fn = SCRAPERS.get(municipality)
        if scraper_fn is None:
            continue

        try:
            raw = scraper_fn(soup, municipality, source_url)
        except Exception as exc:
            logger.error("Scraper error for %s: %s", municipality, exc)
            warn(municipality, f"scraper raised {type(exc).__name__}")
            continue

        if len(raw) > MAX_CANDIDATES_PER_MUNICIPALITY:
            logger.error(
                "%s scrape produced %d candidates (cap %d) — treating as a scraper bug, discarding this run's results",
                municipality, len(raw), MAX_CANDIDATES_PER_MUNICIPALITY,
            )
            warn(municipality, f"candidate cap exceeded ({len(raw)} > {MAX_CANDIDATES_PER_MUNICIPALITY})")
            continue

        # The page fetched and parsed, but nothing came out. If this
        # municipality had registered candidates before, the extractor has
        # silently broken (the Markham/Whitchurch-Stouffville domain-move
        # failure mode) and the dashboard is about to serve stale data.
        if not raw:
            warn(municipality, "page parsed but extracted 0 candidates")
            continue

        logger.info("Found %d candidates for %s", len(raw), municipality)
        all_raw.extend(raw)
        scraped_ok.add(municipality)

    merged = reconcile_scraped_candidates(all_raw, existing_candidates, seats, scraped_ok)
    logger.info("Total candidates after merge: %d", len(merged))
    return merged
