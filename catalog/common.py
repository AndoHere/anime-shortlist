"""Shared helpers for company adapters and enrichment: cached fetching and HTML parsing."""
import hashlib
import html as htmllib
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
HTTP_CACHE = os.path.join(DATA, "cache", "http")
UA = "animated-titles-catalog/1.0 (personal catalog builder)"

_last_request = {}


def fetch_status(url):
    """HTTP status of the cached response for url, or None if not cached."""
    path = os.path.join(HTTP_CACHE, hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")
    return load_json(path, {}).get("status")


def fetch(url, refresh=False, min_interval=0.5, timeout=30, headers=None, cache_failures=True):
    """GET a URL as text, cached on disk. Returns None on failure (failures are cached unless cache_failures=False)."""
    os.makedirs(HTTP_CACHE, exist_ok=True)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    path = os.path.join(HTTP_CACHE, key + ".json")
    if not refresh and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)["body"]
    host = urllib.parse.urlsplit(url).netloc
    wait = min_interval - (time.time() - _last_request.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_request[host] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    body, status = None, None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.status
            raw = r.read()
            charset = r.headers.get_content_charset() or "utf-8"
            body = raw.decode(charset, errors="replace")
    except Exception as e:  # network errors and 4xx/5xx
        status = getattr(e, "code", str(e))
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            # some sites send an incomplete certificate chain; curl (the OS certificate store) still verifies them
            body, status = _curl(url, timeout)
    fetch.last_status = status
    if body is None and not cache_failures:
        return None
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"url": url, "status": status, "fetched": time.time(), "body": body}, f, ensure_ascii=False)
    return body


def _curl(url, timeout):
    try:
        r = subprocess.run(["curl", "-s", "-L", "-m", str(timeout), "-A", UA, "-w", "\n%{http_code}", url],
                           capture_output=True, timeout=timeout + 5)
        out = r.stdout.decode("utf-8", errors="replace")
        body, _, code = out.rpartition("\n")
        code = int(code) if code.strip().isdigit() else 0
        return (body if 200 <= code < 300 else None), code
    except Exception as e:
        return None, str(e)


def abs_url(base, href):
    href = htmllib.unescape(href.strip())
    if href.startswith("//"):
        return "https:" + href
    return urllib.parse.urljoin(base, href)


def text(html):
    t = re.sub(r"<(script|style|noscript)\b.*?</\1>", "", html, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</(p|div|li|dt|dd|h\d|tr|section)>", "\n", t, flags=re.I)
    t = htmllib.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t　\xa0]+", " ", t)
    return re.sub(r"\s*\n\s*", "\n", t).strip()


def links(html, base):
    """[(absolute href, link text)] for every <a> on the page."""
    out = []
    for href, inner in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
        if href.startswith(("#", "javascript:", "mailto:")):
            continue
        out.append((abs_url(base, href), text(inner)))
    return out


YT_RE = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=|shorts/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})")
YT_ATTR = re.compile(r"""data-(?:youtube|yt|video|movie)(?:-?id)?\s*=\s*["']([A-Za-z0-9_-]{11})["']""", re.I)
YT_MISC = re.compile(r"""(?:["'\s]youtube:|ytimg\.com/vi(?:_webp)?/|youtube\.com/vi(?:_webp)?/)([A-Za-z0-9_-]{11})""")


def youtube_ids(html):
    seen = []
    for vid in YT_RE.findall(html or "") + YT_ATTR.findall(html or "") + YT_MISC.findall(html or ""):
        if vid not in seen:
            seen.append(vid)
    return seen


# decorative images, judged on the file name (and a few folder names) only
IMG_SKIP_NAME = re.compile(
    r"^(prev|next)([_-]?(btn|arrow|on|off|\d))?\.\w+$|"
    r"^(icon|logo|btn|button|bnr|banner|arrow|nav|sns|share|close|pagetop|spacer|loading|blank|"
    r"badge|qr|bg_|favicon|apple-touch|android-icon|ogimage)|"
    r"(twitter|instagram|facebook|youtube|tiktok|line_icon|_btn|_icon|-icon|_arrow|^logo\.)", re.I)
IMG_SKIP_PATH = re.compile(r"/(icons?|common/images/(?:btn|nav))/|/themes/[^/]+/constitution/images/", re.I)
SOCIAL = re.compile(r"twitter\.com|x\.com/|instagram\.com|facebook\.com|youtube\.com|youtu\.be|tiktok\.com|"
                    r"line\.me|amazon\.|apple\.com|google\.|igport\.co\.jp|productionig\.com|bandai|animate", re.I)


def official_links(page_links, own_domain, labels=r"公式|official"):
    """External links that look like a title's official site (by label, or bare-URL links), social sites excluded."""
    out = []
    for u, label in page_links:
        host = urllib.parse.urlsplit(u).netloc
        if not host or own_domain in host or SOCIAL.search(u):
            continue
        if re.search(labels, label, re.I) or label.strip().rstrip("/") in (u.rstrip("/"), host):
            if u not in out:
                out.append(u)
    return out


def official_site(url):
    """Trailer ids and the share image (og:image) from a title's official site, following one PV/movie page."""
    html = fetch(url) or ""
    vids = youtube_ids(html)
    imgs = [abs_url(url, m) for m in re.findall(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)]
    if not vids:
        host = urllib.parse.urlsplit(url).netloc
        subs = [u for u, label in links(html, url)
                if urllib.parse.urlsplit(u).netloc == host
                and re.search(r"movie|pv|trailer|video|special|予告|ムービー|PV|映像", u + " " + label, re.I)]
        for sub in list(dict.fromkeys(subs))[:2]:
            vids += [v for v in youtube_ids(fetch(sub) or "") if v not in vids]
            if vids:
                break
    return {"trailers": vids, "images": imgs[:1]}
IMG_RE = re.compile(r'''(?:src|data-src|href|srcset)\s*=\s*["']([^"']+)["']''', re.I)
WP_SIZE = re.compile(r"(?:-\d{2,4}x\d{2,4}|-scaled)(?=\.(?:jpe?g|png|webp)$)", re.I)


def images(html, base, keep=None):
    """Content images on a page, de-duplicated. `keep` is an optional regex an image URL must match.
    WordPress size variants (name-400x565.jpg) collapse to the original upload."""
    found = []
    for attr in IMG_RE.findall(html or ""):
        for part in attr.split(","):
            u = part.strip().split(" ")[0]
            if not re.search(r"\.(jpe?g|png|webp)(\?.*)?$", u, re.I):
                continue
            u = abs_url(base, u)
            name = urllib.parse.unquote(u.split("?")[0].rsplit("/", 1)[-1])
            if IMG_SKIP_NAME.search(name) or IMG_SKIP_PATH.search(u):
                continue
            if keep and not re.search(keep, u):
                continue
            u = WP_SIZE.sub("", u)
            if u not in found:
                found.append(u)
    return found


def is_anime(type_text):
    """False for live-action work, including live-action/animation hybrids. MyAnimeList is only used for anime."""
    return not re.search(r"live (action|footage)", type_text or "", re.I)


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
