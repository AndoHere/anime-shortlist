"""Production I.G works archive: films, series, OVAs and shorts (games, apps, goods and stage shows skipped)."""
import html as htmllib
import re
import urllib.parse

from common import fetch, images, links, official_links, text, youtube_ids

NAME = "Production I.G"
SLUG = "production-ig"
SITE = "production-ig.co.jp"
ROLE = "Animation studio"
BASE = "https://www.production-ig.co.jp"
LIST_URL = BASE + "/works/index.html"
KEEP_LABELS = {"TV", "MOVIE", "OVA", "VOD", "WEB", "SHORT", "TV, MOVIE"}
SUBPAGE = re.compile(r"steels|stills?|gallery|trailer|movie\.html|pv\.html|スチール|予告|トレイラー|トレーラー|PV", re.I)


def list_titles(refresh=False):
    html = fetch(LIST_URL, refresh=refresh) or ""
    titles, seen = [], set()
    parts = re.split(r"(\d{4})年公開の作品", html)
    for i in range(1, len(parts), 2):
        year, chunk = int(parts[i]), parts[i + 1]
        for href, label, name in re.findall(
                r'<li class="[^"]*">\s*<a href="([^"]+)"[^>]*>\s*<i[^>]*>(.*?)</i>\s*<span>(.*?)</span>', chunk, re.S):
            label = htmllib.unescape(label).strip()
            url = urllib.parse.urljoin(BASE, href)
            if label not in KEEP_LABELS or url in seen:
                continue
            seen.add(url)
            titles.append({"url": url, "ja": text(name), "year": year, "label": label})
    return titles


def _work_dir(url):
    path = urllib.parse.urlsplit(url).path
    return path if path.endswith("/") else path.rsplit("/", 1)[0] + "/"


def details(item, refresh=False):
    url = item["url"]
    html = fetch(url, refresh=refresh) or ""
    page_links = links(html, url)
    work_dir = _work_dir(url)
    imgs, vids = images(html, url), youtube_ids(html)
    # stills galleries and trailer pages inside the same work folder
    subs = [u for u, label in page_links
            if urllib.parse.urlsplit(u).path.startswith(work_dir) and u != url
            and (SUBPAGE.search(u) or SUBPAGE.search(label))]
    for sub in list(dict.fromkeys(subs))[:8]:
        sh = fetch(sub, refresh=refresh) or ""
        imgs += [i for i in images(sh, sub) if i not in imgs]
        vids += [v for v in youtube_ids(sh) if v not in vids]
    official = official_links(page_links, "production-ig.co.jp")
    t = text(html).split("この作品のトップ", 1)[-1]
    return {"images": imgs, "trailers": vids, "official": official[:1], "synopsis": t[:600]}
