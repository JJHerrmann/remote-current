from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

USER_AGENT = "RemoteCurrent/0.1 (+https://github.com/JJHerrmann/remote-current)"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def plain_text(value: str | None) -> str:
    parser = _TextExtractor()
    parser.feed(html.unescape(value or ""))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def fetch_json(url: str, data: dict | None = None) -> Any:
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")


def iso_from_epoch_ms(value: int | None) -> str | None:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat() if value else None


def classify_remote(location: str, description: str, structured_remote: bool = False, workplace_type: str = "") -> dict[str, Any]:
    location_clean = re.sub(r"\s+", " ", location).strip()
    loc = location_clean.casefold()
    workplace = (workplace_type or "").casefold()
    excerpt = (description or "")[:6000].casefold()
    if workplace == "hybrid" or re.search(r"\bhybrid\b", loc):
        return {"type": "hybrid", "confidence": 0.99, "evidence": location_clean}
    remote_signal = structured_remote or workplace == "remote" or bool(re.search(r"\b(remote|home[ -]based|work from home)\b", loc))
    if not remote_signal:
        remote_signal = bool(re.search(r"\b(this (?:position|role) is (?:fully )?remote|work remotely from|fully remote role)\b", excerpt))
    if not remote_signal:
        return {"type": "not_remote", "confidence": 0.96, "evidence": location_clean}
    evidence = location_clean or ("ATS marks this role remote" if structured_remote else "Job description marks this role remote")
    worldwide = r"\b(worldwide|global|work from anywhere|anywhere in the world)\b"
    region = r"\b(emea|europe|european union|eu|apac|asia[- ]pacific|latam|latin america|north america|americas|amer)\b"
    country = r"\b(united states|u\.?s\.?a?\.?|canada|united kingdom|u\.?k\.?|australia|austria|belgium|brazil|bulgaria|canada|croatia|cyprus|czechia|czech republic|denmark|estonia|finland|france|germany|greece|hungary|india|indonesia|ireland|israel|italy|japan|latvia|lithuania|luxembourg|malaysia|malta|mexico|netherlands|new zealand|norway|philippines|poland|portugal|romania|singapore|slovakia|slovenia|south africa|south korea|spain|sweden|switzerland|taiwan|thailand|turkey|united arab emirates|vietnam)\b"
    us_place = r"\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|san francisco|bay area)\b"

    # The location field is authoritative. Descriptions often contain generic
    # phrases such as "global company" which must not broaden an EMEA/US role.
    if re.search(worldwide, loc):
        scope = "worldwide"
    elif re.search(region, loc):
        scope = "region_restricted"
    elif re.search(country, loc) or re.search(us_place, loc):
        scope = "country_restricted"
    elif re.fullmatch(r"(?:remote|home[ -]based|work from home)(?:\s*[-,(].*)?", loc) and re.search(r"\b(ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy)\b", loc):
        scope = "country_restricted"
    elif re.search(r"\b(worldwide remote|remote worldwide|work from anywhere|anywhere in the world)\b", excerpt[:1800]):
        scope = "worldwide"
    elif re.search(region, excerpt[:1800]):
        scope = "region_restricted"
    elif re.search(country, excerpt[:1800]):
        scope = "country_restricted"
    else:
        scope = "remote_unspecified"
    return {"type": scope, "confidence": 0.93 if structured_remote else 0.82, "evidence": evidence}


def parse_salary(text: str) -> dict[str, Any]:
    match = re.search(r"(?P<currency>[$£€])\s*(?P<low>\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?[kK])\s*(?:-|–|—|to)\s*(?:[$£€]\s*)?(?P<high>\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?[kK])", text)
    if not match:
        return {"min": None, "max": None, "currency": None, "text": None}

    def amount(raw: str) -> int:
        return int(float(raw.rstrip("kK").replace(",", "")) * (1000 if raw.lower().endswith("k") else 1))

    return {"min": amount(match["low"]), "max": amount(match["high"]), "currency": {"$": "USD", "£": "GBP", "€": "EUR"}[match["currency"]], "text": match.group(0)}


