"""We Work Remotely — a Tier-3 discovery source (see docs/source-tiering.md).

WWR is not an employer's own feed, so nothing read from it is ever treated as
canonical. Each listing is resolved (crawler.resolve) against the companies
RemoteCurrent already crawls directly before it can affect the dataset: a
match only adds provenance to the existing canonical row, a miss becomes its
own explicitly non-canonical row. Public per-category RSS feeds; no auth, no
API key.
"""
from __future__ import annotations

import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any

from crawler.pipeline import fetch_text, plain_text

CATEGORIES = [
    "remote-programming-jobs",
    "remote-design-jobs",
    "remote-devops-sysadmin-jobs",
    "remote-product-jobs",
    "remote-customer-support-jobs",
    "remote-sales-and-marketing-jobs",
    "remote-management-and-finance-jobs",
    "all-other-remote-jobs",
]

_ITEM = re.compile(r"<item>(.*?)</item>", re.S)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S)
_LINK = re.compile(r"<link[^>]*>(.*?)</link>", re.S)
_GUID = re.compile(r"<guid[^>]*>(.*?)</guid>", re.S)
_PUBDATE = re.compile(r"<pubDate[^>]*>(.*?)</pubDate>", re.S)
_REGION = re.compile(r"<region[^>]*>(.*?)</region>", re.S)
_DESCRIPTION = re.compile(r"<description[^>]*>(.*?)</description>", re.S)


def _field(pattern: re.Pattern, item: str) -> str:
    match = pattern.search(item)
    return plain_text(match.group(1)) if match else ""


def _iso(pub_date: str) -> str | None:
    try:
        return parsedate_to_datetime(pub_date).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _parse_item(raw: str) -> dict[str, Any] | None:
    # WWR's own convention: "<title>Company: Job Title</title>". A row with no
    # colon is not a normal listing (seen on sponsored/blurb entries) and is
    # skipped rather than guessed at.
    company, _, title = _field(_TITLE, raw).partition(": ")
    if not title:
        return None
    return {
        "company": company.strip(),
        "title": title.strip(),
        "url": _field(_LINK, raw) or _field(_GUID, raw),
        "region": _field(_REGION, raw),
        "description": _field(_DESCRIPTION, raw),
        "publishedAt": _iso(_field(_PUBDATE, raw)),
        "provider": "weworkremotely",
    }


def fetch_category(category: str) -> list[dict[str, Any]]:
    document = fetch_text(f"https://weworkremotely.com/categories/{category}.rss")
    return [item for item in (_parse_item(raw) for raw in _ITEM.findall(document)) if item]


def fetch_listings(categories: list[str] | None = None) -> list[dict[str, Any]]:
    """All discovered listings across the given (default: all) WWR categories,
    de-duplicated by URL -- the same posting often appears in more than one
    category feed."""
    seen: dict[str, dict[str, Any]] = {}
    for category in categories or CATEGORIES:
        for listing in fetch_category(category):
            seen.setdefault(listing["url"], listing)
    return list(seen.values())
