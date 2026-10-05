#!/usr/bin/env python3
"""Check the paste-ready Play listing (LW-M6-12): field lengths and trademark use.

Reads listing-en-US.md next to this file. The three ```text blocks under the
"App name", "Short description" and "Full description" headings are the fields.
Limits: title 30 (Play metadata policy), short 80 and full 4000 (Play Console).
The title and short description must not name Firefox, Mozilla or LibreWolf
(Mozilla trademark policy: no Mozilla marks in the product name); the full
description must carry the non-affiliation statement.
"""
import re
import sys
from pathlib import Path

text = (Path(__file__).resolve().parent / "listing-en-US.md").read_text(encoding="utf-8")


def field(heading):
    m = re.search(r"^## " + re.escape(heading) + r"\s*\n+```text\n(.*?)\n```", text, re.S | re.M)
    if not m:
        sys.exit(f"check-listing: no ```text block under '## {heading}'")
    return m.group(1)


title, short, full = field("App name (title)"), field("Short description"), field("Full description")
problems = []
for name, value, limit in (("title", title, 30), ("short", short, 80), ("full", full, 4000)):
    print(f"{name:6} {len(value):5} / {limit}")
    if len(value) > limit:
        problems.append(f"{name} is {len(value)} characters, limit {limit}")
for name, value in (("title", title), ("short", short)):
    if re.search(r"firefox|mozilla|librewolf", value, re.I):
        problems.append(f"{name} names a third-party mark")
    if re.search(r"\b(best|#1|top|free)\b", value, re.I):
        problems.append(f"{name} carries a ranking/promotional word")
if "not officially associated with Mozilla" not in full:
    problems.append("full description lacks the Mozilla non-affiliation statement")
if re.search(r"[\U0001F300-\U0001FAFF]", title + short + full):
    problems.append("emoji in the listing")
for p in problems:
    print("FAIL " + p)
sys.exit(1 if problems else 0)
