// Cloudflare Worker that saves ratings to ratings.json in the repo, so the page needs no GitHub token.
// The token lives here as the secret GITHUB_TOKEN (fine-grained, this repo only, Contents: Read and write).
// Setup steps are in relay/README.md.
//
//   GET  /  -> the current ratings.json from the repo, as JSON (fresher than the Pages copy)
//   POST /  -> body {"changes": {"<title url>": "up" | "maybe" | "down" | "none", ...}}
//              merges the changes into ratings.json and commits them as one "Update ratings" commit

const REPO = "AndoHere/anime-shortlist", BRANCH = "main", FILE = "ratings.json";
const API = `https://api.github.com/repos/${REPO}/contents/${FILE}`;
const ORIGINS = ["https://andohere.github.io", "http://localhost:8000", "http://127.0.0.1:8000"];
const VALUES = new Set(["up", "maybe", "down", "none"]);
const MAX_CHANGES = 500;

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": ORIGINS.includes(origin) ? origin : ORIGINS[0],
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Vary": "Origin",
    };
    const reply = (body, status = 200) =>
      new Response(JSON.stringify(body), {status, headers: {...cors, "Content-Type": "application/json", "Cache-Control": "no-store"}});

    if (request.method === "OPTIONS") return new Response(null, {status: 204, headers: cors});
    if (!env.GITHUB_TOKEN) return reply({error: "GITHUB_TOKEN secret is not set"}, 500);
    const gh = {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "User-Agent": "anime-shortlist-ratings-relay",
    };

    async function read() {
      const r = await fetch(`${API}?ref=${BRANCH}`, {headers: gh});
      if (r.status === 404) return {data: {}, sha: null};
      if (!r.ok) throw new Error(`GitHub read failed: ${r.status}`);
      const j = await r.json();
      const bytes = Uint8Array.from(atob(j.content.replace(/\s/g, "")), c => c.charCodeAt(0));
      return {data: JSON.parse(new TextDecoder().decode(bytes) || "{}"), sha: j.sha};
    }

    try {
      if (request.method === "GET") return reply((await read()).data);
      if (request.method !== "POST") return reply({error: "method not allowed"}, 405);
      // Browsers always send Origin on a cross-site POST; this keeps other websites from using the relay.
      if (!ORIGINS.includes(origin)) return reply({error: "origin not allowed"}, 403);

      const text = await request.text();
      if (text.length > 100000) return reply({error: "too large"}, 413);
      const changes = (JSON.parse(text) || {}).changes;
      if (!changes || typeof changes !== "object" || Array.isArray(changes)) return reply({error: "expected {changes: {...}}"}, 400);
      const entries = Object.entries(changes);
      if (!entries.length || entries.length > MAX_CHANGES) return reply({error: "bad number of changes"}, 400);
      for (const [id, v] of entries)
        if (!/^https?:\/\/\S{1,300}$/.test(id) || !VALUES.has(v)) return reply({error: `bad change for ${id}`}, 400);

      for (let attempt = 0; ; attempt++) {
        const {data, sha} = await read();
        for (const [id, v] of entries) { if (v === "none") delete data[id]; else data[id] = v; }
        const sorted = Object.fromEntries(Object.keys(data).sort().map(k => [k, data[k]]));
        const json = JSON.stringify(sorted, null, 2) + "\n";
        let bin = ""; for (const b of new TextEncoder().encode(json)) bin += String.fromCharCode(b);
        const body = {
          message: `Update ratings (${entries.length} change${entries.length === 1 ? "" : "s"})`,
          content: btoa(bin), branch: BRANCH, ...(sha ? {sha} : {}),
        };
        const r = await fetch(API, {method: "PUT", headers: {...gh, "Content-Type": "application/json"}, body: JSON.stringify(body)});
        if ((r.status === 409 || r.status === 422) && attempt < 3) continue; // another save landed first: re-read and retry
        if (!r.ok) return reply({error: `GitHub save failed: ${r.status}`}, 502);
        return reply(sorted);
      }
    } catch (e) {
      return reply({error: String(e.message || e)}, 500);
    }
  },
};
