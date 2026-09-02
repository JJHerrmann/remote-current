# RemoteCurrent

Fresh remote jobs, direct from employers. Free forever.

RemoteCurrent is an open, donation-supported index of remote jobs collected
from employer career pages and public applicant-tracking-system job feeds.

## Principles

- No accounts required to search.
- No paywalled listings or application links.
- Every job links to the employer's original application page.
- Every job shows its source, first-seen time, and last-verified time.
- Remote-location restrictions are explicit and evidence-backed.
- Employers cannot buy ranking priority.
- Deterministic parsers come first; AI is reserved for ambiguous text.
- Collection methods and corrections remain inspectable.

## Initial architecture

```text
Company registry
      |
      v
ATS collectors (Greenhouse, Lever, Ashby)
      |
      v
Normalization -> remote classification -> deduplication
      |
      v
SQLite locally / Cloudflare D1 in production
      |
      +-- Search API
      +-- Public web interface
      +-- RSS feeds
      +-- Optional email digests
```

The crawler will run on a schedule through GitHub Actions. The public site and
API are intended for Cloudflare Workers, static assets, and D1. Applications
remain on the employer's own site.

## Planned first milestone

1. Define the normalized job schema and SQLite migrations.
2. Implement Greenhouse, Lever, and Ashby collectors.
3. Seed 50 reviewed remote-friendly employers.
4. Track first seen, last seen, and closure state.
5. Add deterministic remote-scope and salary parsing.
6. Serve a searchable local prototype.

See [docs/architecture.md](docs/architecture.md) for the working technical
plan and [companies/companies.example.yaml](companies/companies.example.yaml)
for the proposed source registry format.

## Funding

RemoteCurrent will be free to browse. Voluntary support may be accepted through
Ko-fi to help cover the domain, hosting, email, and classification costs.

## Status

Pre-alpha. The repository currently captures the project charter and intended
architecture; collection code has not been implemented yet.

## License

Code is licensed under the MIT License. The license does not grant rights to
third-party job descriptions, company names, trademarks, or source data.
