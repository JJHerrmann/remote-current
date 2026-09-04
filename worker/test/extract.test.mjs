import { test } from "node:test";
import assert from "node:assert/strict";
import { decodeEntities, excerpt, extractJobPostings, plainText, summarizePosting, summarizeSalary } from "../src/extract.js";

test("plainText strips tags and decodes entities", () => {
  assert.equal(plainText("<p>Hello &amp; goodbye</p>"), "Hello & goodbye");
});

test("decodeEntities handles numeric and named entities", () => {
  assert.equal(decodeEntities("Caf&#233; &mdash; &amp;"), "Café &mdash; &");
});

test("excerpt returns short text unchanged", () => {
  assert.equal(excerpt("short", 1200), "short");
});

test("excerpt truncates at a word boundary with an ellipsis", () => {
  const text = "word ".repeat(400).trim();
  const result = excerpt(text, 100);
  assert.ok(result.length <= 101);
  assert.ok(result.endsWith("…"));
  assert.ok(!result.slice(0, -1).endsWith(" "));
});

test("extractJobPostings finds a single JobPosting block", () => {
  const html = `<html><head><script type="application/ld+json">{"@type":"JobPosting","title":"Backend Engineer","identifier":"J-42","url":"https://acme.example/jobs/42","description":"<p>Fully remote.</p>"}</script></head></html>`;
  const postings = extractJobPostings(html);
  assert.equal(postings.length, 1);
  assert.equal(postings[0].title, "Backend Engineer");
});

test("extractJobPostings walks an ItemList and de-dupes by identifier", () => {
  const html = `<script type="application/ld+json">{"@type":"ItemList","itemListElement":[
    {"@type":"ListItem","item":{"@type":"JobPosting","title":"A","identifier":"1"}},
    {"@type":"ListItem","item":{"@type":"JobPosting","title":"A dup","identifier":"1"}},
    {"@type":"ListItem","item":{"@type":"JobPosting","title":"B","identifier":"2"}}
  ]}</script>`;
  const postings = extractJobPostings(html);
  assert.deepEqual(postings.map((p) => p.title), ["A", "B"]);
});

test("extractJobPostings ignores non-JobPosting ld+json and malformed blocks", () => {
  const html = `<script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script><script type="application/ld+json">not json</script>`;
  assert.deepEqual(extractJobPostings(html), []);
});

test("summarizeSalary formats a min/max range", () => {
  assert.equal(summarizeSalary({ currency: "USD", value: { minValue: 150000, maxValue: 190000 } }), "$150,000 - $190,000");
});

test("summarizeSalary formats a single value", () => {
  assert.equal(summarizeSalary({ currency: "GBP", value: 65000 }), "£65,000");
});

test("summarizeSalary returns null for an unknown currency", () => {
  assert.equal(summarizeSalary({ currency: "JPY", value: 9000000 }), null);
});

test("summarizePosting builds the preview contract", () => {
  const posting = {
    title: "Backend Engineer",
    hiringOrganization: { name: "Acme" },
    description: "<p>Build the payments platform. " + "Real work. ".repeat(300) + "</p>",
    baseSalary: { currency: "USD", value: { minValue: 150000, maxValue: 190000 } },
    datePosted: "2026-02-01",
    url: "https://acme.example/jobs/42",
  };
  const summary = summarizePosting(posting, "https://acme.example/careers/42");
  assert.equal(summary.title, "Backend Engineer");
  assert.equal(summary.company, "Acme");
  assert.equal(summary.salary, "$150,000 - $190,000");
  assert.equal(summary.sourceUrl, "https://acme.example/jobs/42");
  assert.ok(summary.preview.length <= 1201);
  assert.ok(summary.preview.startsWith("Build the payments platform."));
});

test("summarizePosting falls back to the fetched URL when the posting has none", () => {
  const summary = summarizePosting({ title: "X" }, "https://acme.example/careers/42");
  assert.equal(summary.sourceUrl, "https://acme.example/careers/42");
  assert.equal(summary.preview, null);
});
