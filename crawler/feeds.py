from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

SITE_URL = os.environ.get("REMOTECURRENT_SITE_URL", "https://jjherrmann.github.io/remote-current").rstrip("/")
ITEM_CAP = 100  # newest N per feed


def _rfc822(value: str | None) -> str:
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return format_datetime(parsed)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "feed"


def _cdata(text: str) -> str:
    return "<![CDATA[" + str(text or "").replace("]]>", "]]]]><![CDATA[>") + "]]>"


def _item(job: dict[str, Any]) -> str:
    title = " — ".join(part for part in (job.get("title"), job.get("company")) if part)
    summary = " · ".join(str(part) for part in (job.get("company"), job.get("location"), job.get("remoteType"), job.get("source"), job.get("salaryText")) if part)
    return "".join([
        "<item>",
        f"<title>{_cdata(title)}</title>",
        f"<link>{escape(job.get('url') or SITE_URL)}</link>",
        f'<guid isPermaLink="false">{escape("remotecurrent:" + (job.get("id") or ""))}</guid>',
        f"<pubDate>{_rfc822(job.get('postedAt') or job.get('firstSeenAt'))}</pubDate>",
        f"<category>{escape(job.get('remoteType') or 'remote')}</category>",
        f"<description>{_cdata(summary)}</description>",
        "</item>",
    ])


def _feed(title: str, description: str, path: str, jobs: list[dict[str, Any]]) -> str:
    self_url = f"{SITE_URL}/feeds/{path}"
    return "".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
        f"<title>{escape(title)}</title>",
        f"<link>{SITE_URL}/</link>",
        f'<atom:link href="{escape(self_url)}" rel="self" type="application/rss+xml"/>',
        f"<description>{escape(description)}</description>",
        "<language>en</language>",
        f"<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>",
        "<ttl>60</ttl>",
        "".join(_item(job) for job in jobs[:ITEM_CAP]),
        "</channel></rss>",
    ])


def write_feeds(root: Path, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Write standing RSS feeds plus feeds/index.json; return the catalog."""
    feeds_dir = root / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    ordered = sorted(jobs, key=lambda job: job.get("postedAt") or job.get("firstSeenAt") or "", reverse=True)
    catalog: list[dict[str, Any]] = []

    def emit(title: str, description: str, path: str, subset: list[dict[str, Any]]) -> None:
        if not subset:
            return
        (feeds_dir / path).write_text(_feed(title, description, path, subset), encoding="utf-8")
        catalog.append({"title": title, "path": f"feeds/{path}", "count": len(subset)})

    emit("RemoteCurrent — all remote jobs", "Every remote listing, newest first.", "all.xml", ordered)
    emit("RemoteCurrent — worldwide remote", "Remote jobs with no country or region restriction.", "worldwide.xml", [job for job in ordered if job.get("remoteType") == "worldwide"])
    emit("RemoteCurrent — jobs that list pay", "Remote listings that disclose a salary range.", "with-salary.xml", [job for job in ordered if job.get("salaryText")])

    for source in sorted({job.get("source") for job in ordered if job.get("source")}):
        emit(f"RemoteCurrent — {source} sources", f"Remote jobs collected from {source}.", f"source-{_slug(source)}.xml", [job for job in ordered if job.get("source") == source])

    for company in sorted({job.get("company") for job in ordered if job.get("company")}):
        emit(f"RemoteCurrent — {company}", f"Current remote roles at {company}.", f"company-{_slug(company)}.xml", [job for job in ordered if job.get("company") == company])

    (feeds_dir / "index.json").write_text(json.dumps({"generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "feeds": catalog}, ensure_ascii=False), encoding="utf-8")
    return catalog
