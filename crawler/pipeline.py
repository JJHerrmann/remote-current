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


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


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


def normalize(company: dict[str, str], source_id: Any, title: str, location: str, description: str, url: str, posted_at: str | None, department: str | None, employment_type: str | None, structured_remote: bool, workplace_type: str) -> dict[str, Any]:
    remote, salary = classify_remote(location, description, structured_remote, workplace_type), parse_salary(description)
    stable = f"{company['type']}:{company['key']}:{source_id}"
    return {"id": hashlib.sha256(stable.encode()).hexdigest()[:20], "sourceId": str(source_id), "source": company["type"], "company": company["name"], "title": re.sub(r"\s+", " ", title).strip(), "location": re.sub(r"\s+", " ", location).strip() or "Not specified", "department": department, "employmentType": employment_type, "description": description[:5000], "url": url, "postedAt": posted_at, "remoteType": remote["type"], "remoteConfidence": remote["confidence"], "remoteEvidence": remote["evidence"], "salaryMin": salary["min"], "salaryMax": salary["max"], "salaryCurrency": salary["currency"], "salaryText": salary["text"]}


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


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def collect(companies: list[dict[str, str]], previous: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    now, old, gathered, errors = datetime.now(timezone.utc).replace(microsecond=0).isoformat(), {job["id"]: job for job in (previous or [])}, [], []
    with ThreadPoolExecutor(max_workers=min(6, len(companies))) as pool:
        futures = {pool.submit(ADAPTERS[c["type"]], c): c for c in companies}
        for future in as_completed(futures):
            company = futures[future]
            try:
                gathered.extend(future.result())
            except Exception as exc:
                errors.append({"company": company["name"], "error": str(exc)})
    visible = []
    for job in gathered:
        if job["remoteType"] in {"not_remote", "hybrid"}:
            continue
        job["firstSeenAt"] = old.get(job["id"], {}).get("firstSeenAt", now)
        job["lastSeenAt"] = now
        visible.append(job)
    visible.sort(key=lambda job: job.get("postedAt") or job["firstSeenAt"], reverse=True)
    return visible, errors


def write_dataset(root: Path, jobs: list[dict[str, Any]], errors: list[dict[str, str]]) -> None:
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    document = {"generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "jobCount": len(jobs), "companyCount": len({job["company"] for job in jobs}), "sourceErrors": errors, "jobs": jobs}
    (data_dir / "jobs.json").write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
