"""Shared listing-date rules.

ATS providers sometimes refresh ``publishedAt`` on an existing requisition.  A
listing should not become "new" again when its stable ID has already been in
our dataset, so freshness uses the earliest trustworthy public timestamp:
the employer's posted date or RemoteCurrent's first-seen date.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parsed(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def listing_datetime(job: dict[str, Any]) -> datetime:
    """Return the earliest valid posted/first-seen timestamp for a listing."""
    values = [_parsed(job.get("postedAt")), _parsed(job.get("firstSeenAt"))]
    return min((value for value in values if value is not None), default=datetime.min.replace(tzinfo=timezone.utc))


def listing_date(job: dict[str, Any]) -> str | None:
    """Return the original timestamp string selected by ``listing_datetime``."""
    candidates = []
    for key in ("postedAt", "firstSeenAt"):
        value = job.get(key)
        parsed = _parsed(value)
        if parsed is not None:
            candidates.append((parsed, str(value)))
    return min(candidates, default=(None, None), key=lambda item: item[0])[1]
