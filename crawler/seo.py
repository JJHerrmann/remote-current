"""Search-discoverability build steps.

`write_sitemap` emits sitemap.xml. `prerender` bakes the newest listings and an
ItemList into a static copy of index.html so crawlers see real job content
instead of an empty single-page app. Both run at deploy time; see
.github/workflows/pages.yml.
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SITE_URL = os.environ.get("REMOTECURRENT_SITE_URL", "https://jjherrmann.github.io/remote-current").rstrip("/")
PRERENDER_ROWS = 40

PAGES = [("/", "1.0"), ("/sources.html", "0.5"), ("/about.html", "0.5")]

_SCOPE = {
    "worldwide": ("Worldwide", "open"),
    "region_restricted": ("Region-restricted", "sig"),
    "country_restricted": ("Country-restricted", "sig"),
    "remote_unspecified": ("Scope unclear", ""),
}
_EXP = {"internship": "Internship", "entry": "Entry", "mid": "Mid", "senior": "Senior",
        "lead": "Staff / lead", "manager": "Manager", "director": "Director", "executive": "Executive"}
_EMP = {"full_time": "Full-time", "part_time": "Part-time", "contract": "Contract", "internship": "Internship"}


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def write_sitemap(root: Path, site_url: str = SITE_URL) -> str:
    stamp = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{site_url}{path}</loc><lastmod>{stamp}</lastmod>"
        f"<priority>{priority}</priority></url>"
        for path, priority in PAGES
    )
    doc = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'
    (root / "sitemap.xml").write_text(doc, encoding="utf-8")
    return doc


def _rel(hours: float) -> str:
    if hours < 1:
        return "under 1h"
    if hours < 24:
        return f"{round(hours)}h"
    if hours < 24 * 14:
        return f"{round(hours / 24)}d"
    return f"{round(hours / 168)}w"


def _row_html(job: dict[str, Any], now: datetime) -> str:
    posted = job.get("postedAt") or job.get("firstSeenAt")
    try:
        hours = (now - datetime.fromisoformat(str(posted).replace("Z", "+00:00"))).total_seconds() / 3600
    except (TypeError, ValueError):
        hours = 999.0
    fresh = max(0.0, min(1.0, 1 - hours / 72))
    lit = round(fresh * 4)
    bars = "".join(f'<i class="{"on" if i <= lit else ""}"></i>' for i in range(1, 5))
    scope_label, scope_cls = _SCOPE.get(job.get("remoteType"), (job.get("remoteType") or "Remote", ""))
    emp = _EMP.get(job.get("employmentCategory"), "")
    dept = _esc(job.get("department")) if job.get("department") else emp
    chips = [f'<span class="chip {scope_cls}"><span class="cdot"></span>{_esc(scope_label)}</span>']
    exp = job.get("experienceLevel")
    if exp and exp != "unspecified":
        chips.append(f'<span class="chip">{_esc(_EXP.get(exp, exp))}</span>')
    if job.get("salaryText"):
        chips.append(f'<span class="chip pay">{_esc(job["salaryText"])}</span>')
    chips.append(f'<span class="chip">&#8967; posted {_rel(hours)}</span>')
    chips.append(f'<span class="chip src">&#9670; {_esc(job.get("source"))}</span>')
    return (
        f'<article class="row" style="--fresh:{fresh:.3f}">'
        f'<div><div class="co"><b>{_esc(job.get("company"))}</b>'
        f'{f" &nbsp;/&nbsp; {dept}" if dept else ""}</div>'
        f'<h2 class="ttl">{_esc(job.get("title"))}</h2>'
        f'<div class="loc">{_esc(job.get("location"))}</div>'
        f'<div class="chips">{"".join(chips)}</div></div>'
        f'<div class="rail"><div class="bars">{bars}</div>'
        f'<div class="age">{_rel(hours)} ago</div>'
        f'<a class="apply" href="{_esc(job.get("url"))}" target="_blank" rel="noopener noreferrer">Apply direct &#8599;</a>'
        f'</div></article>'
    )


def _itemlist(jobs: list[dict[str, Any]], site_url: str) -> str:
    elements = [
        {
            "@type": "ListItem",
            "position": i,
            "url": job.get("url"),
            "name": f'{job.get("title", "")} — {job.get("company", "")}'.strip(" —"),
        }
        for i, job in enumerate(jobs, start=1)
        if job.get("url")
    ]
    payload = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Current remote job listings on RemoteCurrent",
        "url": f"{site_url}/",
        "numberOfItems": len(elements),
        "itemListElement": elements,
    }
    return '<script type="application/ld+json">' + json.dumps(payload, ensure_ascii=False) + "</script>"


def render_index(template: str, jobs: list[dict[str, Any]], site_url: str = SITE_URL, limit: int = PRERENDER_ROWS) -> str:
    now = datetime.now(timezone.utc)
    ordered = sorted(jobs, key=lambda job: job.get("postedAt") or job.get("firstSeenAt") or "", reverse=True)
    top = ordered[:limit]

    rows = "".join(_row_html(job, now) for job in top) or '<div class="empty">No listings right now.</div>'
    placeholder = re.compile(r'(<div class="rows" id="rows"[^>]*>).*?(</div>\s*<button class="more")', re.S)
    if not placeholder.search(template):
        raise ValueError("index template: could not find the #rows placeholder")
    out = placeholder.sub(lambda m: m.group(1) + rows + m.group(2), template, count=1)

    injected = (
        f'<meta property="og:updated_time" content="{now.replace(microsecond=0).isoformat()}">\n'
        + _itemlist(top, site_url) + "\n</head>"
    )
    return out.replace("</head>", injected, 1)


def prerender(root: Path, site_url: str = SITE_URL) -> None:
    site = root / "_site"
    jobs = json.loads((root / "data" / "jobs.json").read_text()).get("jobs", []) if (root / "data" / "jobs.json").exists() else []
    template = (root / "index.html").read_text()
    (site / "index.html").write_text(render_index(template, jobs, site_url), encoding="utf-8")
    write_sitemap(site, site_url)
    print(f"prerendered _site/index.html with {min(len(jobs), PRERENDER_ROWS)} listings; wrote _site/sitemap.xml")


if __name__ == "__main__":
    prerender(Path(__file__).resolve().parents[1])
