#!/usr/bin/env python3
"""Detect roster changes between two candidates.json snapshots.

Compares the candidates.json from *before* a scraper run against the one
*after* it and reports everything that changed on the Regional Council roster:

  - NEW REGISTRATIONS — filing status flipped to registered (a brand-new filed
    candidate, or a sitting member who has now filed).
  - WITHDRAWALS — filing status flipped the other way, either because the clerk
    annotated the name "- Withdrawn" or because the candidate vanished from the
    published list for two consecutive runs (see _mark_vanished_as_withdrawn in
    fetch_candidates.py). Withdrawals move the lame-duck count DOWN toward the
    17-of-22 threshold, so they matter at least as much as filings.
  - SCRAPE WARNINGS — a municipality that used to yield candidates and now
    yields none. Reported here so a silently broken extractor surfaces in the
    same place as real news instead of only in the run log.

This makes the bot's own output the monitoring channel: the one-line summary
goes into the commit message (so `git log` reads as a change feed) and, when
anything is present, the workflow opens an Issue that emails the maintainer.
Quiet runs print nothing at all — no news is genuinely no news.

Usage:
    python detect_new_registrations.py <before.json> <after.json> <body_out.md>
                                       [<metadata.json>]

Prints a one-line summary to stdout when something changed (empty otherwise),
and writes a Markdown issue body to <body_out.md>.
"""
import json
import sys


def is_filed(c: dict) -> bool:
    if not c:
        return False
    return bool(c.get("registered")) or c.get("filed_for_reelection") == "confirmed"


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return {c["id"]: c for c in json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _sort_key(c: dict):
    return (c.get("municipality", ""), c.get("office", ""), c.get("name", ""))


def main() -> int:
    before = load(sys.argv[1])
    after = load(sys.argv[2])
    body_out = sys.argv[3]

    warnings = []
    if len(sys.argv) > 4:
        try:
            with open(sys.argv[4], encoding="utf-8") as f:
                warnings = json.load(f).get("data_confidence", {}).get("scrape_warnings", []) or []
        except (FileNotFoundError, json.JSONDecodeError, AttributeError):
            warnings = []

    new_regs, withdrawals = [], []
    for cid, cand in after.items():
        was, now = is_filed(before.get(cid)), is_filed(cand)
        if now and not was:
            new_regs.append(cand)
        # Only count a flip for someone we already knew about: an unfiled
        # candidate appearing for the first time is not a withdrawal.
        elif was and not now and cid in before:
            withdrawals.append(cand)

    if not (new_regs or withdrawals or warnings):
        return 0  # nothing to report; stdout stays empty

    new_regs.sort(key=_sort_key)
    withdrawals.sort(key=_sort_key)

    bits = []
    if new_regs:
        bits.append(f"+{len(new_regs)} filed: " + ", ".join(
            f"{c.get('name')} ({c.get('municipality')})" for c in new_regs))
    if withdrawals:
        bits.append(f"-{len(withdrawals)} WITHDRAWN: " + ", ".join(
            f"{c.get('name')} ({c.get('municipality')})" for c in withdrawals))
    if warnings:
        bits.append(f"{len(warnings)} scraper warning(s): " + ", ".join(
            w.get("municipality", "?") for w in warnings))
    summary = " | ".join(bits)

    lines = ["The 2-hour scraper detected changes to the York Regional Council roster:", ""]

    if new_regs:
        lines += ["### Newly registered", ""]
        for c in new_regs:
            status = "incumbent filed for re-election" if c.get("status") == "incumbent" else "new candidate"
            date = c.get("registration_date") or "filing date not published"
            lines.append(
                f"- **{c.get('name')}** — {c.get('municipality')} · {c.get('office')} "
                f"— _{status}_ ({date})"
            )
        lines.append("")

    if withdrawals:
        lines += [
            "### Withdrawn",
            "",
            "_This lowers the count of members continuing to the new council — "
            "check the lame-duck threshold (17 of 22)._",
            "",
        ]
        for c in withdrawals:
            basis = c.get("withdrawal_basis") or "no longer listed as registered"
            lines.append(
                f"- **{c.get('name')}** — {c.get('municipality')} · {c.get('office')} — _{basis}_"
            )
        lines.append("")

    if warnings:
        lines += [
            "### Scraper warnings",
            "",
            "_A municipality that previously returned candidates returned none. "
            "The dashboard is serving its last known data for it — most likely the "
            "clerk's site moved or changed structure._",
            "",
        ]
        for w in warnings:
            lines.append(f"- **{w.get('municipality')}** — {w.get('reason')}")
        lines.append("")

    lines += [
        "Dashboard: https://yrmuni2026.wordi.ca",
        "",
        "_Auto-filed by the update_data workflow. Close this issue once you've noted it._",
    ]

    with open(body_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
