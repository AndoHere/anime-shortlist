# Anime shortlist

A browsable catalog of animated titles from Japanese studios and distributors, with trailers,
images and MyAnimeList scores.

- `animated-titles.html` is the site itself: one self-contained page.
- `index.html` sends visitors from the site's root address to that page.
- `catalog/` holds the scripts that build the page from the company sites. See
  [catalog/README.md](catalog/README.md).

## Hosting on GitHub Pages

1. In the repository, open **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Pick the `main` branch and the `/ (root)` folder, then **Save**.

After a minute or so the catalog is live at <https://andohere.github.io/anime-shortlist/>.
Every push to `main` republishes it.

Your ratings (Want to watch, Not sure, Not for me) are saved in the browser per web address, so picks made on
`localhost` don't carry over to the GitHub Pages address.

## Updating the catalog

```
python catalog/build.py --refresh   # re-download the company sites and rebuild animated-titles.html
python catalog/serve.py             # preview at http://localhost:8000/animated-titles.html
```

Commit the rebuilt `animated-titles.html` (and `catalog/data/titles.json`, `catalog/TODO.md`) and push.
The downloaded page cache in `catalog/data/cache/` is not stored in the repository, so the first build
on a new machine needs `--refresh`.
