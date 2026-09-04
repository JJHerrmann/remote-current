"""Resolve Tier-2/3 discovery listings against the canonical dataset.

RemoteCurrent's own adapters (crawler.pipeline.ADAPTERS) read employer ATS
feeds directly and are canonical: `source` is the ATS, `url` is the real
apply link. Everything else -- job boards, aggregators, distribution networks
-- is discovery only, and discovery_source != canonical_source: see
docs/source-tiering.md. A discovered {company, title, url, ...} either

  - matches a company + posting RemoteCurrent already has canonically, in
    which case it only adds provenance (`discoveredVia`) to that existing
    record and is never written as a second row, or
  - matches no known canonical posting, in which case it becomes its own
    standalone record, explicitly marked `canonical: False`, so coverage
    still grows without pretending the discovery source is the employer's
    own feed.

Company/title matching is deliberately conservative: a company match with no
title match is left unresolved (logged, not written) rather than risk a
duplicate row for a posting our canonical crawl may already carry under
slightly different wording.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from crawler.pipeline import DROPPED_SCOPES, classify_employment, classify_experience, classify_remote, parse_salary

_SUFFIX = re.compile(r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|plc|gmbh|sa|srl|bv)\.?\b", re.I)
_PUNCT = re.compile(r"[^\w\s]")
_SPACE = re.compile(r"\s+")
_TITLE_NOISE = re.compile(r"\((?:remote|hybrid|contract|full[- ]time|part[- ]time)\)|\b(?:remote|hybrid)\b", re.I)
_MIN_TITLE_OVERLAP = 0.8


def normalize_company(name: str) -> str:
    value = _PUNCT.sub(" ", name or "").casefold()
    value = _SUFFIX.sub(" ", value)
    return _SPACE.sub(" ", value).strip()


def normalize_title(title: str) -> str:
    value = _TITLE_NOISE.sub(" ", title or "")
    value = _PUNCT.sub(" ", value).casefold()
    return _SPACE.sub(" ", value).strip()


def _title_match(a: str, b: str) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / max(1, min(len(ta), len(tb))) >= _MIN_TITLE_OVERLAP


def index_by_company(jobs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        index.setdefault(normalize_company(job["company"]), []).append(job)
    return index


def _standalone_job(item: dict[str, Any]) -> dict[str, Any]:
    description = item.get("description") or ""
    remote = classify_remote(item.get("region") or "", description)
    salary = parse_salary(description)
    stable = f"{item['provider']}:{item['url']}"
    return {
        "id": hashlib.sha256(stable.encode()).hexdigest()[:20],
        "sourceId": item["url"],
        "source": item["provider"],
        "company": item["company"],
        "title": re.sub(r"\s+", " ", item["title"]).strip(),
        "location": item.get("region") or "Not specified",
        "department": None,
        "employmentType": None,
        "employmentCategory": classify_employment(None),
        "experienceLevel": classify_experience(item["title"]),
        "experienceInferred": True,
        "url": item["url"],
        "postedAt": item.get("publishedAt"),
        "remoteType": remote["type"],
        "remoteConfidence": remote["confidence"],
        "remoteEvidence": remote["evidence"],
        "salaryMin": salary["min"],
        "salaryMax": salary["max"],
        "salaryCurrency": salary["currency"],
        "salaryText": salary["text"],
        "canonical": False,
        "discoveryProvider": item["provider"],
        "discoveryUrl": item["url"],
    }


def resolve(
    discovered: list[dict[str, Any]],
    canonical_jobs: list[dict[str, Any]],
    previous: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge `discovered` listings against `canonical_jobs` (mutated in place
    to add `discoveredVia` on matches). Returns (standalone, unresolved):
    ready-to-append non-canonical job rows, and the raw discovered items at
    known companies that could not be matched to a specific canonical posting
    (for visibility only -- never written to the dataset)."""
    by_company = index_by_company(canonical_jobs)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    old = {job["id"]: job for job in (previous or [])}
    standalone, unresolved = [], []
    for item in discovered:
        candidates = by_company.get(normalize_company(item["company"]))
        if candidates is None:
            job = _standalone_job(item)
            if job["remoteType"] in DROPPED_SCOPES:
                continue
            job["firstSeenAt"] = old.get(job["id"], {}).get("firstSeenAt", now)
            job["lastSeenAt"] = now
            standalone.append(job)
            continue
        match = next((job for job in candidates if _title_match(job["title"], item["title"])), None)
        if match is None:
            unresolved.append(item)
            continue
        provenance = {"provider": item["provider"], "url": item["url"], "firstSeenAt": item.get("publishedAt") or now}
        existing = match.setdefault("discoveredVia", [])
        if not any(p["provider"] == provenance["provider"] and p["url"] == provenance["url"] for p in existing):
            existing.append(provenance)
    return standalone, unresolved
