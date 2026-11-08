"""MyAnimeList lookups: score, romaji title and (Jikan only) trailer.

Two sources, tried in this order:
  1. The official MAL API, when a client ID is set (env MAL_CLIENT_ID or catalog/config.json {"mal_client_id": ...}).
     Get one free at https://myanimelist.net/apiconfig (App type: "other").
  2. Jikan (api.jikan.moe), the public unofficial MAL API, which needs no key but is sometimes down.
Results are cached per title in data/cache/mal.json, so each title is looked up once.
Set "mal_id" in a curated entry to force a match, or false to mark a title as not on MAL.
"""
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

from common import DATA, ROOT, UA, load_json, save_json

CACHE = os.path.join(DATA, "cache", "mal.json")
FIELDS = "alternative_titles,mean,start_date,media_type,num_episodes"


def client_id():
    cfg = load_json(os.path.join(ROOT, "config.json"), {})
    return os.environ.get("MAL_CLIENT_ID") or cfg.get("mal_client_id")


def _get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"^(劇場版|映画|新劇場版)\s*", "", s)
    return re.sub(r"[\s\W_]+", "", s)


def similar(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 4 and short in long_ and len(short) / len(long_) >= 0.6


class Source:
    def __init__(self):
        self.cid = client_id()
        self.jikan_ok = None
        self.last = 0

    def _wait(self, gap):
        d = gap - (time.time() - self.last)
        if d > 0:
            time.sleep(d)
        self.last = time.time()

    def available(self):
        if self.cid:
            return "MAL API"
        if self.jikan_ok is None:
            try:
                _get("https://api.jikan.moe/v4/anime/1", timeout=8)
                self.jikan_ok = True
            except Exception:
                self.jikan_ok = False
        return "Jikan" if self.jikan_ok else None

    # each returns a list of normalised candidates
    def search(self, q):
        q = q[:60]
        if self.cid:
            self._wait(0.5)
            d = _get("https://api.myanimelist.net/v2/anime?" + urllib.parse.urlencode(
                {"q": q, "limit": 10, "fields": FIELDS}), {"X-MAL-CLIENT-ID": self.cid})
            return [self._from_official(x["node"]) for x in d.get("data", [])]
        self._wait(1.2)
        d = _get("https://api.jikan.moe/v4/anime?" + urllib.parse.urlencode({"q": q, "limit": 10}))
        return [self._from_jikan(x) for x in d.get("data", [])]

    def by_id(self, mal_id):
        if self.cid:
            self._wait(0.5)
            return self._from_official(_get(f"https://api.myanimelist.net/v2/anime/{mal_id}?fields={FIELDS}",
                                            {"X-MAL-CLIENT-ID": self.cid}))
        self._wait(1.2)
        return self._from_jikan(_get(f"https://api.jikan.moe/v4/anime/{mal_id}")["data"])

    @staticmethod
    def _from_official(n):
        alt = n.get("alternative_titles", {})
        sd = n.get("start_date") or ""
        return {"mal_id": n["id"], "romaji": n.get("title"), "en": alt.get("en"), "ja": alt.get("ja"),
                "syn": alt.get("synonyms", []), "score": n.get("mean"),
                "year": int(sd[:4]) if sd[:4].isdigit() else None, "trailer": None,
                "url": f"https://myanimelist.net/anime/{n['id']}"}

    @staticmethod
    def _from_jikan(x):
        frm = (x.get("aired") or {}).get("from") or ""
        return {"mal_id": x["mal_id"], "romaji": x.get("title"), "en": x.get("title_english"),
                "ja": x.get("title_japanese"), "syn": x.get("title_synonyms", []), "score": x.get("score"),
                "year": x.get("year") or (int(frm[:4]) if frm[:4].isdigit() else None),
                "trailer": (x.get("trailer") or {}).get("youtube_id"), "url": x.get("url")}


def match(cands, ja, en, year):
    best = None
    for c in cands:
        names_ja = [c.get("ja")] + c.get("syn", [])
        hit = any(similar(ja, n) for n in names_ja if n) or (en and any(
            similar(en, n) for n in [c.get("en"), c.get("romaji")] if n))
        if not hit:
            continue
        if year and c.get("year") and abs(c["year"] - year) > 1:
            continue
        if best is None or (c.get("score") or 0) > (best.get("score") or 0):
            best = c
    return best


def enrich(rows, refresh=False, log=print):
    """Adds row["mal"] = {...} (or None) to each row. Returns the source used, or None."""
    cache = load_json(CACHE, {})
    src = Source()
    name = src.available()
    for i, r in enumerate(rows):
        key = r.get("key") or r["u"]
        forced = r.get("mal_id")
        if forced is False or r.get("live_action"):
            r["mal"] = None
            continue
        hit = cache.get(key)
        if hit is not None and not refresh and (not forced or hit.get("mal_id") == forced):
            r["mal"] = hit or None
            continue
        if not name:
            r["mal"] = hit or None
            continue
        try:
            if forced:
                found = src.by_id(forced)
            else:
                found = None
                for q in [r.get("ja"), r.get("t"), r.get("romaji")]:
                    if q and len(q) >= 3:
                        found = match(src.search(q), r.get("ja"), r.get("t"), r.get("year"))
                        if found:
                            break
            cache[key] = found or {}
            r["mal"] = found
            log(f"  MAL {i + 1}/{len(rows)} {r['t'][:40]!r}: {found['romaji'] + ' ' + str(found['score']) if found else 'no match'}")
        except Exception as e:
            log(f"  MAL lookup failed for {r['t']!r}: {e}")
            r["mal"] = hit or None
        save_json(CACHE, cache)
    return name
