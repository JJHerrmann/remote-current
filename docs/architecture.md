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

## Deployment target

- Scheduled Python crawler on GitHub Actions
- Cloudflare D1 for normalized records
- Cloudflare Worker for the read API
- Static frontend served through Cloudflare
- RSS before email, avoiding early deliverability and privacy overhead

## Explicit non-goals for the MVP

- Accepting or submitting job applications
- Storing resumes or candidate profiles
- Automated mass applications
- Scraping authenticated sources
- Bypassing anti-bot controls
- Selling ranking or preferred placement
