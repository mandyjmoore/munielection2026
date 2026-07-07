"""Harvest the full motion-level voting record of York Regional Council,
November 2022 inauguration through today, from eScribe minutes.

Keeps: substantive motions, anything with a recorded vote, and procedural
motions that gate substantive outcomes (defer/reconsider/waive-notice/
chair challenges). Drops routine machinery (minutes adoption, receipts,
recesses, private session, confirmatory bylaws) unless recorded.
"""
import json
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://yorkpublishing.escribemeetings.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (research script)", "Content-Type": "application/json"}
from pathlib import Path
OUT = str(Path(__file__).parent.parent / "data" / "voting_record.json")

DISPOSITIONS = re.compile(r"^(Carried(?: by 2/3 majority)?(?: Unanimously)?|Defeated|Withdrawn|Referred.*)$", re.I)
RECORDED_START = re.compile(r"A recorded vote", re.I)  # may appear mid-line after "requires a 2/3 majority vote to carry."
ITEM_HEAD = re.compile(r"^([A-Z]\.\d+(?:\.\d+)?)$")

DROP_PATTERNS = re.compile(
    r"^Council (adopt the minutes|receive the |consent to receive|approve the \d{4} Council and Committee Meeting Calendar"
    r"|resolve into private session|rise and report|proceed into|extend the meeting"
    r"|enact (the )?[Bb]ylaws? .*confirm)", re.I)
GATING_PATTERNS = re.compile(r"(defer consideration|reconsider|overrule the Chair|waive the notice)", re.I)

STAFF_REC = re.compile(
    r"(adopt the following recommendations?|recommendations? (in|from|of) the report dated"
    r"|the report dated [^.]{5,80} from the (Commissioner|Chief|Regional Solicitor|Medical Officer)"
    r"|adopt the .*recommendations? from Committee of the Whole)", re.I)
MEMBER_MOTION = re.compile(r"^(Council amend|Whereas|WHEREAS)|Motion to Amend|Notice of Motion", re.I)


def get_meetings():
    meetings = []
    for year in range(2022, 2027):
        for month in range(1, 13):
            if year == 2022 and month < 11:  # term starts Nov 15, 2022; pre-inauguration meetings filtered below
                continue
            if year == 2026 and month > 7:
                break
            start = f"{year}-{month:02d}-01T00:00:00"
            em, ey = (1, year + 1) if month == 12 else (month + 1, year)
            end = f"{ey}-{em:02d}-01T00:00:00"
            try:
                r = requests.post(f"{BASE}/MeetingsCalendarView.aspx/GetCalendarMeetings",
                                  headers=HEADERS,
                                  data=json.dumps({"calendarStartDate": start, "calendarEndDate": end}),
                                  timeout=25)
                r.raise_for_status()
                for m in r.json().get("d", []):
                    name = m.get("MeetingName") or ""
                    if "Regional Council" in name:
                        meetings.append((m["ID"], name, m.get("StartDate")))
            except Exception as exc:
                print(f"calendar {year}-{month:02d}: FAILED {exc}")
            time.sleep(0.3)
    # dedupe by id
    seen, out = set(), []
    for mid, name, date in meetings:
        if mid not in seen:
            seen.add(mid)
            out.append((mid, name, date))
    return sorted([m for m in out if (m[2] or "").replace("/", "-")[:10] >= "2022-11-15"], key=lambda x: x[2] or "")


def parse_recorded(lines, i):
    """Parse a recorded-vote block starting at lines[i] ('A recorded vote...').
    Returns (dict, next_index)."""
    vote = {"for": [], "against": [], "absent": [], "conflict": []}
    i += 1
    current = None
    while i < len(lines):
        ln = lines[i].strip()
        low = ln.lower()
        m = re.match(r"^(For|Against|Absent|Conflict)\s*(?:\(\d+\))?\s*:?\s*(.*)$", ln, re.I)
        if m:
            current = m.group(1).lower()
            rest = m.group(2)
            if rest:
                vote[current].extend([n.strip() for n in re.sub(r"\(\d+\)", "", rest).split(",") if n.strip()])
        elif DISPOSITIONS.match(ln):
            return vote, i
        elif re.match(r"^\(\d+\)$", ln):
            pass  # count-only line
        elif current and ln and not ln.lower().startswith(("moved by", "seconded by")):
            vote[current].extend([n.strip() for n in re.sub(r"\(\d+\)", "", ln).split(",") if n.strip()])
        else:
            return vote, i - 1
        i += 1
    return vote, i


