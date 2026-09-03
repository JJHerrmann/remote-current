"""Registry discovery.

Harvest ATS tenant slugs from public URL archives, validate each against the
live jobs endpoint, and (optionally) merge new sources into
companies/companies.json. Runs separately from the hourly crawl so a slow
archive never delays fresh listings -- see docs/source-discovery.md.

    python -m crawler.discover --ats greenhouse                 # dry run
    python -m crawler.discover --ats ashby --source urlscan
    python -m crawler.discover --ats greenhouse --limit 300 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from crawler.pipeline import USER_AGENT, fetch_json

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "companies" / "companies.json"

RESERVED = {"embed", "v1", "boards", "api", "job-boards", "www", "widget", "spi", "job", "jobs", "posting-api"}

ATS: dict[str, dict] = {
    "greenhouse": {
        "hosts": ["boards.greenhouse.io", "job-boards.greenhouse.io"],
        "slug_re": re.compile(r"greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9][a-z0-9_-]+)", re.I),
    },
    "lever": {
        "hosts": ["jobs.lever.co"],
        "slug_re": re.compile(r"jobs\.lever\.co/([a-z0-9][a-z0-9_-]+)", re.I),
    },
    "ashby": {
        "hosts": ["jobs.ashbyhq.com"],
        "slug_re": re.compile(r"jobs\.ashbyhq\.com/([a-z0-9][a-z0-9_-]+)", re.I),
    },
}


def _get(url: str, timeout: int = 60, headers: dict | None = None):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def harvest_wayback(host: str, limit: int) -> set[str]:
    # Best effort: the CDX index is slow to collapse over a high-volume host and
    # can time out. A partial or empty result just means a thin run this week.
    url = (
        "http://web.archive.org/cdx/search/cdx?"
        f"url={urllib.parse.quote(host)}/*&output=json&fl=original&collapse=urlkey"
        f"&filter=statuscode:200&limit={limit}"
    )
    try:
        rows = _get(url, timeout=150)
    except Exception as exc:
        print(f"  wayback {host}: {exc}", file=sys.stderr)
        return set()
    return {row[0] for row in rows[1:]} if isinstance(rows, list) and rows else set()


def harvest_urlscan(host: str, limit: int) -> set[str]:
    # urlscan's search API paginates and handles large hosts well. An API key in
    # URLSCAN_API_KEY lifts the unauthenticated rate limit.
    query = urllib.parse.quote(f"domain:{host}")
    headers = {}
    if os.environ.get("URLSCAN_API_KEY"):
        headers["API-Key"] = os.environ["URLSCAN_API_KEY"]
    try:
        data = _get(f"https://urlscan.io/api/v1/search/?q={query}&size={min(limit, 10000)}", headers=headers)
    except Exception as exc:
        print(f"  urlscan {host}: {exc}", file=sys.stderr)
        return set()
    return {r["page"]["url"] for r in data.get("results", []) if r.get("page", {}).get("url")}


HARVESTERS = {"wayback": harvest_wayback, "urlscan": harvest_urlscan}


def validate(ats: str, slug: str) -> dict | None:
    """Return a registry entry if the slug resolves to a live board with jobs."""
    try:
        if ats == "greenhouse":
            jobs = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs").get("jobs", [])
            name = None
            try:
                name = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}").get("name")
            except Exception:
                pass
        elif ats == "lever":
            jobs, name = fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json"), None
        elif ats == "ashby":
            jobs = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}").get("jobs", [])
            name = None
        else:
            return None
    except Exception:
        return None
    if not jobs:
        return None
    return {"name": name or slug, "type": ats, "key": slug}


def _write_registry(entries: list[dict]) -> None:
    body = ",\n".join(f"  {json.dumps(entry, ensure_ascii=False)}" for entry in entries)
    REGISTRY.write_text(f"[\n{body}\n]\n", encoding="utf-8")


def discover(ats: str, source: str, limit: int, apply: bool, sleep: float) -> int:
    spec = ATS[ats]
    harvest = HARVESTERS[source]
    urls: set[str] = set()
    for host in spec["hosts"]:
        try:
            urls |= harvest(host, limit * 4)
        except Exception as exc:
            print(f"  {source} {host}: {exc}", file=sys.stderr)

    slugs = set()
    for url in urls:
        match = spec["slug_re"].search(url)
        if match:
            slug = match.group(1).lower().strip("-_")
            if slug and slug not in RESERVED:
                slugs.add(slug)

    registry = json.loads(REGISTRY.read_text())
    have = {(entry["type"], str(entry["key"]).lower()) for entry in registry}
    candidates = sorted(slug for slug in slugs if (ats, slug) not in have)
    print(f"{ats} via {source}: {len(urls)} urls -> {len(slugs)} slugs -> {len(candidates)} new to try")

    found: list[dict] = []
    for slug in candidates[:limit]:
        entry = validate(ats, slug)
        if entry:
            found.append(entry)
            print(f"  + {entry['name']}  ({ats}:{slug})")
        time.sleep(sleep)

    print(f"{ats}: {len(found)} live boards found" + ("" if apply else " (dry run; pass --apply to merge)"))
    if apply and found:
        _write_registry(registry + found)
        print(f"merged {len(found)} into {REGISTRY} (formatting normalised to one entry per line)")
    return len(found)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ats", choices=sorted(ATS), required=True)
    parser.add_argument("--source", choices=sorted(HARVESTERS), default="wayback")
    parser.add_argument("--limit", type=int, default=150, help="max slugs to validate")
    parser.add_argument("--sleep", type=float, default=0.3, help="seconds between validation calls")
    parser.add_argument("--apply", action="store_true", help="merge live boards into companies.json")
    args = parser.parse_args()
    discover(args.ats, args.source, args.limit, args.apply, args.sleep)


if __name__ == "__main__":
    main()
