"""Build animated-titles.html from the company sites, the curated JSON files and MyAnimeList.

    python catalog/build.py              use cached pages, look up new titles on MAL, rebuild the page
    python catalog/build.py --refresh    re-download company title lists and pages first
    python catalog/build.py --no-mal     skip MyAnimeList lookups
    python catalog/build.py --mal-refresh  redo every MAL lookup

Outputs: animated-titles.html (next to the catalog folder), catalog/data/titles.json and catalog/TODO.md.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import DATA, ROOT, WP_SIZE, is_anime, load_json, official_site, save_json  # noqa: E402
from companies import COMPANIES  # noqa: E402
import mal  # noqa: E402
import trailers  # noqa: E402

OUT_HTML = os.path.join(os.path.dirname(ROOT), "animated-titles.html")
TEMPLATE = os.path.join(ROOT, "template.html")


def log(*a):
    print(*a, flush=True)


def build_company(co, refresh):
    curated_path = os.path.join(DATA, "curated", co.SLUG + ".json")
    curated = load_json(curated_path, {})
    items = co.list_titles(refresh=refresh)
    log(f"{co.NAME}: {len(items)} titles listed")
    rows = []
    for n, item in enumerate(items, 1):
        e = curated.get(item["url"], {})
        if e.get("skip"):
            continue
        det = co.details(item, refresh=refresh)
        official_vids, official_imgs = [], []
        for site in det.get("official", [])[:1]:
            o = official_site(site)
            official_vids += o["trailers"]
            official_imgs += o["images"]
        # full-size images for the viewer; the list thumbnail (item poster) only if no full version exists
        imgs = []
        for i in e.get("images", []) + det.get("images", []) + official_imgs:
            if i and i not in imgs:
                imgs.append(i)
        poster_full = WP_SIZE.sub("", item.get("poster", ""))
        if poster_full and poster_full not in imgs:
            imgs.insert(0, item["poster"])
        elif poster_full:  # show the poster first in the viewer
            imgs.remove(poster_full)
            imgs.insert(0, poster_full)
        # trailer candidates in priority order; trailers.choose() picks the first that checks out
        if "trailer" in e:
            cands = [(e["trailer"], e.get("trailerSrc", "found by search"))] if e["trailer"] else []
        else:
            cands = [(v, co.SITE) for v in det.get("trailers", [])[:3]] + \
                    [(v, "official site") for v in official_vids[:3]]
        ja = e.get("ja") or det.get("ja") or item.get("ja") or ""
        company = item.get("co") or co.NAME
        url = e.get("u") or item["url"]
        rows.append({
            "u": url,
            "key": item["url"],
            "co": company, "cos": [company], "role": co.ROLE, "site": co.SITE,
            "links": [{"co": company, "site": co.SITE, "u": url}],
            "t": clean_title(e.get("en") or item.get("en") or det.get("romaji") or ja),
            "ja": ja,
            "romaji": e.get("romaji") or det.get("romaji") or "",
            "poster": e.get("poster") or det.get("poster") or item.get("poster") or (imgs[0] if imgs else ""),
            "images": imgs,
            "cands": cands, "noTrailer": e.get("trailer") is False,
            "fmt": e.get("fmt") or item.get("label") or "—",
            "dur": e.get("dur") or det.get("dur_release") or "—",
            "year": e.get("year") or det.get("year") or item.get("year") or 0,
            "yearNote": e.get("yearNote", ""),
            "type": e.get("type") or "Animated",
            "g": e.get("g") or item.get("tags") or [],
            "s": e.get("s") or "",
            "d": e.get("d") or "",
            "mal_id": e.get("mal_id"),
            "live_action": bool(re.match(r"live action", e.get("type", ""), re.I)),
            "curated": bool(e),
        })
        extra = item.get("extra_co")  # the same title also listed by this company on the same site (Hakuhodo JP)
        if extra and extra["co"] != company:
            rows[-1]["cos"].append(extra["co"])
            rows[-1]["links"].append({"co": extra["co"], "site": co.SITE, "u": extra["u"]})
        if n % 25 == 0:
            log(f"  {co.NAME}: {n}/{len(items)} pages read")
    unused = set(curated) - {i["url"] for i in items}
    if unused:
        log(f"  note: {len(unused)} curated {co.NAME} entries no longer listed on the site: {sorted(unused)[:5]}")
    return rows


def clean_title(t):
    """Drops zero-width characters and adds the missing space before a trailing numeral ("Dungeon?Ⅳ", "Time2")."""
    t = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", t or "")
    t = re.sub(r"(?<=[?!])(?=[Ⅰ-Ⅻ])", " ", t)
    return re.sub(r"(?<=[a-z])(?=\d$)", " ", t)


def title_key(r):
    name = r["ja"] or r["t"]
    name = re.sub(r"^(劇場版|映画|劇場アニメーション|劇場アニメ|新劇場版)\s*|[『』「」〈〉《》]", "", name or "")
    return mal.norm(name)


def merge_duplicates(rows):
    """One card per title: a title listed by several companies keeps the first company's entry
    (company order in companies/__init__.py) and gains the others' names, links, images and trailers."""
    kept = []
    for r in rows:
        k = title_key(r)
        twin = next((x for x in kept if k and title_key(x) == k and
                     (not x["year"] or not r["year"] or abs(x["year"] - r["year"]) <= 1)), None)
        if not twin:
            kept.append(r)
            continue
        if r["site"] != twin["site"]:  # same site twice (e.g. Hakuhodo JP + Intl.): the adapter's choice stands
            for c in r["cos"]:
                if c not in twin["cos"]:
                    twin["cos"].append(c)
            twin["links"] += [l for l in r["links"] if l["u"] not in [x["u"] for x in twin["links"]]]
        twin["images"] += [i for i in r["images"] if i not in twin["images"]]
        twin["cands"] += r["cands"]
        twin["mal"] = twin.get("mal") or r.get("mal")
        for f in ("ja", "romaji", "s", "d"):
            twin[f] = twin[f] or r[f]
        if not twin["curated"] and r["curated"]:
            for f in ("t", "fmt", "dur", "type", "g", "yearNote"):
                twin[f] = r[f]
            twin["curated"] = True
        twin.setdefault("also", []).append(r["key"])
    if len(kept) < len(rows):
        log(f"Merged {len(rows) - len(kept)} titles listed by more than one company")
    return kept


