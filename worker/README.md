# RemoteCurrent preview worker

Fetches the real, live posting for one listing (by `job` id, looked up
against RemoteCurrent's own published `data/jobs.json`) and returns a short
structured preview: title, company, an excerpt of the actual description, and
parsed salary. Nothing is stored -- every request re-fetches the employer's
page fresh, subject only to Cloudflare's HTTP cache (1h per posting, 5min for
the dataset lookup).

See `src/index.js` and `../docs/source-tiering.md` for the reasoning; this
file is only the "how to run it" half.

## Why a Cloudflare Worker

A browser can't fetch arbitrary employer domains directly (CORS), and this
needed to run *somewhere* server-side. A Worker matches
[`docs/architecture.md`](../docs/architecture.md)'s existing "Deployment
target" plan (a Cloudflare Worker for the read API), needs no server to
manage, and the free tier (workers.dev subdomain, 100k requests/day) covers
this comfortably -- **no move off GitHub Pages required**; the main site stays
exactly where it is, this is a small standalone endpoint the frontend calls.

## Extraction coverage (honest, as tested 2026-09-04)

Generic `application/ld+json` `JobPosting` extraction, one path for every
source rather than re-implementing every ATS adapter in JavaScript. Checked
against one live listing per ATS currently in the registry:

| ATS | Preview works? |
|---|---|
| Ashby | yes -- real title/company/description extracted |
| Lever | yes |
| Recruitee | yes |
| Greenhouse (branded career-page URLs) | **no** -- the stored apply URL is the employer's own branded page (e.g. `coinbase.com/careers/...`), which 403'd on a plain fetch. The crawler itself doesn't hit this URL either -- it calls Greenhouse's clean `boards-api.greenhouse.io` JSON API using the company's registry `key`, which this worker doesn't currently look up. |
| SmartRecruiters | **no** -- page loads (200) but doesn't server-render JSON-LD |
| Workday | **no** -- the branded job page is a thin SPA shell; content loads client-side after the fact, same reason `crawler/pipeline.py`'s `workday()` adapter uses a two-step search+detail API instead of scraping the page |
| We Work Remotely (standalone/discovery rows) | untested here, but WWR's own posting pages are plain server-rendered HTML -- likely to need the same JSON-LD path or a small HTML fallback; check before relying on it |

Ashby alone covers 43 of the 108 companies in `companies/companies.json` (the
largest single group), so this is a genuinely useful first cut, not a token
gesture -- but Greenhouse/SmartRecruiters/Workday together are a similar-sized
chunk of the registry with **no preview today**, and a visitor gets an honest
"preview not available, Apply direct" for those rather than a broken one.

**Follow-up, not done:** for the known-gap ATS types, look up the company's
`{type, key}` from `companies/companies.json` (also public via GitHub Pages)
and call that ATS's own clean JSON API directly -- the same shape
`crawler/pipeline.py`'s adapters already use -- instead of scraping the
branded frontend page. That closes Greenhouse/SmartRecruiters immediately;
Workday would still need the two-step detail fetch.

## One-time setup (needs your Cloudflare account -- nothing here can do this for you)

```sh
cd worker
npx wrangler login      # opens a browser, authorizes this machine once
npx wrangler deploy     # publishes to https://remotecurrent-preview.<your-subdomain>.workers.dev
```

No custom domain, no DNS change, no credit card required for the free tier.
Note the `*.workers.dev` URL `wrangler deploy` prints -- the frontend needs it
(see `PREVIEW_API` in `index.html`, currently a commented placeholder,
same pattern as the GoatCounter snippet).

## Local testing

```sh
node --test test/            # pure extraction logic, no network, no wrangler
npx wrangler dev              # runs the actual worker locally against real network calls
```

## Operating cost

Free tier: 100,000 requests/day, no card on file historically for Workers
(confirm at signup -- Cloudflare's terms can change). Each page view that
opens a preview costs at most 2 requests (dataset lookup, usually cached;
the employer page fetch). Comfortably within free-tier limits at RemoteCurrent's
current traffic.