def parse_meeting(mid, name, date):
    url = f"{BASE}/Meeting.aspx?Id={mid}&Agenda=PostMinutes&lang=English"
    r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)
    r.raise_for_status()
    text = BeautifulSoup(r.text, "lxml").get_text("\n", strip=True)
    lines = [l for l in text.split("\n") if l.strip()]

    motions = []
    current_item = None
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        m = ITEM_HEAD.match(ln)
        if m and i + 1 < len(lines) and len(lines[i + 1]) > 3 and not lines[i + 1].startswith(("Moved", "Seconded")):
            current_item = f"{m.group(1)} {lines[i + 1][:120]}"
            i += 2
            continue

        if ln == "Moved by" and i + 3 < len(lines) and lines[i + 2].strip() == "Seconded by":
            mover, seconder = lines[i + 1].strip(), lines[i + 3].strip()
            j = i + 4
            body = []
            recorded = None
            disposition = None
            while j < len(lines):
                l2 = lines[j].strip()
                if l2 == "Moved by":
                    break
                rm = RECORDED_START.search(l2)
                if rm:
                    # any text before the phrase belongs to the motion body
                    prefix = l2[:rm.start()].strip()
                    if prefix:
                        body.append(prefix)
                    recorded, j = parse_recorded(lines, j)
                    # parse_recorded stops AT the disposition line — consume it
                    # here rather than letting the loop's j += 1 skip past it
                    nxt = lines[j].strip() if j < len(lines) else ""
                    if DISPOSITIONS.match(nxt):
                        disposition = nxt
                        j += 1
                        break
                    continue  # re-evaluate lines[j] without the extra increment
                elif DISPOSITIONS.match(l2):
                    disposition = l2
                    j += 1
                    break
                else:
                    body.append(l2)
                j += 1
            motion_text = " ".join(body).strip()

            keep = True
            if DROP_PATTERNS.match(motion_text) and not recorded:
                keep = False
            if len(motion_text) < 15 and not recorded:
                keep = False
            if GATING_PATTERNS.search(motion_text):
                keep = True

            if keep and (disposition or recorded):
                staff = None
                if STAFF_REC.search(motion_text):
                    staff = True
                elif MEMBER_MOTION.search(motion_text) or (current_item and 'Motion' in current_item.split(' ', 1)[-1][:30]):
                    staff = False
                if recorded and not disposition:
                    # Minutes sometimes phrase outcomes non-standardly
                    # ("Challenge is defeated") or omit the word entirely;
                    # for recorded votes the tally determines it (simple
                    # majority; flagged as derived for honesty).
                    disposition = ("Carried" if len(recorded["for"]) > len(recorded["against"]) else "Defeated") + " (derived from tally)"
                motions.append({
                    "item": current_item,
                    "mover": mover,
                    "seconder": seconder,
                    "text": motion_text[:2400],
                    "disposition": disposition or ("Recorded" if recorded else "Unknown"),
                    "vote_type": "recorded" if recorded else "voice",
                    "recorded_vote": recorded,
                    "staff_recommended": staff,
                })
            i = j
            continue
        i += 1
    return motions


def main():
    meetings = get_meetings()
    print(f"meetings found: {len(meetings)}")
    record = []
    for mid, name, date in meetings:
        try:
            motions = parse_meeting(mid, name, date)
        except Exception as exc:
            print(f"{date} {name}: FAILED {exc}")
            continue
        iso = (date or "").replace("/", "-")[:10]
        record.append({
            "meeting": name,
            "date": iso,
            "url": f"{BASE}/Meeting.aspx?Id={mid}&Agenda=PostMinutes&lang=English",
            "motions": motions,
        })
        rec_n = sum(1 for m in motions if m["vote_type"] == "recorded")
        print(f"{iso} {name}: {len(motions)} motions kept ({rec_n} recorded)")
        time.sleep(0.4)

    total = sum(len(m["motions"]) for m in record)
    recorded = sum(1 for mtg in record for m in mtg["motions"] if m["vote_type"] == "recorded")
    out = {
        "_generated": time.strftime("%Y-%m-%d"),
        "_scope": "York Regional Council motions since the Nov 2022 inauguration. Routine procedural motions (minutes, receipts, recesses, private session, confirmatory bylaws) are excluded unless they went to a recorded vote; deferrals/reconsiderations/chair challenges are kept. staff_recommended is INFERRED from motion structure (adopting a staff report or CoW recommendation), null = undetermined.",
        "meetings": record,
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"TOTAL: {total} motions across {len(record)} meetings ({recorded} recorded votes) -> voting_record.json")


if __name__ == "__main__":
    main()
