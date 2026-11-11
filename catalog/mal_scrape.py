"""Look up each catalog title on myanimelist.net and store its score.

    python catalog/mal_scrape.py                 every title not looked up yet
    python catalog/mal_scrape.py --limit 5       only the first 5 (quick test)
    python catalog/mal_scrape.py --only haikyu   titles whose name contains "haikyu"
    python catalog/mal_scrape.py --redo          look up again, ignoring earlier results
    python catalog/mal_scrape.py --retry-nomatch look up again only the titles that found no match

Reads the title list from data/titles.json (run build.py first) and writes data/cache/mal.json, which
build.py uses for the MAL row, the "MAL score" sort and, where a title has none, a trailer.

How a title is matched: search MyAnimeList for its romaji, then English title; open up to three
candidate pages and accept the first whose Japanese, English or romaji title matches ours and whose
start year is within one year of ours. Pin a match with "mal_id": <id> in the curated file, or
"mal_id": false for a title that isn't on MyAnimeList.

Politeness: one request every 3 seconds, an honest user agent, every page cached, and the run stops
at the first sign of blocking (HTTP 403/429).
"""
import argparse
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, fetch, is_anime, load_json, save_json, text  # noqa: E402
from companies import COMPANIES  # noqa: E402
from mal import CACHE, norm, similar  # noqa: E402

GAP = 3.0
BASE = "https://myanimelist.net"


class Blocked(Exception):
    pass


def get(url):
    fetch.last_status = 200
    html = fetch(url, min_interval=GAP)  # 404s are cached too: MAL answers "no results" with 404
    status = getattr(fetch, "last_status", 200)
    if html is None and status in (403, 429):
        raise Blocked(f"HTTP {status} from {url}")
    return html or ""


def search(q):
    """[(mal_id, title)] from a MyAnimeList anime search, or [(mal_id, None, page)] when MAL jumps straight
    to a title page because the query matched it exactly."""
    html = get(f"{BASE}/anime.php?cat=anime&q={urllib.parse.quote(q[:80])}")
    direct = re.search(r'(?:rel="canonical" href|property="og:url" content)="https://myanimelist\.net/anime/(\d+)', html)
    if direct and '<h1 class="title-name' in html:
        return [(direct.group(1), None, parse_page(html, direct.group(1)))]
    out = []
    for mid, title in re.findall(
            r'href="https://myanimelist\.net/anime/(\d+)/[^"]*"\s+id="sarea\d+"[^>]*>\s*<img[^>]*?alt="([^"]*)"', html, re.S):
        if mid not in [x[0] for x in out]:
            out.append((mid, text(title), None))
    if not out and "sarea" in html:
        print("  warning: search page layout changed; no results parsed", flush=True)
    return out


def page(mal_id):
    html = get(f"{BASE}/anime/{mal_id}")
    return parse_page(html, mal_id) if html else None


def parse_page(html, mal_id):
    def field(label):
        m = re.search(r'<span class="dark_text">' + label + r':</span>\s*(.*?)\s*</div>', html, re.S)
        return text(m.group(1)) if m else ""

    score = re.search(r'itemprop="ratingValue"[^>]*>\s*([\d.]+)\s*<', html)
    title = re.search(r'<h1 class="title-name[^"]*"><strong>(.*?)</strong>', html, re.S)
    year = re.search(r"(19|20)\d\d", field("Aired"))
    trailer = re.search(r"youtube(?:-nocookie)?\.com/embed/([\w-]{11})", html)
    return {"mal_id": int(mal_id), "url": f"{BASE}/anime/{mal_id}",
            "romaji": text(title.group(1)) if title else "",
            "ja": field("Japanese"), "en": field("English"),
            "syn": [s.strip() for s in field("Synonyms").split(",") if s.strip()],
            "type": field("Type"), "year": int(year.group(0)) if year else None,
            "score": float(score.group(1)) if score else None,
            "trailer": trailer.group(1) if trailer else None}


def _head(name):
    """The part of a title before a subtitle separator."""
    return re.split(r"\s*[:：–—―]\s*|\s+-\s+", name or "")[0]


def strength(cand, row):
    """2 = a title matches exactly (year within 1), 1 = partial title match in the same year, 0 = no match.
    Partial matches need the exact year so franchise siblings (a recut film vs. its TV season) aren't confused."""
    names_ja = [cand["ja"]] + cand["syn"]
    names_lat = [cand["romaji"], cand["en"]] + cand["syn"]
    mine_ja, mine_lat = row["ja"], [x for x in (row["t"], row["romaji"]) if x]
    dy = abs(cand["year"] - row["year"]) if row.get("year") and cand["year"] else 0
    exact = any(norm(mine_ja) == norm(n) for n in names_ja if n) or any(
        norm(m) == norm(n) for m in mine_lat for n in names_lat if n)
    if exact and dy <= 1:
        return 2
    partial = any(similar(mine_ja, n) for n in names_ja if n) or any(
        similar(m, n) for m in mine_lat for n in names_lat if n)
    if partial and dy == 0:
        return 1
    # the site's year is often a re-release or announcement year: accept an exact name up to 3 years off,
    # or the same title before a subtitle ("Name: Subtitle" vs "Name") up to 1 year off
    if exact and dy <= 3:
        return 1
    mine_heads = {norm(_head(x)) for x in [mine_ja] + mine_lat if x}
    cand_heads = {norm(_head(x)) for x in names_ja + names_lat if x}
    if any(len(h) >= 4 for h in mine_heads & cand_heads) and dy <= 1:
        return 1
    return 0


