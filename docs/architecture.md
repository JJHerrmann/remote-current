# Architecture

## Acquisition

Start with reviewed companies and documented or deliberately public ATS job
feeds. Each adapter returns the same normalized representation while retaining
the original payload for debugging.

Initial adapters:

- Greenhouse Job Board API
- Lever Postings API
- Ashby public job-posting API

Generic HTML and JSON-LD collection comes later and must respect each site's
robots policy, rate limits, and terms.

## Job lifecycle

```text
new -> active -> suspected_closed -> closed
          ^              |
          +--------------+
```

A job is not closed because of one missing or failed request. Source-wide
failures must not modify individual job status. Reappearance reactivates a job
and records a lifecycle event.

## Remote classification

The internal model distinguishes:

- worldwide
- country restricted
- region restricted
- timezone restricted
- remote near office
- hybrid
- temporarily remote
- unclear
- not remote

Structured source fields and deterministic phrase rules run first. An AI
classifier may process only unresolved listings, must return schema-constrained
JSON, must quote evidence present in the listing, and is cached by content hash.

## Trust model

Public records should expose source, canonical application URL, first-seen
time, last-verified time, remote-classification confidence, and supporting
evidence. Manual corrections live as versioned overrides with an explanation.

`data/overrides.json` holds those corrections, keyed by job `id`
(`data/overrides.example.json` shows the shape). Each entry names an `action`,
a human `reason`, and an `addedAt` date:

- `drop` / `not_remote` removes a listing the classifier should not have kept.
- `set_scope` pins `remoteType` to `value` and sets confidence to 1.0.

`crawler.pipeline.apply_overrides` applies them during collection and stamps the
surviving change onto the job as `correction`. The file is reviewed input, like
the company registry, and its git history is the audit trail.

Per-source health is published to `data/sources.json` each run: fetch count,
visible remote count, average classification confidence, scope mix, last
successful run, and any error. The `/sources` page renders it.

**Discovery vs. canonical.** Not every source is the employer's own feed. A
job record's `canonical` flag, `discoveryProvider`/`discoveryUrl`, and
optional `discoveredVia` list make that distinction explicit rather than
letting the same requisition become a second row because a different site
happened to list it first. See `docs/source-tiering.md` for the tier model
and `crawler/resolve.py` for the matching logic.

## Deployment target

- Scheduled Python crawler on GitHub Actions
- Cloudflare D1 for normalized records
- Cloudflare Worker for the read API
- Static frontend served through Cloudflare
- RSS before email, avoiding early deliverability and privacy overhead

**Built, not yet deployed:** `worker/` holds a first Cloudflare Worker --
not the D1-backed read API above, but a narrower `/preview?job=<id>` fetch-
on-demand endpoint (no storage; live employer-page fetch through Cloudflare's
HTTP cache) backing the frontend's per-listing preview. See
`worker/README.md` for coverage, deploy steps, and cost. `index.html` is
wired for it behind a `PREVIEW_API` constant (currently `null`, i.e. off) --
set that constant to the deployed `*.workers.dev` URL to turn previews on.

## Explicit non-goals for the MVP

- Accepting or submitting job applications
- Storing resumes or candidate profiles
- Automated mass applications
- Scraping authenticated sources
- Bypassing anti-bot controls
- Selling ranking or preferred placement
