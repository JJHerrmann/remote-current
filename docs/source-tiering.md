# Source tiering

RemoteCurrent's coverage comes from three structurally different kinds of
source, not one feed. Treating them as equivalent is how a job board ends up
with the same requisition four times over, wearing four different hats.

## The tiers

**Tier 1 — canonical.** The employer's own feed: Greenhouse, Lever, Ashby,
Workable, SmartRecruiters, iCIMS, Workday, Jobvite, Taleo/Oracle Recruiting,
ADP Recruiting, Paylocity, BambooHR, Recruitee, or a career page's own
schema.org `JobPosting` markup. This is ground truth for that employer: the
requisition ID, the real apply URL, the real posting date. `crawler.pipeline`
reads Tier 1 only, and does so directly against each employer's own API —
never through an intermediary.

**Tier 2 — aggregators / distributors.** Indeed, ZipRecruiter, LinkedIn,
Appcast, Ocelot. These mirror Tier 1 postings (sometimes through a paid
distribution pipe an employer pays into) rather than originating them. Not
ingested today.

**Tier 3 — remote-specific boards.** We Work Remotely, Remote OK, Working
Nomads, Remotive, FlexJobs, Wellfound, Built In, Remote.co, Himalayas,
Jobspresso, Dynamite Jobs. Editorial or self-serve boards, not an employer
feed. **We Work Remotely is the first one wired in** (`crawler.weworkremotely`)
as the pilot for this whole mechanism — public RSS, no key, no ToS risk.
Indeed/LinkedIn scraping was deliberately not chosen as the pilot: no public
API for this use case, and scraping the rendered site is exactly the kind of
fragile, adversarial dependency the project's [not doing](roadmap.md#not-doing)
list already rules out for the RTO giants.

## The rule

```
discovery_source != canonical_source
```

A listing's *discovery* provenance (where RemoteCurrent found out about it)
and its *canonical* identity (the employer's own feed and apply link) are
different things, and only the canonical one should ever produce a row in the
dataset. Example flow:

```
We Work Remotely lists "Samsara: Staff Software Engineer"
  -> normalize company + title
  -> already crawled canonically via Samsara's own Greenhouse board
  -> record WWR as discovery provenance on that existing row
  -> do NOT create a second "Staff Software Engineer" row
```

## What's on each job record

Every row already carried `source` / `url` / `sourceId` (canonical provider,
canonical apply URL, requisition ID) and `firstSeenAt` / `lastSeenAt`. Two
kinds of record now exist:

- **Canonical rows** (the vast majority — anything from `crawler.pipeline`):
  gain `canonical: true`, `discoveryProvider` (= the ATS, same as `source`),
  `discoveryUrl` (= the apply URL, same as `url`) for schema symmetry, and an
  optional `discoveredVia: [{provider, url, firstSeenAt}, ...]` list recording
  every non-canonical source that independently surfaced the same posting.
- **Standalone discovery rows** (Tier 2/3 listings at a company RemoteCurrent
  has no canonical feed for): `canonical: false`, `source` and
  `discoveryProvider` both set to the discovery provider (e.g.
  `"weworkremotely"`), because there is nothing more canonical to fall back
  to. Classified with the same `classify_remote` / `parse_salary` /
  `classify_experience` logic as every other row, so filters behave
  identically regardless of where a listing came from.

## Matching

`crawler.resolve` does the work: `normalize_company` (casefold, strip legal
suffixes and punctuation) groups canonical jobs by company; a discovered
listing's company is looked up there. `normalize_title` + a token-overlap
check (≥ 0.8) decides whether it is the *same* posting.

Three outcomes:

1. **Company found, title matched** → provenance only, no new row.
2. **Company found, no title matched** → left unresolved. Logged (see
   `crawler.run._discover`'s print line), never written. A company we already
   crawl canonically is trusted as complete for that company; an unmatched
   title is treated as wording drift rather than a gap, to keep duplicate
   risk at zero. (In practice this is also a useful signal that our own
   canonical crawl may be capped or paginated short — see Open threads.)
3. **Company not found at all** → a standalone, explicitly non-canonical row.
   This is where Tier 3 actually grows coverage: small or remote-first
   companies with no ATS in `companies/companies.json` yet.

A live run against the current dataset (2026-09-04) found 232 WWR listings,
resolved 15 as provenance on existing canonical rows (Databricks, GitLab,
Reddit, Coinbase, Samsara, and others — proving the same requisition really
does get cross-posted), added 3 new standalone companies, and left 4 listings
at known companies (Webflow, Reddit, NVIDIA, Zoom) unresolved — worth a manual
look, since Workday's per-tenant `WORKDAY_LIST_CAP` / `WORKDAY_DETAIL_CAP`
mean the canonical crawl can legitimately miss postings a board like WWR still
sees.

## Tier-1 coverage gap

Adapters that exist today: `greenhouse`, `lever`, `ashby`, `recruitee`,
`smartrecruiters`, `workday`, `phenom`, `jsonld` (`microsoft` retired, see
`crawler/pipeline.py`). Not yet built: iCIMS, Jobvite, Taleo/Oracle
Recruiting, ADP Recruiting, Paylocity, BambooHR. Each is the same shape as the
existing adapters in `crawler/pipeline.py` — a fetch function returning
`normalize(...)` calls, registered in `ADAPTERS`.
