// RemoteCurrent preview worker.
//
// Fetches the real, live posting for one listing and returns a short,
// structured preview -- title, company, an excerpt of the actual description,
// and parsed salary -- so a visitor can screen a listing before deciding to
// click "Apply direct". Nothing here is stored: every request re-fetches the
// employer's own page fresh (subject to Cloudflare's HTTP cache, see the `cf`
// fetch options below).
//
// Security note: this endpoint takes a `job` id, never a raw `url`. The only
// URLs ever fetched are ones already present in RemoteCurrent's own published,
// crawler-vetted data/jobs.json -- that dataset is the trust boundary, and is
// exactly what keeps this from being an open URL-fetching proxy.
//
// See docs/source-tiering.md (crawler side) and README.md in this folder
// (deploy steps) for the rest of the picture.

import { extractJobPostings, summarizePosting } from "./extract.js";

const DATASET_URL = "https://jjherrmann.github.io/remote-current/data/jobs.json";
const USER_AGENT = "RemoteCurrent-Preview/0.1 (+https://github.com/JJHerrmann/remote-current)";
const ALLOWED_ORIGINS = new Set(["https://jjherrmann.github.io", "http://localhost:8000", "http://127.0.0.1:8000"]);

function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.has(origin) ? origin : "https://jjherrmann.github.io";
  return { "Access-Control-Allow-Origin": allow, "Access-Control-Allow-Methods": "GET, OPTIONS", "Vary": "Origin" };
}

function json(body, status, origin) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...corsHeaders(origin) } });
}

async function loadDataset() {
  // Cloudflare's edge cache, not KV/Durable Objects -- free-tier friendly,
  // and the dataset itself only changes hourly.
  const response = await fetch(DATASET_URL, { headers: { "User-Agent": USER_AGENT }, cf: { cacheTtl: 300, cacheEverything: true } });
  if (!response.ok) throw new Error(`dataset fetch failed: ${response.status}`);
  return response.json();
}

async function fetchPosting(job) {
  const targetUrl = job.url;
  const upstream = await fetch(targetUrl, { headers: { "User-Agent": USER_AGENT, Accept: "text/html" }, cf: { cacheTtl: 3600, cacheEverything: true } });
  if (!upstream.ok) throw new Error(String(upstream.status));
  const html = await upstream.text();
  const postings = extractJobPostings(html);
  return { targetUrl, posting: postings[0] || null };
}

export default {
  async fetch(request) {
    const origin = request.headers.get("Origin") || "";
    if (request.method === "OPTIONS") return new Response(null, { headers: corsHeaders(origin) });
    if (request.method !== "GET") return json({ ok: false, reason: "method_not_allowed" }, 405, origin);

    const url = new URL(request.url);
    if (url.pathname !== "/preview") return json({ ok: false, reason: "not_found" }, 404, origin);

    const jobId = url.searchParams.get("job");
    if (!jobId) return json({ ok: false, reason: "missing_job_id" }, 400, origin);

    let dataset;
    try {
      dataset = await loadDataset();
    } catch {
      return json({ ok: false, reason: "dataset_unavailable" }, 502, origin);
    }

    const job = (dataset.jobs || []).find((entry) => entry.id === jobId);
    if (!job) return json({ ok: false, reason: "job_not_found" }, 404, origin);

    let targetUrl, posting;
    try {
      ({ targetUrl, posting } = await fetchPosting(job));
    } catch {
      return json({ ok: false, reason: "fetch_failed", sourceUrl: job.url }, 502, origin);
    }

    if (!posting) return json({ ok: false, reason: "no_structured_data", sourceUrl: targetUrl }, 200, origin);
    return json({ ok: true, job: summarizePosting(posting, targetUrl) }, 200, origin);
  },
};