def finish(rows, mal_source):
    for r in rows:
        m = r.pop("mal", None)
        if not is_anime(r["type"]) or r.get("mal_id") is False:
            m = None  # MyAnimeList is only used for anime titles
        if m and not r["ja"] and m.get("ja"):
            r["ja"] = m["ja"]
        if m and r["t"] == r["ja"] and m.get("en"):
            r["t"] = m["en"]  # no English name curated yet: use MyAnimeList's
        if m and not r["year"] and m.get("year"):
            r["year"] = m["year"]
        r.pop("also", None)
        r["mal"] = {"score": m.get("score"), "url": m.get("url"), "id": m.get("mal_id")} if m else None
        if m and not r["romaji"] and m.get("romaji"):
            r["romaji"] = m["romaji"]
        if not r["romaji"] and re.fullmatch(r"[\x20-\x7E・]+", r["ja"] or "x"):
            r["romaji"] = r["ja"].replace("・", ".")  # original title is already in Latin letters
        cands = r.pop("cands")
        if m and m.get("trailer") and not r["noTrailer"]:
            cands.append((m["trailer"], "MyAnimeList"))
        names = [r["ja"], r["t"], r["romaji"]]
        others = [o["ja"] for o in rows if o is not r and o["ja"] != r["ja"]]
        r["trailer"], r["trailerSrc"], r["trailerTitle"] = trailers.choose(cands, names, others)
        r.pop("noTrailer")
        r["id"] = r.pop("key")  # stable id for saved ratings
        r["malOff"] = r.get("mal_id") is False
        for k in ("mal_id", "live_action"):
            r.pop(k, None)
    return rows


def write_todo(rows, mal_source):
    lines = ["# Catalog TODO", "", f"Generated {datetime.date.today()} by build.py. Fill these in "
             "in catalog/data/curated/<company>.json (keyed by the title's page URL), then rebuild.", ""]

    def section(title, items):
        if items:
            lines.extend([f"## {title} ({len(items)})", ""] + [f"- [{r['t']}]({r['u']}) — {r['ja']}" for r in items] + [""])

    section("New titles without curated info (en, s, g, fmt, dur, type)", [r for r in rows if not r["curated"]])
    section("Missing summary", [r for r in rows if r["curated"] and not r["s"]])
    section("Missing romaji", [r for r in rows if not r["romaji"]])
    section("No trailer found (set \"trailer\": \"<youtube id>\" or false)", [r for r in rows if not r["trailer"]])
    if mal_source:
        section("No MyAnimeList match (set \"mal_id\": <id> or false)",
                [r for r in rows if not r["mal"] and is_anime(r["type"]) and r.get("malOff") is not True])
    with open(os.path.join(ROOT, "TODO.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def render(rows):
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    data = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    companies = [{"name": c.NAME, "site": c.SITE, "role": c.ROLE,
                  "list": c.LIST_URL} for c in COMPANIES]
    page = (tpl.replace("/*DATA*/[]", data)
               .replace("/*COMPANIES*/[]", json.dumps(companies, ensure_ascii=False))
               .replace("{{BUILT}}", datetime.date.today().strftime("%-d %b %Y") if os.name != "nt"
                        else datetime.date.today().strftime("%#d %b %Y")))
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--mal", action="store_true", help="look up MyAnimeList scores (automatic when a client ID is set)")
    ap.add_argument("--no-mal", action="store_true")
    ap.add_argument("--mal-refresh", action="store_true")
    a = ap.parse_args()
    rows = []
    for co in COMPANIES:
        rows += build_company(co, a.refresh)
    src = None
    if (a.mal or a.mal_refresh or mal.client_id()) and not a.no_mal:
        src = mal.enrich(rows, refresh=a.mal_refresh, log=log)
        log(f"MyAnimeList source: {src or 'none reachable (using cache only)'}")
    else:
        cache = load_json(mal.CACHE, {})
        for r in rows:
            r["mal"] = cache.get(r["key"]) or None
    for r in rows:  # titles listed only in English get their Japanese name from MyAnimeList, so duplicates can be found
        if r.get("mal") and not r["ja"] and r["mal"].get("ja"):
            r["ja"] = r["mal"]["ja"]
    rows = merge_duplicates(rows)
    rows = finish(rows, src)
    save_json(os.path.join(DATA, "titles.json"), rows)
    write_todo(rows, src or bool(load_json(mal.CACHE, {})))
    render(rows)
    log(f"Wrote {len(rows)} titles to {OUT_HTML}")
    log(f"  trailers: {sum(1 for r in rows if r['trailer'])}, MAL scores: {sum(1 for r in rows if r['mal'] and r['mal']['score'])}, "
        f"romaji: {sum(1 for r in rows if r['romaji'])}")


if __name__ == "__main__":
    main()
