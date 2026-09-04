// Pure extraction logic -- no Workers-runtime APIs, so it is testable with
// plain Node and has no dependency on how it is called (see src/index.js).
//
// Ported from crawler/pipeline.py's schema.org JobPosting handling
// (_LDJSON / _iter_jobpostings / _ld_salary / plain_text) so a listing
// previewed here is read the same way the crawler itself would classify it.

const LDJSON_RE = /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;

const ENTITY = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export function decodeEntities(text) {
  return String(text).replace(/&(#\d+|#x[0-9a-f]+|[a-z]+);/gi, (whole, ent) => {
    if (ent[0] === "#") {
      const code = ent[1].toLowerCase() === "x" ? parseInt(ent.slice(2), 16) : parseInt(ent.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : whole;
    }
    return ENTITY[ent.toLowerCase()] ?? whole;
  });
}

export function plainText(html) {
  if (!html) return "";
  return decodeEntities(String(html).replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}

export function excerpt(text, maxLen) {
  if (!text) return null;
  if (text.length <= maxLen) return text;
  const cut = text.slice(0, maxLen);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > maxLen * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

function* iterJobPostings(node) {
  if (Array.isArray(node)) {
    for (const item of node) yield* iterJobPostings(item);
    return;
  }
  if (node && typeof node === "object") {
    const kinds = node["@type"];
    const list = Array.isArray(kinds) ? kinds : [kinds];
    if (list.includes("JobPosting")) yield node;
    for (const key of ["@graph", "itemListElement", "item", "mainEntity"]) {
      if (key in node) yield* iterJobPostings(node[key]);
    }
  }
}

/** Every distinct JobPosting found in any application/ld+json block on the page. */
export function extractJobPostings(html) {
  const postings = [];
  const seen = new Set();
  LDJSON_RE.lastIndex = 0;
  let match;
  while ((match = LDJSON_RE.exec(html))) {
    let data;
    try {
      data = JSON.parse(match[1].trim());
    } catch {
      continue;
    }
    for (const posting of iterJobPostings(data)) {
      const identifier = posting.identifier && typeof posting.identifier === "object" ? posting.identifier.value : posting.identifier;
      const key = String(identifier ?? posting.url ?? posting["@id"] ?? JSON.stringify(posting).slice(0, 120));
      if (seen.has(key)) continue;
      seen.add(key);
      postings.push(posting);
    }
  }
  return postings;
}

const CURRENCY_SYMBOL = { USD: "$", GBP: "£", EUR: "€" };

export function summarizeSalary(base) {
  if (!base || typeof base !== "object") return null;
  const currency = String(base.currency || base.currencyCode || "").toUpperCase();
  const symbol = CURRENCY_SYMBOL[currency];
  if (!symbol) return null;
  let value = base.value;
  if (value && typeof value === "object") {
    const { minValue, maxValue } = value;
    if (minValue && maxValue) {
      return `${symbol}${Math.round(minValue).toLocaleString("en-US")} - ${symbol}${Math.round(maxValue).toLocaleString("en-US")}`;
    }
    value = value.value;
  }
  return value ? `${symbol}${Math.round(value).toLocaleString("en-US")}` : null;
}

const PREVIEW_MAX_CHARS = 1200;

/** {title, company, preview, salary, sourceUrl, datePosted} from one JobPosting node. */
export function summarizePosting(posting, sourceUrl) {
  const description = plainText(posting.description);
  return {
    title: plainText(posting.title) || null,
    company: plainText(posting.hiringOrganization && posting.hiringOrganization.name) || null,
    preview: excerpt(description, PREVIEW_MAX_CHARS),
    salary: summarizeSalary(posting.baseSalary),
    datePosted: posting.datePosted || null,
    sourceUrl: posting.url || sourceUrl || null,
  };
}
