"""GAGA International Sales: every title tagged Animation."""
import html as htmllib
import re

from common import fetch, images, links, official_links, text, youtube_ids

NAME = "GAGA"
SLUG = "gaga"
SITE = "gaga.co.jp"
ROLE = "International sales"
LIST_URL = "https://www.gaga.co.jp/intls/"


def list_titles(refresh=False):
    titles, page = [], 1
    while True:
        url = LIST_URL if page == 1 else f"{LIST_URL}page/{page}/"
        html = fetch(url, refresh=refresh)
        if not html:
            break
        cards = re.findall(r'<div id="post-\d+"(.*?)</div>\s*</div>\s*</div>', html, re.S)
        if not cards:
            break
        for c in cards:
            tags = [htmllib.unescape(t).strip() for t in re.findall(r'class="[^"]*cat-tag[^"]*">([^<]+)</a>', c)]
            if "Animation" not in tags:
                continue
            href = re.search(r'<a href="([^"]+)"', c).group(1)
            h5 = re.search(r"<h5[^>]*>(.*?)</h5>", c, re.S)
            thumb = re.search(r'<img[^>]+src="([^"]+)"', c)
            titles.append({
                "url": href,
                "en": text(h5.group(1)) if h5 else "",
                "tags": [t for t in tags if t != "Animation" and not re.search(r"Selection|Lineup", t)],
                "poster": thumb.group(1) if thumb else "",
            })
        page += 1
    return titles


def details(item, refresh=False):
    html = fetch(item["url"], refresh=refresh) or ""
    t = text(html)
    out = {
        "images": images(html, item["url"], keep=r"/wp-content/uploads/"),
        "trailers": youtube_ids(html),
        "official": official_links(links(html, item["url"]), "gaga.co.jp")[:1],
    }
    m = re.search(r"\(Original title:\s*([^)]*)\)", t)
    if m:
        parts = [p.strip() for p in m.group(1).split("/")]
        out["ja"] = parts[0]
        if len(parts) > 1 and parts[1]:
            out["romaji"] = parts[1]

    def field(label, stop):
        mm = re.search(r"\n" + label + r"\n(.*?)\n(?:" + stop + ")", "\n" + t, re.S)
        return mm.group(1).strip() if mm else ""

    out["dur_release"] = field("Duration/Release", "Synopsis|Address")
    out["director"] = field("DIRECTOR", "CAST|CREW|Film Festivals|Duration")
    out["synopsis"] = field("Synopsis", "Address|©")
    y = re.findall(r"(?:19|20)\d\d", out["dur_release"])
    if y:
        out["year"] = int(y[0])
    return out