def classify_experience(title: str, structured: str | None = None) -> str:
    known = (structured or "").casefold().replace("-", "_").replace(" ", "_")
    structured_map = {"internship": "internship", "entry_level": "entry", "associate": "entry", "mid_senior_level": "mid", "mid_level": "mid", "director": "director", "executive": "executive"}
    if known in structured_map:
        return structured_map[known]
    value = title.casefold()
    rules = [
        ("internship", r"\b(intern|internship|apprentice)\b"),
        ("entry", r"\b(junior|entry[- ]level|new grad|graduate)\b"),
        ("executive", r"\b(chief .+ officer|vice president|[se]?vp)\b"),
        ("director", r"\b(director|head of)\b"),
        ("manager", r"\bmanager\b"),
        ("lead", r"\b(principal|staff|lead)\b"),
        ("senior", r"\b(senior|sr\.?)\b"),
        ("mid", r"\b(mid[- ]level|intermediate)\b"),
    ]
    return next((level for level, pattern in rules if re.search(pattern, value)), "unspecified")


def classify_employment(value: str | None) -> str:
    text = (value or "").casefold()
    if "intern" in text:
        return "internship"
    if "part" in text:
        return "part_time"
    if any(word in text for word in ("contract", "freelance", "temporary")):
        return "contract"
    if "full" in text or "permanent" in text:
        return "full_time"
    return "unspecified"


def normalize(company: dict[str, str], source_id: Any, title: str, location: str, description: str, url: str, posted_at: str | None, department: str | None, employment_type: str | None, structured_remote: bool, workplace_type: str, structured_experience: str | None = None) -> dict[str, Any]:
    remote, salary = classify_remote(location, description, structured_remote, workplace_type), parse_salary(description)
    stable = f"{company['type']}:{company['key']}:{source_id}"
    return {"id": hashlib.sha256(stable.encode()).hexdigest()[:20], "sourceId": str(source_id), "source": company["type"], "company": company["name"], "title": re.sub(r"\s+", " ", title).strip(), "location": re.sub(r"\s+", " ", location).strip() or "Not specified", "department": department, "employmentType": employment_type, "employmentCategory": classify_employment(employment_type), "experienceLevel": classify_experience(title, structured_experience), "experienceInferred": not bool(structured_experience), "url": url, "postedAt": posted_at, "remoteType": remote["type"], "remoteConfidence": remote["confidence"], "remoteEvidence": remote["evidence"], "salaryMin": salary["min"], "salaryMax": salary["max"], "salaryCurrency": salary["currency"], "salaryText": salary["text"], "canonical": True, "discoveryProvider": company["type"], "discoveryUrl": url}


def greenhouse(company: dict[str, str]) -> list[dict[str, Any]]:
    payload = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{company['key']}/jobs?content=true")
    return [normalize(company, item["id"], item.get("title", ""), item.get("location", {}).get("name", ""), plain_text(item.get("content")), item.get("absolute_url", ""), item.get("updated_at"), (item.get("departments") or [{}])[0].get("name"), None, False, "") for item in payload.get("jobs", [])]


def lever(company: dict[str, str]) -> list[dict[str, Any]]:
    payload = fetch_json(f"https://api.lever.co/v0/postings/{company['key']}?mode=json")
    jobs = []
    for item in payload:
        categories = item.get("categories") or {}
        location = ", ".join(categories.get("allLocations") or [categories.get("location", "")])
        lists = " ".join(plain_text(block.get("content")) for block in item.get("lists", []))
        description = " ".join(filter(None, [item.get("descriptionPlain", ""), lists, item.get("additionalPlain", "")]))
        jobs.append(normalize(company, item["id"], item.get("text", ""), location, description, item.get("hostedUrl") or item.get("applyUrl", ""), iso_from_epoch_ms(item.get("createdAt")), categories.get("department"), categories.get("commitment"), False, ""))
    return jobs


def ashby(company: dict[str, str]) -> list[dict[str, Any]]:
    payload = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{company['key']}?includeCompensation=true")
    jobs = []
    for item in payload.get("jobs", []):
        location = ", ".join(filter(None, [item.get("location", ""), *[entry.get("location", "") for entry in item.get("secondaryLocations", [])]]))
        compensation = item.get("compensation") or {}
        compensation_text = compensation.get("scrapeableCompensationSalarySummary") or compensation.get("compensationTierSummary") or ""
        description = plain_text(item.get("descriptionPlain") or item.get("descriptionHtml"))
        jobs.append(normalize(company, item["id"], item.get("title", ""), location, f"{compensation_text} {description}".strip(), item.get("jobUrl") or item.get("applyUrl", ""), item.get("publishedAt"), item.get("department") or item.get("team"), item.get("employmentType"), bool(item.get("isRemote")), item.get("workplaceType", "")))
    return jobs


