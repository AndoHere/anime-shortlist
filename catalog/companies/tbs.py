"""TBS Program Catalog, Anime category: theatrical films only.

The list mixes TV series, specials and films, and gives each card a running time. Series show
"30 min. x 12 eps." and specials "45 min. x 1 ep."; films show a single runtime ("110 min."). A card
with one runtime of 40 minutes or more counts as a film. Cards with no runtime or "TBD" are decided
from the title page: a "Japan Release" date or 劇場版/映画/Movie in the title means a film.
"""
import html as htmllib
import re

from common import fetch, text, youtube_ids

NAME = "TBS"
SLUG = "tbs"
SITE = "tbscontents.com"
ROLE = "International sales"
BASE = "https://www.tbscontents.com"
LIST_URL = BASE + "/animation/"
MIN_FILM_MINUTES = 40


def _pages(refresh):
    """The list page and its "load more" pages (36 cards each, ?pnum=36, 72, ... until the pager says -1)."""
    html = fetch(LIST_URL, refresh=refresh) or ""
    yield html
    seen = {0}
    while True:
        m = re.search(r"\$\('#pagerStartIndex'\)\.val\((-?\d+)\)", html)
        nxt = int(m.group(1)) if m else -1
        if nxt < 0 or nxt in seen:
            return
        seen.add(nxt)
        html = fetch(f"{LIST_URL}?part=pc&pnum={nxt}&tab=1", refresh=refresh) or ""
        yield html


def _runtime(card_time):
    """Minutes when the card shows a single runtime (a film), else None (series, special, TBD)."""
    t = htmllib.unescape(card_time or "")
    if re.search(r"\bep", t, re.I):
        return None
    m = re.fullmatch(r"\s*(\d+)\s*min\.?\s*", t)
    return int(m.group(1)) if m else None


def _ja(sub_subject):
    """Japanese title: the first of the ja / ko / zh titles, which are separated by ideographic spaces."""
    t = htmllib.unescape(re.sub(r"<[^>]+>", "", sub_subject or "")).strip()
    return re.split(r"　+|\s{2,}", t)[0].strip() if t else ""


def _fields(html):
    """{label: text} for the labelled blocks on a title page (Broadcast Date, Director, ...)."""
    out = {}
    for label, body in re.findall(
            r'class="tv_program_label tbs-program-label">([^<]+)</div>\s*(.*?)</(?:p|ul)>', html, re.S):
        out.setdefault(label.strip(), text(body))
    return out


def _main(html):
    return html.split("You may also like", 1)[0]


def _is_film_page(url, refresh):
    html = _main(fetch(url, refresh=refresh) or "")
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    return bool(re.search(r"Japan Release", html)
                or (title and re.search(r"劇場版|映画|\bmovie\b", htmllib.unescape(title.group(1)), re.I)))


def list_titles(refresh=False):
    titles, seen = [], set()
    for html in _pages(refresh):
        for card in re.split(r'<div class="card__item">', html)[1:]:
            href = re.search(r'href="(/en/program/[^"]+)"', card)
            if not href:
                continue
            url = BASE + href.group(1)
            if url in seen:
                continue
            seen.add(url)
            time_m = re.search(r'class="program-time">\s*<p>(.*?)</p>', card, re.S)
            card_time = time_m.group(1).strip() if time_m else ""
            minutes = _runtime(card_time)
            if minutes is not None:
                if minutes < MIN_FILM_MINUTES:
                    continue
            elif re.search(r"\bep", card_time, re.I) or not _is_film_page(url, refresh):
                continue
            name = re.search(r"<h4[^>]*>\s*<a[^>]*>(.*?)</a>", card, re.S)
            sub = re.search(r'class="sub-subject[^"]*">(.*?)</p>', card, re.S)
            tid = re.search(r"tid=(\d+)", card)
            tags = [htmllib.unescape(t).strip() for t in re.findall(r"<li>([^<]+)</li>", card)]
            titles.append({
                "url": url,
                "en": text(name.group(1)) if name else "",
                "ja": _ja(sub.group(1)) if sub else "",
                "tags": [t for t in tags if t != "For Children"] or tags,
                "poster": f"{BASE}/tbs-eng-ps/open/open-tv-program!image?tid={tid.group(1)}&imageNumber=1" if tid else "",
                "label": "Movie",
                "dur": f"{minutes} min" if minutes else "",
            })
    return titles


def details(item, refresh=False):
    html = _main(fetch(item["url"], refresh=refresh) or "")
    tid = re.search(r"form\.tid=(\d+)", html)
    imgs = []
    if tid:
        for n in re.findall(r"open-tv-program!image\?tid=" + tid.group(1) + r"&(?:amp;)?imageNumber=(\d+)", html):
            u = f"{BASE}/tbs-eng-ps/open/open-tv-program!image?tid={tid.group(1)}&imageNumber={n}"
            if u not in imgs:
                imgs.append(u)
    f = _fields(html)
    out = {"images": imgs, "trailers": youtube_ids(html), "official": []}
    if item.get("ja"):
        out["ja"] = item["ja"]
    if item.get("dur"):
        out["dur_release"] = item["dur"]
    y = re.search(r"(?:19|20)\d\d", f.get("Broadcast Date", ""))
    if y:
        out["year"] = int(y.group(0))
    if f.get("Director"):
        # "Naoko Yamada (山田尚子)" -> "Naoko Yamada"; several directors are on separate lines
        out["director"] = ", ".join(re.sub(r"\s*\(.*?\)\s*$", "", d).strip()
                                    for d in f["Director"].split("\n") if d.strip())
    syn = re.search(r'<div class="tv_program_label tbs-program-label">Episode / Duration</div>.*?</p>(.*?)'
                    r'(?:<div class="tv_program_label|$)', html, re.S)
    if syn:
        out["synopsis"] = text(syn.group(1))[:800]
    return out
