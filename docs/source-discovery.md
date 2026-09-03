# Source discovery

RemoteCurrent polls public employer career systems directly. It does not need
LinkedIn, Indeed, a commercial jobs API, or an AI call to find a listing.

## How large boards get early listings

The core asset is a registry of employer career sites. Once the ATS vendor and
tenant slug are known, Greenhouse, Lever, Ashby, Recruitee, and SmartRecruiters
expose public machine-readable data used by the employer's own career page.
Polling those feeds hourly finds a job when the employer publishes it, before a
secondary board indexes or receives it.

Workday and bespoke career sites need their own adapters, but the model is the
same: discover the public career endpoint, normalize its records, retain a
stable source ID, and send applicants back to the employer. The Workday CxS and
Phenom adapters follow this pattern. Those feeds are mostly onsite roles, so
each narrows server-side first (`searchText=remote`, `keywords=remote`) and lets
classification make the final call, keeping an hourly crawl bounded.

## Free registry growth

ATS vendors generally do not provide a global customer directory. A sustainable
free discovery loop is:

1. Extract tenant slugs from public URL indexes such as the Wayback Machine CDX,
   Common Crawl, and urlscan.io.
2. Reject malformed paths and individual job IDs.
3. Validate every candidate against the ATS public jobs endpoint.
4. Merge successful candidates into a reviewed registry without deleting known
   sources when an archive misses them.
5. Poll the registry separately from discovery, keeping normal hourly collection
   fast and predictable.

The initial expanded seed set is adapted from the MIT-licensed
[mherzog4/job-boards](https://github.com/mherzog4/job-boards), whose discovery
workflow uses this archive-and-validation approach. RemoteCurrent adds direct
Recruitee and SmartRecruiters adapters and validates every configured source on
each crawl.

## Shipped adapters

- Greenhouse, Lever, Ashby, Recruitee, SmartRecruiters direct ATS boards.
- Workday CxS, keyed by host, tenant, and career-site name. The list rows carry
  no description or real date, so each surviving posting takes one detail call.
- Phenom career sites (for example PepsiCo), keyed by host.
- `jsonld` fallback: fetch a careers URL and parse any server-rendered
  schema.org `JobPosting` blocks (bare, `@graph`, or `ItemList`). Single-page
  apps that inject JSON-LD client-side yield nothing; those need the sitemap
  path below.

## The discovery loop

`crawler/discover.py` implements the archive-and-validate loop for the direct
ATS types (Greenhouse, Lever, Ashby):

1. Harvest candidate URLs for each ATS host from **urlscan.io** (paginated,
   handles high-volume hosts; `URLSCAN_API_KEY` lifts the rate limit) or the
   **Wayback CDX** index (slower, best-effort, times out on popular hosts).
2. Extract the tenant slug with a per-ATS regex; drop reserved path segments.
3. Skip slugs already in `companies.json`.
4. Validate each remaining slug against the live jobs endpoint; keep those with
   at least one posting.
5. With `--apply`, append the survivors to `companies.json` (formatting
   normalises to one entry per line). Without it, print a dry run.

`.github/workflows/discover.yml` runs this weekly, well clear of the hourly job
crawl, and commits any additions. The job registry only grows; a source is
never removed because an archive missed it.

## Next adapters

- Microsoft moved off `gcsservices.careers.microsoft.com` (now a bad cert + 404)
  to `apply.careers.microsoft.com`. The `microsoft` adapter and its registry
  entry are disabled until the new API is mapped onto the normalized shape.
- Apple (`jobs.apple.com`) needs a CSRF token bootstrapped from a page load and
  blocks datacenter IPs; the JSON-LD fallback is the more durable route.
- SAP SuccessFactors career-site OData API — McDonald's (`jobs.mcdonalds.com`)
  runs on it, as do many large non-tech employers.
- Sitemap crawl feeding the `jsonld` adapter, for SPA careers pages and
  employers whose ATS is not identified from static HTML (Yum! Brands).
- Workable and Teamtailor: **not pursued.** Workable's public widget API now
  returns empty job lists without an account token, and Teamtailor's API
  requires auth; both are better reached through `jsonld` or a sitemap crawl if
  they matter later.

Discovery should run daily or weekly. Job polling can run hourly. Keeping those
jobs separate prevents a slow archive service from delaying fresh listings.
