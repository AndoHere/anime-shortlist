"""Puts MyAnimeList results onto the page without the company-site cache.

    python catalog/apply_mal.py

Reads data/titles.json (the last build) and data/cache/mal.json (from mal_scrape.py), updates each anime
card's MAL row and fills gaps the match can fill (Japanese title, English title when it only has the Japanese
one, romaji, year), writes data/titles.json and re-renders ../animated-titles.html from template.html.
Unlike build.py it needs no company pages, so it also runs on GitHub. Trailers are left as they are.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, is_anime, load_json, save_json  # noqa: E402
import build  # noqa: E402
import mal  # noqa: E402


def main():
    rows = load_json(os.path.join(DATA, "titles.json"), [])
    cache = load_json(mal.CACHE, {})
    if not rows or not cache:
        sys.exit("Need data/titles.json and data/cache/mal.json.")
    changed = 0
    for r in rows:
        m = cache.get(r["id"])
        if not m or r.get("malOff") or not is_anime(r["type"]):
            continue
        new = {"score": m.get("score"), "url": m.get("url"), "id": m.get("mal_id")}
        if r.get("mal") != new:
            changed += 1
        r["mal"] = new
        if not r["ja"] and m.get("ja"):
            r["ja"] = m["ja"]
        if r["t"] == r["ja"] and m.get("en"):
            r["t"] = m["en"]
        if not r["year"] and m.get("year"):
            r["year"] = m["year"]
        if not r["romaji"] and m.get("romaji"):
            r["romaji"] = m["romaji"]
        if not r["romaji"] and re.fullmatch(r"[\x20-\x7E・]+", r["ja"] or "x"):
            r["romaji"] = r["ja"].replace("・", ".")
    path = os.path.join(DATA, "titles.json")
    crlf = b"\r\n" in open(path, "rb").read(4096)
    save_json(path, rows)
    if crlf:  # keep the file's Windows line endings so the commit shows only real changes
        raw = open(path, "rb").read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        open(path, "wb").write(raw)
    build.render(rows)
    print(f"{changed} cards changed; {sum(1 for r in rows if r.get('mal') and r['mal'].get('score'))} of {len(rows)} have a MAL score.")


if __name__ == "__main__":
    main()
