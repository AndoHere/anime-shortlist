"""Hakuhodo DY Music & Pictures: theatrical animation only.

Two lists are read:
  - the international sales animation list (English): only titles whose category says "Theatrical" are kept,
    labelled "Hakuhodo DY Intl."
  - the Japanese theatrical animation list (劇場公開作品), labelled "Hakuhodo DY JP"
A title on both lists appears once, as "Hakuhodo DY Intl.", and takes its Japanese name from the JP list.
Both lists are matched on the title's official website link or its poster file.
"""
import os
import re
import urllib.parse

from common import WP_SIZE, fetch, images, links, official_links, text, youtube_ids

NAME = "Hakuhodo DY"
SLUG = "hakuhodo"
SITE = "hakuhodody-map.jp"
ROLE = "Film production, distribution & international sales"
LIST_URL = "https://www.hakuhodody-map.jp/animation-movie/"
EN_LIST = "https://www.hakuhodody-map.jp/en/animation_en/"
INTL, JP = "Hakuhodo DY Intl.", "Hakuhodo DY JP"
NAMES = [INTL, JP]  # company names this adapter can give a title


def _cards(first_page, refresh):
    out, page = [], 1
    while page < 30:
        url = first_page if page == 1 else f"{first_page}page/{page}/"
        html = fetch(url, refresh=refresh)
        if not html:
            break
        found = re.findall(r'<li[^>]*>\s*<a href="([^"]+)">\s*<div class="photo">.*?<img[^>]+src="([^"]+)".*?'
                           r'<p class="ttl[^"]*">(.*?)</p>', html, re.S)
        if not found:
            break
        for href, img, title in found:
            out.append({"url": href, "poster": urllib.parse.urljoin(url, img), "title": text(title)})
        page += 1
    return out


def _keys(url, html, poster):
    """Identifiers that are the same for one title on the JP and English sites."""
    keys = set()
    for site in official_links(links(html, url), "hakuhodody-map.jp", labels=r"official|公式"):
        p = urllib.parse.urlsplit(site)
        keys.add("site:" + (p.netloc.replace("www.", "") + p.path).rstrip("/").lower())
    name = os.path.basename(urllib.parse.unquote(WP_SIZE.sub("", urllib.parse.urlsplit(poster).path)))
    if name:
        keys.add("img:" + os.path.splitext(name)[0].lower())
    return keys


def _category(html):
    m = re.search(r"\nCategory\n(.*?)\n", "\n" + text(html) + "\n")
    return m.group(1).strip() if m else ""


def list_titles(refresh=False):
    intl = []
    for c in _cards(EN_LIST, refresh):
        html = fetch(c["url"], refresh=refresh) or ""
        cat = _category(html)  # e.g. "2025～2026/Theatrical animation/Drama, Youth"
        if not re.search(r"theatrical|movie|film", cat, re.I):
            continue
        parts = [p.strip() for p in cat.split("/")]
        years = re.findall(r"(?:19|20)\d\d", cat)
        # the remaining parts are genres, unless they are a running time or the format
        genres = [g.strip() for p in parts if not re.search(r"\d|theatrical|animation|series|length", p, re.I)
                  for g in p.split(",") if g.strip()]
        intl.append({"url": c["url"], "co": INTL, "en": c["title"], "poster": c["poster"], "label": "Movie",
                     "year": int(years[0]) if years else None, "tags": genres,
                     "keys": _keys(c["url"], html, c["poster"])})
    by_key = {k: item for item in intl for k in item["keys"]}
    titles = list(intl)
    for c in _cards(LIST_URL, refresh):
        html = fetch(c["url"], refresh=refresh) or ""
        twin = next((by_key[k] for k in _keys(c["url"], html, c["poster"]) if k in by_key), None)
        if twin:  # on both lists: keep the international entry, give it the Japanese title
            twin.setdefault("ja", c["title"])
            continue
        # JP pages give no release date (the © year is often the franchise's), so the year comes from MyAnimeList
        titles.append({"url": c["url"], "co": JP, "ja": c["title"], "poster": c["poster"], "label": "Movie"})
    for t in titles:
        t.pop("keys", None)
    return titles


def details(item, refresh=False):
    html = fetch(item["url"], refresh=refresh) or ""
    t = text(html)
    m = re.search(r"\n(?:コピーライト|Copyright)\n", "\n" + t)
    return {
        "images": images(html, item["url"], keep=r"hakuhodody-map\.jp/img/"),
        "trailers": youtube_ids(html),
        "official": official_links(links(html, item["url"]), "hakuhodody-map.jp")[:1],
        "synopsis": t[:m.start()][-800:] if m else "",
    }
