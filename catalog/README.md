# Animated titles catalog

`build.py` turns the company sites into `../animated-titles.html`. Nothing in the page is typed by hand except
the curated text in `data/curated/`.

## Everyday use

```
python catalog/build.py             # rebuild from cached pages
python catalog/build.py --refresh   # re-download the company sites first (new releases, new images/trailers)
python catalog/apply_trailer_picks.py   # copy hand-found trailers from data/trailer_search_picks.json, then rebuild
python catalog/serve.py             # open the page at http://localhost:8000/animated-titles.html
```

Open the page through `serve.py` rather than double-clicking the file: YouTube's player refuses to play
on pages opened straight from disk (file://).

After each build, `TODO.md` lists what still needs a human: new titles without an English name or summary,
missing romaji and titles with no trailer.

## What is automatic

| Field | Source |
|---|---|
| Title list, Japanese title, year, page link | company adapter (`companies/*.py`) |
| All images for the viewer | the title's page, plus stills/gallery sub-pages |
| Trailer | YouTube embed on the title page or its trailer sub-page, then the title's official site; each one is checked with YouTube (exists, embeddable, names the title) |
| Romaji fallback | the original title, when it is already in Latin letters |
| Duration/year/director (GAGA) | parsed from the GAGA page when not curated |

## What is curated (`data/curated/<company>.json`)

Keyed by the title's page URL. Every field is optional and overrides the automatic value:

```json
"https://www.example.com/works/some-title/": {
  "en": "English title", "romaji": "Romaji title", "ja": "日本語タイトル",
  "fmt": "Movie | TV series | Streaming series | OVA | OVA series | Film series | TV film | Short film | TV special | Music video | Commercial | Web short | Concert film",
  "dur": "95 min", "year": 2024, "yearNote": "12 Mar 2024 (Japan)",
  "type": "2D anime | 3DCG anime | Stop-motion | Live action | Hybrid: ...",
  "g": ["Drama", "Sci-Fi"], "s": "One- or two-sentence summary in your own words.", "d": "Director",
  "trailer": "YouTube video id, or false for none", "mal_id": 12345,
  "images": ["extra image URLs shown first"], "poster": "card image URL",
  "u": "link override", "skip": true
}
```

## MyAnimeList scores

```
python catalog/mal_scrape.py               # look up every title not looked up yet, then run build.py
python catalog/mal_scrape.py --limit 5     # quick test
python catalog/mal_scrape.py --only haikyu --redo   # redo some titles
```

MyAnimeList is used for anime titles only: anything whose type mentions live action or live footage
(live-action films and dramas, and live-action/animation hybrids) is never looked up and never shows a score.

`mal_scrape.py` searches myanimelist.net for each title's romaji, English name, shorter forms of both and the
Japanese title, opens up to three candidate pages per search, and accepts a page only if a title matches exactly
(start year within one year), or partly with the same start year. It waits 3 seconds between requests, caches
every page, and stops if MyAnimeList starts refusing requests. Results go to `data/cache/mal.json`; build.py
then shows the MAL row and the "MAL score" sort, and uses MAL's trailer for titles that still have none.

New titles from a company are looked up the next time you run it. TODO.md lists titles without a match; pin one
with `"mal_id": <id>` in the curated file (the number in the MAL page URL), or `"mal_id": false` if it isn't on MAL.

`mal.py` is an alternative that uses the official MAL API (needs a free client ID from
https://myanimelist.net/apiconfig in `catalog/config.json` as `{"mal_client_id": "..."}`).

## Adding a company

1. Copy `companies/production_ig.py` (or `gaga.py`) to `companies/<name>.py` and change the constants:
   `NAME`, `SLUG` (curated file name), `SITE`, `ROLE`, `LIST_URL`.
2. `list_titles(refresh)` returns one dict per title with at least `"url"`; add hints you can read from the list
   page (`"ja"`, `"en"`, `"year"`, `"poster"`, `"tags"` → genres, `"label"` → format).
3. `details(item, refresh)` returns `{"images": [...], "trailers": [...], "official": [...]}` and optionally
   `"ja"`, `"romaji"`, `"year"`, `"director"`, `"synopsis"`. `common.py` has `fetch`, `images`, `youtube_ids`,
   `links` and `text` helpers that cover most sites.
4. Add the module to `COMPANIES` in `companies/__init__.py`, run `build.py --refresh`, then fill in the
   titles listed in `TODO.md`.

Pages are cached in `data/cache/http/`, so re-running a build doesn't hit the sites again unless you pass `--refresh`.
