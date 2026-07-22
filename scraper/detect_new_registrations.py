#!/usr/bin/env python3
"""Detect newly-registered Regional Council candidates between two snapshots.

Compares the candidates.json from *before* a scraper run against the one
*after* it, and reports candidates whose filing status just flipped to
registered — either a brand-new filed candidate or a sitting member who has
now filed. Used by the update_data workflow to open a GitHub Issue (which
emails the maintainer) when a new registration appears.

Usage:
    python detect_new_registrations.py <before.json> <after.json> <body_out.md>

Prints a one-line summary to stdout when there are new registrations (empty
otherwise), and writes a Markdown issue body to <body_out.md>.
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


def main() -> int:
    before = load(sys.argv[1])
    after = load(sys.argv[2])
    body_out = sys.argv[3]

    new_regs = []
    for cid, cand in after.items():
        if is_filed(cand) and not is_filed(before.get(cid)):
            new_regs.append(cand)

    if not new_regs:
        return 0  # nothing to report; stdout stays empty

    new_regs.sort(key=lambda c: (c.get("municipality", ""), c.get("office", ""), c.get("name", "")))

    names = ", ".join(f"{c.get('name')} ({c.get('municipality')})" for c in new_regs)
    summary = f"{len(new_regs)} new registration(s): {names}"

    lines = [
        "The 2-hour scraper detected **newly registered candidate(s)** for York Regional Council:",
        "",
    ]
    for c in new_regs:
        status = "incumbent filed for re-election" if c.get("status") == "incumbent" else "new candidate"
        date = c.get("registration_date") or "filing date not published"
        lines.append(
            f"- **{c.get('name')}** — {c.get('municipality')} · {c.get('office')} "
            f"— _{status}_ ({date})"
        )
    lines += [
        "",
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
