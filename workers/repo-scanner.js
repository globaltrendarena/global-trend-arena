/**
 * repo-scanner.js — Cloudflare Worker
 *
 * Bridges the "drop a file in and it's found automatically" gap for a static
 * host: it calls the GitHub Contents API for admin-modules/ and pages/ in
 * your repo and returns a flat JSON list, filtered down to files that aren't
 * already listed in config.json's admin_modules / storefront_routes.
 *
 * DEPLOY:
 *   1. Cloudflare dashboard → Workers & Pages → Create Worker → paste this file.
 *   2. Settings → Variables → add a secret named GITHUB_TOKEN
 *      (a fine-grained GitHub PAT with read-only "Contents" access to the repo
 *      is enough — do NOT use a broad-scope token).
 *   3. Note the Worker's URL (https://<name>.<subdomain>.workers.dev) and
 *      paste it into the "Repo Auto-Scan" panel in admin.html along with the
 *      repo in "owner/name" form.
 *
 * CALL:
 *   GET https://<worker>.workers.dev?repo=owner/name&branch=main
 *   -> { "files": [ { "path": "admin-modules/ai-writer.html", "folder": "admin-modules" }, ... ] }
 */

const SCAN_FOLDERS = ["admin-modules", "pages"];

export default {
  async fetch(request, env) {
    // CORS: the admin dashboard runs on a different origin (Cloudflare Pages /
    // wherever it's hosted), so this needs to allow cross-origin GETs.
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const repo = url.searchParams.get("repo");
    const branch = url.searchParams.get("branch") || "main";

    if (!repo || !repo.includes("/")) {
      return json({ error: "Pass ?repo=owner/name" }, 400, corsHeaders);
    }
    if (!env.GITHUB_TOKEN) {
      return json({ error: "Worker is missing the GITHUB_TOKEN secret." }, 500, corsHeaders);
    }

    try {
      // 1. Pull config.json from the repo so we know what's already registered.
      const configFiles = await fetchJsonFile(repo, branch, "config.json", env.GITHUB_TOKEN);
      const known = new Set([
        ...(configFiles.admin_modules || []).map((m) => m.path),
        ...(configFiles.storefront_routes || []).map((r) => r.path),
      ]);

      // 2. List each watched folder and diff against `known`.
      const found = [];
      for (const folder of SCAN_FOLDERS) {
        const entries = await listFolder(repo, branch, folder, env.GITHUB_TOKEN);
        for (const entry of entries) {
          if (entry.type !== "file") continue;
          if (!entry.name.endsWith(".html")) continue;
          if (entry.name.startsWith("_")) continue; // skip _template.html etc.
          if (known.has(entry.path)) continue;
          found.push({ path: entry.path, folder });
        }
      }

      return json({ files: found }, 200, corsHeaders);
    } catch (err) {
      return json({ error: err.message }, 502, corsHeaders);
    }
  },
};

async function githubRequest(path, token) {
  const res = await fetch(`https://api.github.com/repos/${path}`, {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "repo-scanner-worker",
    },
  });
  if (!res.ok) {
    throw new Error(`GitHub API ${res.status} for ${path}`);
  }
  return res.json();
}

async function listFolder(repo, branch, folder, token) {
  try {
    return await githubRequest(`${repo}/contents/${folder}?ref=${branch}`, token);
  } catch (err) {
    // Folder may not exist yet — treat as empty rather than failing the whole scan.
    return [];
  }
}

async function fetchJsonFile(repo, branch, path, token) {
  const meta = await githubRequest(`${repo}/contents/${path}?ref=${branch}`, token);
  const decoded = atob(meta.content.replace(/\n/g, ""));
  return JSON.parse(decoded);
}

function json(body, status, headers) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}
