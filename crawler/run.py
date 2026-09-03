#!/usr/bin/env python3
import json
from pathlib import Path
from crawler.pipeline import collect, write_dataset

ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    companies = json.loads((ROOT / "companies" / "companies.json").read_text())
    output = ROOT / "data" / "jobs.json"
    previous = json.loads(output.read_text()).get("jobs", []) if output.exists() else []
    jobs, errors = collect(companies, previous)
    write_dataset(ROOT, jobs, errors)
    print(f"Collected {len(jobs)} remote jobs from {len(companies) - len(errors)}/{len(companies)} sources")
    for error in errors:
        print(f"ERROR {error['company']}: {error['error']}")
    if len(errors) == len(companies):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