# which MyAnimeList types fit each of our formats
FORMAT_TYPES = {
    "Movie": {"Movie"}, "Film series": {"Movie", "OVA", "TV"}, "TV film": {"TV Special", "Movie", "Special"},
    "TV series": {"TV"}, "Streaming series": {"ONA", "TV"}, "TV special": {"TV Special", "Special"},
    "OVA": {"OVA", "Special"}, "OVA series": {"OVA", "ONA", "Special"},
    "Short film": {"Movie", "ONA", "OVA", "Special"}, "Music video": {"Music"},
    "Commercial": {"CM", "ONA", "Special", "PV"}, "Web short": {"ONA", "CM", "Special"}, "Concert film": {"Movie"},
}


def fit(cand, row):
    """Sort key, higher is better: match strength, then format agreement, then year closeness."""
    s = strength(cand, row)
    type_ok = cand["type"] in FORMAT_TYPES.get(row["fmt"], {cand["type"]})
    dy = abs(cand["year"] - row["year"]) if row.get("year") and cand["year"] else 0
    return (s, type_ok, -dy)


def ranked(results, row):
    """Search results ordered by how close their title is to ours."""
    mine = [norm(row["romaji"]), norm(row["t"])]

    def score(item):
        n = norm(item[1] or "")
        if n in mine:
            return 0
        if any(m and (m in n or n in m) for m in mine):
            return 1
        return 2
    return sorted(results, key=score)


def queries(row):
    """Search terms, most specific first. MAL returns nothing for long titles that don't match exactly,
    so shorter forms follow: the part before a colon/dash, the first words, and the Japanese title."""
    qs = []
    for name in (row["romaji"], row["t"]):
        if not name:
            continue
        qs.append(name)
        bare = re.sub(r"^(Gekijou-?ban|Shin Gekijouban|Eiga|Gekijou Soushuuhen)\s+", "", name)
        qs.append(bare)  # MAL titles rarely carry the "the movie" prefix
        name = bare
        head = re.split(r"\s*[:：–—]\s*|\s+-\s+", name)[0]
        qs.append(head)
        words = re.sub(r"[^\w\s]", " ", head).split()
        if len(words) > 2:
            qs.append(" ".join(words[:2]))
    ja = re.sub(r"^(劇場版|映画|新劇場版)\s*|[『』「」]", "", row["ja"] or "")
    qs.append(ja)
    return [q for q in dict.fromkeys(q.strip() for q in qs) if len(q) >= 3]


def lookup(row, forced=None):
    if forced:
        return page(forced)
    tried, best, best_fit = set(), None, (0, False, -99)
    for q in queries(row):
        opened = 0
        for mid, _, parsed in ranked(search(q)[:8], row):
            if mid in tried or opened >= 3:
                continue
            tried.add(mid)
            opened += 0 if parsed else 1
            cand = parsed or page(mid)
            if not cand:
                continue
            f = fit(cand, row)
            if f[0] and f > best_fit:
                best, best_fit = cand, f
            if f == (2, True, 0):  # exact title, right format, same year: done
                return cand
        if best_fit[:2] == (2, True):  # exact title and format found; shorter searches won't do better
            break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--retry-nomatch", action="store_true", help="look up again only the titles that found no match")
    a = ap.parse_args()

    rows = load_json(os.path.join(DATA, "titles.json"), [])
    if not rows:
        sys.exit("No data/titles.json yet: run build.py first.")
    curated = {}
    for c in COMPANIES:
        for k, v in load_json(os.path.join(DATA, "curated", c.SLUG + ".json"), {}).items():
            curated[k] = v
    cache = load_json(CACHE, {})

    todo = []
    for r in rows:
        forced = curated.get(r["id"], {}).get("mal_id")
        if forced is False or not is_anime(r["type"]):  # anime only: no live action or hybrids
            cache.pop(r["id"], None)
            continue
        if a.only and a.only.lower() not in (r["t"] + " " + r["romaji"]).lower():
            continue
        if a.retry_nomatch and r["id"] in cache and not cache[r["id"]] and not forced:
            todo.append((r, forced))
            continue
        if r["id"] in cache and not a.redo and (not forced or cache[r["id"]].get("mal_id") == forced):
            continue
        todo.append((r, forced))
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo)} titles to look up (about {len(todo) * 3 * GAP / 60:.0f} min at most)", flush=True)

    found = 0
    try:
        for n, (r, forced) in enumerate(todo, 1):
            hit = lookup(r, forced)
            cache[r["id"]] = hit or {}
            save_json(CACHE, cache)
            found += bool(hit)
            res = f"{hit['score'] or 'no score'}  ←  {hit['romaji']} ({hit['year']}) {hit['url']}" if hit else "no match"
            print(f"{n:>3}/{len(todo)}  {r['t'][:45]:<45}  {res}", flush=True)
    except Blocked as e:
        print(f"Stopped: MyAnimeList refused a request ({e}). Results so far are saved; try again later.")
    except KeyboardInterrupt:
        print("Interrupted; results so far are saved.")
    print(f"Matched {found} of {len(todo)}. Run build.py to put the scores on the page.")


if __name__ == "__main__":
    main()