def recruitee(company: dict[str, str]) -> list[dict[str, Any]]:
    payload = fetch_json(f"https://{company['key']}.recruitee.com/api/offers/")
    jobs = []
    for item in payload.get("offers", []):
        remote = bool(item.get("remote"))
        country = (item.get("country_code") or "").upper()
        location = f"Remote, {country}" if remote and country else item.get("location", "")
        published = (item.get("published_at") or item.get("created_at") or "").replace(" UTC", "+00:00") or None
        jobs.append(normalize(company, item.get("slug"), item.get("title", ""), location, "", item.get("careers_url") or item.get("careers_apply_url", ""), published, item.get("category_code"), item.get("employment_type_code"), remote, "remote" if remote else ""))
    return jobs


def smartrecruiters(company: dict[str, str]) -> list[dict[str, Any]]:
    items, offset, limit = [], 0, 100
    while True:
        payload = fetch_json(f"https://api.smartrecruiters.com/v1/companies/{company['key']}/postings?limit={limit}&offset={offset}")
        batch = payload.get("content", [])
        items.extend(batch)
        offset += len(batch)
        if not batch or offset >= payload.get("totalFound", 0):
            break
    jobs = []
    for item in items:
        location = item.get("location") or {}
        remote, hybrid = bool(location.get("remote")), bool(location.get("hybrid"))
        jobs.append(normalize(company, item.get("id"), item.get("name", ""), location.get("fullLocation", ""), "", f"https://jobs.smartrecruiters.com/{company['key']}/{item.get('id')}", item.get("releasedDate"), (item.get("department") or {}).get("label"), (item.get("typeOfEmployment") or {}).get("label"), remote, "hybrid" if hybrid else ("remote" if remote else ""), (item.get("experienceLevel") or {}).get("id")))
    return jobs


WORKDAY_LIST_CAP = 400   # postings scanned per tenant before paging stops
WORKDAY_DETAIL_CAP = 120  # detail requests per tenant per crawl


def _workday_detail(company: dict[str, str], base: str, posting: dict[str, Any]) -> dict[str, Any] | None:
    try:
        info = fetch_json(f"{base}{posting['externalPath']}").get("jobPostingInfo") or {}
    except Exception:
        return None
    if not info:
        return None
    location = " / ".join(filter(None, [info.get("location", ""), *info.get("additionalLocations", [])]))
    start = info.get("startDate")
    source_id = info.get("jobReqId") or info.get("jobPostingId") or (posting.get("bulletFields") or [posting.get("externalPath")])[0]
    return normalize(company, source_id, info.get("title") or posting.get("title", ""), location, plain_text(info.get("jobDescription")), info.get("externalUrl", ""), f"{start}T00:00:00+00:00" if start else None, None, info.get("timeType"), False, "")


