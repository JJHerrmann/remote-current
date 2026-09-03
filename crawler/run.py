#!/usr/bin/env python3
import json
from pathlib import Path
from crawler.pipeline import collect, write_dataset, write_sources
from crawler.feeds import write_feeds
from crawler.seo import write_sitemap

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, key: str) -> list:
    return json.loads(path.read_text()).get(key, []) if path.exists() else []


def main() -> None:
    companies = [c for c in json.loads((ROOT / "companies" / "companies.json").read_text()) if c.get("enabled", True)]
    previous = _load(ROOT / "data" / "jobs.json", "jobs")
    previous_sources = _load(ROOT / "data" / "sources.json", "sources")
    overrides = _load(ROOT / "data" / "overrides.json", "overrides")

    jobs, errors, reports = collect(companies, previous, overrides)
    write_dataset(ROOT, jobs, errors)
    write_sources(ROOT, reports, previous_sources)
    feeds = write_feeds(ROOT, jobs)
    write_sitemap(ROOT)

    print(f"Collected {len(jobs)} remote jobs from {len(companies) - len(errors)}/{len(companies)} sources; wrote {len(feeds)} feeds")
    for error in errors:
        print(f"ERROR {error['company']}: {error['error']}")
    if len(errors) == len(companies):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
