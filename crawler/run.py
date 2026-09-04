#!/usr/bin/env python3
import json
from pathlib import Path
from crawler.pipeline import collect, write_dataset, write_sources
from crawler.feeds import write_feeds
from crawler.resolve import resolve
from crawler.seo import write_sitemap
from crawler.weworkremotely import fetch_listings as fetch_wwr_listings

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, key: str) -> list:
    return json.loads(path.read_text()).get(key, []) if path.exists() else []


def _discover(jobs: list[dict], previous: list[dict]) -> tuple[list[dict], int]:
    """Tier-3 discovery pass: We Work Remotely, resolved against the canonical
    `jobs` this run already collected. Never fatal -- a discovery-source outage
    should not fail the canonical crawl. See docs/source-tiering.md."""
    try:
        discovered = fetch_wwr_listings()
    except Exception as exc:
        print(f"WARN We Work Remotely discovery skipped: {exc}")
        return [], 0
    standalone, unresolved = resolve(discovered, jobs, previous)
    return standalone, len(unresolved)


def main() -> None:
    companies = [c for c in json.loads((ROOT / "companies" / "companies.json").read_text()) if c.get("enabled", True)]
    previous = _load(ROOT / "data" / "jobs.json", "jobs")
    previous_sources = _load(ROOT / "data" / "sources.json", "sources")
    overrides = _load(ROOT / "data" / "overrides.json", "overrides")

    jobs, errors, reports = collect(companies, previous, overrides)
    standalone, unresolved_count = _discover(jobs, previous)
    jobs = jobs + standalone
    jobs.sort(key=lambda job: job.get("postedAt") or job["firstSeenAt"], reverse=True)

    write_dataset(ROOT, jobs, errors)
    write_sources(ROOT, reports, previous_sources)
    feeds = write_feeds(ROOT, jobs)
    write_sitemap(ROOT)

    print(f"Collected {len(jobs)} remote jobs from {len(companies) - len(errors)}/{len(companies)} sources; wrote {len(feeds)} feeds")
    print(f"We Work Remotely discovery: +{len(standalone)} new companies not otherwise tracked, {unresolved_count} at known companies left unmatched")
    for error in errors:
        print(f"ERROR {error['company']}: {error['error']}")
    if len(errors) == len(companies):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
