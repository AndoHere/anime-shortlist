# Anime shortlist: notes for Claude

Static catalog of animated titles. `animated-titles.html` is **generated**. Everything else is source.

## Rules that save tokens

- **Never read or edit `animated-titles.html`** (~390 KB, generated). Not even to look. Change the source and rebuild.
- Page UI/JS/CSS lives in `catalog/template.html`. Titles live in `catalog/data/`. Don't re-explore the repo; use the map below.
- One small, focused change per thread. Don't grow long threads.
- Routine work (re-run a build, rebuild, commit) is fine on Sonnet. Use a bigger model only for real code changes.
- Ando starts scrapes manually. Don't add schedules, cron jobs or GitHub Actions for scraping.

## Where things live

- `catalog/build.py`: builds the page from `template.html` + data. Also writes `catalog/data/titles.json` and `catalog/TODO.md`.
- `catalog/companies/*.py`: one scraper per source (GAGA, Production I.G, Hakuhodo, Aniplex, TBS). Registered in `companies/__init__.py`.
- `catalog/data/curated/<company>.json`: hand-curated overrides keyed by title URL (English name, summary, trailer, `skip`, `mal_id`...). Format is in `catalog/README.md`.
- `catalog/data/titles.json`: built catalog data. `catalog/data/trailer_search_picks.json`: hand-found trailers.
- `catalog/mal_scrape.py` / `mal.py`: MyAnimeList scores. `catalog/trailers.py`, `common.py`: helpers.
- `ratings.json` (repo root): ratings the page commits itself through the GitHub API. Don't edit by hand.
- `index.html`: redirect to the page for GitHub Pages. `catalog/data/cache/` is gitignored (~198 MB).

## Commands (run from the repo root)

```
python catalog/build.py             # rebuild from cached pages
python catalog/build.py --refresh   # re-download company sites first
python catalog/apply_trailer_picks.py
python catalog/mal_scrape.py        # MAL lookups for new titles
python catalog/serve.py             # http://localhost:8000/animated-titles.html
```

## Environment gotchas

- The page cache and company-site access exist only on Ando's laptop (clone at `D:\Claude\anime-shortlist-repo`, reached via Remote Control). Cloud sessions can't scrape or fully rebuild. For those, edit the source and have the rebuild run on the laptop (`git pull` first so it doesn't build from an old template).
- Open the page via `serve.py`, not as a file: YouTube won't play from `file://`.