def workday(company: dict[str, str]) -> list[dict[str, Any]]:
    # Workday CxS: a POST search endpoint plus one detail GET per posting. The
    # list rows carry no description or real date, so classification needs the
    # detail call; searchText="remote" and the caps keep an hourly crawl bounded.
    base = f"https://{company['host']}/wday/cxs/{company['tenant']}/{company['site']}"
    postings, offset = [], 0
    while offset < WORKDAY_LIST_CAP:
        payload = fetch_json(f"{base}/jobs", {"limit": 20, "offset": offset, "searchText": "remote", "appliedFacets": {}})
        batch = payload.get("jobPostings", [])
        postings.extend(batch)
        offset += len(batch)
        if not batch or offset >= payload.get("total", 0):
            break
    hinted = [p for p in postings if re.search(r"remote", f"{p.get('title', '')} {p.get('locationsText', '')} {p.get('externalPath', '')}", re.I)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        detailed = list(pool.map(lambda p: _workday_detail(company, base, p), hinted[:WORKDAY_DETAIL_CAP]))
    return [job for job in detailed if job]


PHENOM_PAGE_CAP = 20


def phenom(company: dict[str, str]) -> list[dict[str, Any]]:
    # Phenom career sites (PepsiCo and many large employers) expose a paged JSON
    # feed with the description inline. There is no structured remote flag, so
    # keywords=remote narrows a mostly-onsite feed and classify_remote decides
    # from the location and description text.
    rows, page = [], 1
    while page <= PHENOM_PAGE_CAP:
        payload = fetch_json(f"https://{company['host']}/api/jobs?page={page}&limit=100&keywords=remote")
        batch = payload.get("jobs", [])
        rows.extend(item.get("data") or item for item in batch)
        page += 1
        if not batch or len(rows) >= payload.get("totalCount", 0):
            break
    jobs = []
    for data in rows:
        category = (data.get("category") or [None])[0]
        posted = (data.get("posted_date") or data.get("create_date") or "").replace("+0000", "+00:00") or None
        jobs.append(normalize(company, data.get("req_id"), data.get("title", ""), data.get("full_location") or data.get("location_name", ""), data.get("description") or "", data.get("apply_url", ""), posted, category.strip() if isinstance(category, str) else None, None, False, ""))
    return jobs


MICROSOFT_CAP = 200


def microsoft(company: dict[str, str]) -> list[dict[str, Any]]:
    # RETIRED: gcsservices.careers.microsoft.com now serves a mismatched cert and
    # 404s; Microsoft migrated to apply.careers.microsoft.com. The registry entry
    # is disabled. Kept as a starting point for whoever maps the new API onto
    # this same normalized shape.
    base = "https://gcsservices.careers.microsoft.com/search/api/v1"
    results, page = [], 1
    while len(results) < MICROSOFT_CAP:
        result = (fetch_json(f"{base}/search?q=&l=en_us&pg={page}&pgSz=20&o=Recent&flt=true").get("operationResult") or {}).get("result") or {}
        batch = result.get("jobs", [])
        results.extend(batch)
        page += 1
        if not batch or len(results) >= result.get("totalJobs", 0):
            break
    jobs = []
    for item in results:
        props = item.get("properties") or {}
        locations = props.get("locations") or ([props["location"]] if props.get("location") else [])
        flex = (props.get("workSiteFlexibility") or "").casefold()
        job_id = item.get("jobId") or item.get("id")
        jobs.append(normalize(company, job_id, item.get("title", ""), props.get("primaryLocation") or ", ".join(locations), "", f"https://jobs.careers.microsoft.com/global/en/job/{job_id}", item.get("postingDate") or props.get("postingDate"), props.get("profession") or props.get("discipline"), props.get("employmentType"), "100%" in flex or "work from home" in flex, ""))
    return jobs


_LDJSON = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)


def _iter_jobpostings(node: Any):
    if isinstance(node, list):
        for item in node:
            yield from _iter_jobpostings(item)
    elif isinstance(node, dict):
        kinds = node.get("@type")
        if "JobPosting" in (kinds if isinstance(kinds, list) else [kinds]):
            yield node
        for key in ("@graph", "itemListElement", "item", "mainEntity"):
            if key in node:
                yield from _iter_jobpostings(node[key])


def _ld_location(posting: dict[str, Any]) -> tuple[str, bool]:
    remote = str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE" or bool(posting.get("applicantLocationRequirements"))
    names: list[str] = []
    reqs = posting.get("applicantLocationRequirements")
    for req in (reqs if isinstance(reqs, list) else [reqs] if reqs else []):
        if isinstance(req, dict) and req.get("name"):
            names.append(str(req["name"]))
    locs = posting.get("jobLocation")
    for loc in (locs if isinstance(locs, list) else [locs] if locs else []):
        addr = loc.get("address") if isinstance(loc, dict) else loc
        if isinstance(addr, dict):
            names.append(", ".join(str(addr[k]) for k in ("addressLocality", "addressRegion", "addressCountry") if isinstance(addr.get(k), str)))
        elif isinstance(addr, str):
            names.append(addr)
    location = "; ".join(name for name in names if name)
    if remote and "remote" not in location.lower():
        location = f"Remote{f' — {location}' if location else ''}"
    return location, remote


_CURRENCY_SYMBOL = {"USD": "$", "GBP": "£", "EUR": "€"}


def _ld_salary(posting: dict[str, Any]) -> str:
    base = posting.get("baseSalary")
    if not isinstance(base, dict):
        return ""
    symbol = _CURRENCY_SYMBOL.get(str(base.get("currency") or base.get("currencyCode") or "").upper())
    if not symbol:
        return ""
    value = base.get("value")
    try:
        if isinstance(value, dict):
            low, high = value.get("minValue"), value.get("maxValue")
            if low and high:
                return f"{symbol}{int(float(low)):,} - {symbol}{int(float(high)):,}"
            value = value.get("value")
        return f"{symbol}{int(float(value)):,}" if value else ""
    except (TypeError, ValueError):
        return ""


