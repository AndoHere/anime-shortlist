"""Pick a trailer per title from candidate YouTube ids, checking each one with YouTube's oEmbed endpoint.

oEmbed tells us whether the video still exists and is embeddable, and gives its title. Candidates found on a
title's official site must also mention the title in the video name, since old official domains sometimes
expire and start showing unrelated videos.
"""
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request

from common import DATA, UA, load_json, save_json

CACHE = os.path.join(DATA, "cache", "youtube.json")
_cache = None


def info(vid):
    """{'ok': bool, 'title': str, 'author': str}, cached."""
    global _cache
    if _cache is None:
        _cache = load_json(CACHE, {})
    if vid not in _cache:
        url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(
            f"https://www.youtube.com/watch?v={vid}", safe="")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8"))
            _cache[vid] = {"ok": True, "title": d.get("title", ""), "author": d.get("author_name", "")}
        except Exception as e:
            code = getattr(e, "code", None)
            if code is None:  # network trouble: don't cache, assume fine
                return {"ok": True, "title": "", "author": "", "unchecked": True}
            _cache[vid] = {"ok": False, "title": "", "author": "", "code": code}
        save_json(CACHE, _cache)
    return _cache[vid]


def _n(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"^(劇場版|映画|新劇場版|gekijouban|eiga)\s*", "", s)
    return re.sub(r"[\s\W_]+", "", s)


def mentions(video_title, names):
    vt = _n(video_title)
    for name in names:
        n = _n(name)
        if len(n) >= 2 and n[:min(len(n), 6)] in vt:
            return True
        words = [w for w in re.split(r"[\s:;/!?・\-–—]+", (name or "").lower()) if len(w) >= 4]
        if words and sum(1 for w in words if _n(w) in vt) >= max(1, len(words) // 2):
            return True
    return False


def specific(video_title, own_ja, other_ja):
    """True if the video names this exact title, and no longer title in the catalog matches it better.
    Franchise sites (Psycho-Pass, Haikyu!!) show their newest video, which would otherwise be picked for every entry."""
    vt, own = _n(video_title), _n(own_ja)
    if len(own) < 2 or own not in vt:
        return False
    return not any(len(o) > len(own) and o in vt for o in other_ja)


def choose(candidates, names, other_ja=()):
    """candidates: [(video_id, source)] in priority order. Returns (id, source, video_title) or (None, None, None)."""
    others = [_n(o) for o in other_ja]
    for vid, src in candidates:
        if not vid:
            continue
        i = info(vid)
        if not i["ok"]:
            continue
        if src in ("official site", "MyAnimeList") and i["title"] and not specific(i["title"], names[0], others):
            continue
        return vid, src, i["title"]
    return None, None, None
