# Source discovery

RemoteCurrent polls public employer career systems directly. It does not need
LinkedIn, Indeed, a commercial jobs API, or an AI call to find a listing.

## How large boards get early listings

The core asset is a registry of employer career sites. Once the ATS vendor and
tenant slug are known, Greenhouse, Lever, Ashby, Recruitee, and SmartRecruiters
expose public machine-readable data used by the employer's own career page.
Polling those feeds hourly finds a job when the employer publishes it, before a
secondary board indexes or receives it.

Workday and bespoke career sites require additional adapters, but the model is
the same: discover the public career endpoint, normalize its records, retain a
stable source ID, and send applicants back to the employer.

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

## Next adapters

- Workday CXS, keyed by host, tenant, and career-site name.
- Workable and Teamtailor public career endpoints.
- Bespoke JSON-LD `JobPosting` pages as the standards-based fallback.
- Sitemap and careers-page discovery for employers whose ATS is not yet known.

Discovery should run daily or weekly. Job polling can run hourly. Keeping those
jobs separate prevents a slow archive service from delaying fresh listings.