def jsonld(company: dict[str, str]) -> list[dict[str, Any]]:
    # Standards-based fallback for careers pages on no known ATS: parse any
    # server-rendered schema.org JobPosting blocks. Single-page apps that inject
    # JSON-LD client-side yield nothing here; those need the sitemap path.
    document = fetch_text(company["url"])
    seen: set[str] = set()
    jobs = []
    for block in _LDJSON.findall(document):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for posting in _iter_jobpostings(data):
            url = posting.get("url") or posting.get("@id") or company["url"]
            identifier = posting.get("identifier")
            if isinstance(identifier, dict):
                identifier = identifier.get("value")
            source_id = str(identifier or url)
            if source_id in seen:
                continue
            seen.add(source_id)
            location, remote = _ld_location(posting)
            description = f"{_ld_salary(posting)} {plain_text(posting.get('description'))}".strip()
            jobs.append(normalize(company, source_id, posting.get("title", ""), location, description, url, posting.get("datePosted"), None, posting.get("employmentType"), remote, ""))
    return jobs


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "recruitee": recruitee, "smartrecruiters": smartrecruiters, "workday": workday, "phenom": phenom, "microsoft": microsoft, "jsonld": jsonld}


DROPPED_SCOPES = {"not_remote", "hybrid"}


def apply_overrides(jobs: list[dict[str, Any]], overrides: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Manual corrections keyed by job id. `drop` removes a misclassified listing;
    `set_scope` pins its remote scope. Each surviving change is recorded on the job."""
    index = {entry["id"]: entry for entry in (overrides or []) if entry.get("id")}
    kept = []
    for job in jobs:
        entry = index.get(job["id"])
        if not entry:
            kept.append(job)
            continue
        action = entry.get("action")
        if action in {"drop", "not_remote"}:
            continue
        if action == "set_scope" and entry.get("value"):
            job["remoteType"] = entry["value"]
            job["remoteConfidence"] = 1.0
            job["remoteEvidence"] = f"Manual correction: {entry.get('reason', '').rstrip('.')}".strip().rstrip(":")
        job["correction"] = {"reason": entry.get("reason", ""), "addedAt": entry.get("addedAt", "")}
        kept.append(job)
    return kept


def collect(companies: list[dict[str, str]], previous: list[dict[str, Any]] | None = None, overrides: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    old = {job["id"]: job for job in (previous or [])}
    gathered, errors, reports = [], [], []
    with ThreadPoolExecutor(max_workers=min(6, len(companies))) as pool:
        futures = {pool.submit(ADAPTERS[c["type"]], c): c for c in companies}
        for future in as_completed(futures):
            company = futures[future]
            report = {"name": company["name"], "type": company["type"], "ok": True, "error": None, "fetched": 0, "visible": 0, "avgConfidence": None, "scopes": {}}
            try:
                rows = future.result()
                keep = [job for job in rows if job["remoteType"] not in DROPPED_SCOPES]
                report["fetched"], report["visible"] = len(rows), len(keep)
                if keep:
                    report["avgConfidence"] = round(sum(job["remoteConfidence"] for job in keep) / len(keep), 3)
                    for job in keep:
                        report["scopes"][job["remoteType"]] = report["scopes"].get(job["remoteType"], 0) + 1
                gathered.extend(rows)
            except Exception as exc:
                report["ok"], report["error"] = False, str(exc)
                errors.append({"company": company["name"], "error": str(exc)})
            reports.append(report)
    visible = []
    for job in apply_overrides(gathered, overrides):
        if job["remoteType"] in DROPPED_SCOPES:
            continue
        job["firstSeenAt"] = old.get(job["id"], {}).get("firstSeenAt", now)
        job["lastSeenAt"] = now
        visible.append(job)
    visible.sort(key=lambda job: job.get("postedAt") or job["firstSeenAt"], reverse=True)
    reports.sort(key=lambda report: (report["ok"], -report["visible"], report["name"].casefold()))
    return visible, errors, reports


def write_dataset(root: Path, jobs: list[dict[str, Any]], errors: list[dict[str, str]]) -> None:
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    document = {"generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "jobCount": len(jobs), "companyCount": len({job["company"] for job in jobs}), "sourceErrors": errors, "jobs": jobs}
    (data_dir / "jobs.json").write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_sources(root: Path, reports: list[dict[str, Any]], previous: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    last_ok = {entry["name"]: entry.get("lastOkAt") for entry in (previous or [])}
    for report in reports:
        report["lastOkAt"] = generated_at if report["ok"] else last_ok.get(report["name"])
    document = {"generatedAt": generated_at, "sourceCount": len(reports), "okCount": sum(1 for r in reports if r["ok"]), "errorCount": sum(1 for r in reports if not r["ok"]), "jobCount": sum(r["visible"] for r in reports), "sources": reports}
    (data_dir / "sources.json").write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return document
