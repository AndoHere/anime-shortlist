# Ratings relay

GitHub Pages can't write files, so the page sends each rating to this small Cloudflare Worker
(`worker.js`). The Worker keeps the GitHub token as a secret and commits `ratings.json` to `main`.
Nobody has to paste a token into a browser, and every device saves right away.

It only accepts saves sent from the GitHub Pages site (and `localhost:8000` for `serve.py`), and only
ratings in the form `"<title url>": "up" | "maybe" | "down" | "none"`. Anyone who opens the public page
can still rate titles, the same as a visitor with a connected browser could before.

## Setting it up (once, free plan)

1. Make a GitHub fine-grained token at <https://github.com/settings/personal-access-tokens/new>:
   **Only select repositories** → `anime-shortlist`, **Contents: Read and write**, nothing else.
   An expiry of a year or "no expiration" saves having to redo step 4.
2. Sign up or log in at <https://dash.cloudflare.com>.
3. Go to **Workers & Pages → Create → Create Worker** (start from "Hello World"), name it
   `anime-ratings`, and click **Deploy**. Then **Edit code**, replace everything with the contents of
   `relay/worker.js`, and click **Deploy** again.
4. In the Worker's **Settings → Variables and Secrets**, click **Add**, choose type **Secret**, name it
   `GITHUB_TOKEN`, paste the token from step 1, and deploy.
5. Copy the Worker's address (like `https://anime-ratings.<your-name>.workers.dev`). Opening it in a
   browser should show the current ratings as JSON.
6. Put that address in `const RELAY = "..."` in `catalog/template.html` and rebuild the page.

When the token expires, make a new one and replace the `GITHUB_TOKEN` secret (step 4). The page doesn't change.
