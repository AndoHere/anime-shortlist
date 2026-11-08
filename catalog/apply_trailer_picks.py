"""Copy hand-found trailers from data/trailer_search_picks.json into the curated company files.

The picks file maps a title (English name as shown on the page) to a YouTube video id, or null when a search
found nothing usable. Run build.py afterwards; every id is still checked against YouTube before it is used.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, load_json, save_json  # noqa: E402
from companies import COMPANIES  # noqa: E402

picks = load_json(os.path.join(DATA, "trailer_search_picks.json"), {})
rows = load_json(os.path.join(DATA, "titles.json"), [])
by_title = {r["t"]: r for r in rows}
slug_of = {c.NAME: c.SLUG for c in COMPANIES}
changed, missing = 0, []
curated = {}
for title, vid in picks.items():
    if title.startswith("_") or not vid:
        continue
    r = by_title.get(title)
    if not r:
        missing.append(title)
        continue
    slug = slug_of[r["co"]]
    if slug not in curated:
        curated[slug] = load_json(os.path.join(DATA, "curated", slug + ".json"), {})
    entry = curated[slug].setdefault(r["id"], {})
    if entry.get("trailer") != vid:
        entry["trailer"], entry["trailerSrc"] = vid, "web search"
        changed += 1
for slug, data in curated.items():
    save_json(os.path.join(DATA, "curated", slug + ".json"), data)
print(f"{changed} trailers written; titles not found: {missing or 'none'}")
