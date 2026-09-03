import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from crawler.seo import render_index, write_sitemap

TEMPLATE = (
    "<!doctype html><html><head><title>RemoteCurrent</title></head><body>"
    '<main><div class="rows" id="rows" aria-live="polite">'
    '<div class="empty">Fetching the current feed&hellip;</div></div>'
    '<button class="more" id="more" hidden>Show more</button></main>'
    "</body></html>"
)


def job(**kw):
    base = {
        "id": "a1", "company": "Acme", "title": "Staff Engineer", "location": "Remote, US",
        "remoteType": "country_restricted", "source": "greenhouse", "url": "https://acme.example/1",
        "experienceLevel": "lead", "employmentCategory": "full_time", "salaryText": "$150K - $190K",
        "postedAt": datetime.now(timezone.utc).isoformat(), "department": "Platform",
    }
    base.update(kw)
    return base


class SeoTests(unittest.TestCase):
    def test_sitemap_lists_pages_and_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_sitemap(root, "https://example.test")
            tree = ET.parse(root / "sitemap.xml")
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            locs = [el.text for el in tree.findall(".//s:loc", ns)]
        self.assertEqual(locs, ["https://example.test/", "https://example.test/story.html", "https://example.test/about.html", "https://example.test/sources.html"])

    def test_render_index_bakes_rows_and_itemlist(self):
        base = datetime(2026, 2, 1, tzinfo=timezone.utc)
        jobs = [
            job(id=f"j{i}", url=f"https://acme.example/{i}", title=f"Role {i}",
                postedAt=base.replace(minute=i).isoformat())
            for i in range(60)
        ]
        out = render_index(TEMPLATE, jobs, "https://example.test", limit=40)

        self.assertEqual(len(re.findall(r'<article class="row"', out)), 40)
        self.assertNotIn("Fetching the current feed", out)          # placeholder replaced
        self.assertIn('<button class="more"', out)                  # sibling preserved
        self.assertIn('href="https://acme.example/59"', out)        # newest job's apply link is baked in
        self.assertRegex(out, r'<h2 class="ttl">Role 59</h2>')

        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', out, re.S)
        data = next(json.loads(b) for b in blocks if '"ItemList"' in b)
        self.assertEqual(data["@type"], "ItemList")
        self.assertEqual(data["numberOfItems"], 40)
        self.assertEqual(data["itemListElement"][0], {"@type": "ListItem", "position": 1,
                                                      "url": "https://acme.example/59", "name": "Role 59 — Acme"})
        self.assertIn('<meta property="og:updated_time"', out)

    def test_render_index_requires_placeholder(self):
        with self.assertRaises(ValueError):
            render_index("<html><head></head><body>no rows here</body></html>", [job()])


if __name__ == "__main__":
    unittest.main()
