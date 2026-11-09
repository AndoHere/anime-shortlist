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

## Saving ratings to the repository

Ratings (Want to watch, Not sure, Not for me) are kept in `ratings.json` in this repository, so they show
up on every device and for anyone who opens the site. The page reads that file on load. Writing to it needs
a GitHub token, which you enter once per browser:

1. Go to <https://github.com/settings/personal-access-tokens/new> (fine-grained token).
2. Give it a name such as "anime-shortlist ratings" and an expiration date you're happy with.
3. Under **Repository access**, choose **Only select repositories** and pick `anime-shortlist`.
4. Under **Permissions → Repository permissions**, set **Contents** to **Read and write**. Leave everything else.
5. Click **Generate token** and copy it.
6. On the site, click **Save ratings to GitHub** (next to the rating filters) and paste the token.

The token stays in that browser's local storage and is only sent to GitHub. Ratings you made in that
browser before connecting are saved too. Each burst of ratings becomes one commit to `main` named
"Update ratings", and GitHub Pages republishes the site a minute later. Click **Disconnect** to remove the
token from the browser; you can also revoke it on GitHub at any time.

Without a token the page still shows the saved ratings, and new ratings stay in that browser only (the
status next to the button says how many).

## Updating the catalog

```
python catalog/build.py --refresh   # re-download the company sites and rebuild animated-titles.html
python catalog/serve.py             # preview at http://localhost:8000/animated-titles.html
```

Commit the rebuilt `animated-titles.html` (and `catalog/data/titles.json`, `catalog/TODO.md`) and push.
The downloaded page cache in `catalog/data/cache/` is not stored in the repository, so the first build
on a new machine needs `--refresh`.
