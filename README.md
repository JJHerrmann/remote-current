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

## Current architecture

```text
Company registry
      |
      v
ATS collectors (Greenhouse, Lever, Ashby, Recruitee, SmartRecruiters)
      |
      v
Normalization -> remote classification -> stable IDs
      |
      v
Versioned JSON dataset
      |
      v
Static filterable GitHub Pages board
```

The crawler runs hourly through GitHub Actions and deploys the static site and
dataset to GitHub Pages. Applications remain on the employer's own site. A
database, API, feeds, and alerts can be added once the collection quality is
proven.

## First milestone

1. Normalize Greenhouse, Lever, Ashby, Recruitee, and SmartRecruiters listings.
2. Track first-seen and last-verified timestamps with stable job IDs.
3. Classify remote scope and extract visible salary ranges.
4. Publish a searchable, filterable static board.
5. Grow the reviewed employer registry and measure classifier accuracy.

See [docs/architecture.md](docs/architecture.md) for the working technical
plan and [companies/companies.example.yaml](companies/companies.example.yaml)
for the proposed source registry format.

## Funding

RemoteCurrent will be free to browse. Voluntary support may be accepted through
Ko-fi to help cover the domain, hosting, email, and classification costs.

## Run locally

```bash
python -m unittest discover -s tests
python -m crawler.run
python -m http.server 8000
```

Then open `http://localhost:8000`. The committed registry currently covers 70
employers across five ATS families. GitHub Actions refreshes the dataset hourly
and deploys the static board to GitHub Pages.

The expanded seed set was adapted from the MIT-licensed
[mherzog4/job-boards](https://github.com/mherzog4/job-boards) project, then
live-validated by this crawler. See
[docs/source-discovery.md](docs/source-discovery.md) for the free discovery
model that grows coverage without depending on LinkedIn or Indeed.

## Status

Pre-alpha. The first end-to-end board is live; source coverage and filter
accuracy are deliberately small enough to inspect while the parsers mature.

## License

Code is licensed under the MIT License. The license does not grant rights to
third-party job descriptions, company names, trademarks, or source data.
