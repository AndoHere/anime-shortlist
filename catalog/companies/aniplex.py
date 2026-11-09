"""Aniplex: theatrical films from the full anime lineup (TV series, streaming and OVAs are skipped).

A title counts as a film when its page is labelled 劇場上映 (theatrical release), or its name says it is one
(劇場版, 劇場アニメーション, 映画, "the Movie") — unreleased films are labelled only "アニメ".
"""
import re
import urllib.parse

from common import fetch, links, official_links, text, youtube_ids

NAME = "Aniplex"
SLUG = "aniplex"
SITE = "aniplex.co.jp"
ROLE = "Producer & distributor"
BASE = "https://www.aniplex.co.jp"
LIST_URL = BASE + "/anime/all/"
ROWS = ["a", "ka", "sa", "ta", "na", "ha", "ma", "ya", "la", "wa"]
FILM_NAME = re.compile(r"劇場版|劇場アニメ|映画|the movie|\bmovie\b", re.I)


def _label(html):
    m = re.search(r'class="p-work:outline__info-text">\s*(.*?)\s*</span>', html, re.S)
    return text(m.group(1)) if m else ""


def list_titles(refresh=False):
    titles, seen = [], set()
    for row in ROWS:
        html = fetch(f"{LIST_URL}?page={row}", refresh=refresh) or ""
        for href, name in re.findall(r'href="(/lineup/[^"]+)" class="p-lineup:archive-card">.*?'
                                     r'archive-card__title">\s*(.*?)\s*</div>', html, re.S):
            url = BASE + href
            if url in seen:
                continue
            seen.add(url)
            name = re.sub(r"\s+\d{4}\.\d{1,2}$", "", text(name)).strip()
            page = fetch(url, refresh=refresh) or ""
            label = _label(page)  # e.g. "劇場上映 (2017.8)", "TVアニメ (2024.10)", "アニメ"
            if "劇場" not in label and not FILM_NAME.search(name):
                continue
            year = re.findall(r"((?:19|20)\d\d)\.\d", label)
            titles.append({"url": url, "ja": name, "label": "Movie", "year": int(year[0]) if year else None,
                           "slug": href.strip("/").split("/")[-1]})
    return titles


def details(item, refresh=False):
    html = fetch(item["url"], refresh=refresh) or ""
    slug = item["slug"]
    kv = sorted(set(re.findall(r'/SYS/CONTENTS/(keyvisual_[\w-]+?)(?:_avif)?/w\d+', html)))
    imgs = [f"{BASE}/SYS/CONTENTS/{k}/w1400" for k in kv if not k.endswith("_avif")] or \
           [f"{BASE}/SYS/CONTENTS/keyvisual_{slug}/w1400"]
    page_links = links(html, item["url"])
    official = [u for u, label in page_links if "オフィシャルサイト" in label and SITE not in u] or \
        official_links(page_links, SITE)
    t = text(html)
    m = re.search(r"\nINTRODUCTION\n|\nSTORY\n", "\n" + t)
    return {"images": imgs, "poster": f"{BASE}/SYS/CONTENTS/keyvisual_{slug}/w400",
            "trailers": youtube_ids(html), "official": official[:1],
            "synopsis": t[m.end():m.end() + 600] if m else ""}
