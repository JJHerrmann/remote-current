import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from crawler.feeds import write_feeds


def job(**overrides):
    base = {"id": "a1", "title": "Staff Engineer", "company": "Acme", "location": "Remote, US",
            "remoteType": "country_restricted", "source": "greenhouse", "url": "https://acme.example/1",
            "postedAt": "2026-09-01T00:00:00+00:00", "firstSeenAt": "2026-09-01T00:00:00+00:00", "salaryText": None}
    base.update(overrides)
    return base


class FeedTests(unittest.TestCase):
    def test_writes_core_feeds_and_matching_catalog(self):
        jobs = [
            job(id="a1"),
            job(id="a2", remoteType="worldwide", company="Globex", url="https://globex.example/2"),
            job(id="a3", salaryText="$100K - $120K", source="ashby", url="https://acme.example/3"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = write_feeds(root, jobs)
            paths = {entry["path"] for entry in catalog}
            for expected in ("feeds/all.xml", "feeds/worldwide.xml", "feeds/with-salary.xml",
                             "feeds/company-acme.xml", "feeds/company-globex.xml", "feeds/source-greenhouse.xml"):
                self.assertIn(expected, paths)

            channel = ET.parse(root / "feeds" / "all.xml").getroot().find("channel")
            items = channel.findall("item")
            self.assertEqual(len(items), 3)
            self.assertTrue(items[0].findtext("guid").startswith("remotecurrent:"))
            self.assertIn(",", items[0].findtext("pubDate"))  # RFC-822 weekday comma

            worldwide = ET.parse(root / "feeds" / "worldwide.xml").getroot().find("channel").findall("item")
            self.assertEqual(len(worldwide), 1)
            self.assertEqual(worldwide[0].findtext("title"), "Staff Engineer — Globex")

            index = json.loads((root / "feeds" / "index.json").read_text())
            self.assertEqual({entry["path"] for entry in index["feeds"]}, paths)

    def test_orders_newest_first_and_caps_items(self):
        jobs = [job(id=f"j{i}", postedAt=f"2026-07-{(i % 27) + 1:02d}T00:00:00+00:00") for i in range(150)]
        jobs.append(job(id="newest", postedAt="2026-09-02T12:00:00+00:00"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_feeds(root, jobs)
            items = ET.parse(root / "feeds" / "all.xml").getroot().find("channel").findall("item")
            self.assertLessEqual(len(items), 100)
            self.assertEqual(items[0].findtext("guid"), "remotecurrent:newest")

    def test_skips_empty_feeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = write_feeds(root, [job(id="a1")])  # no worldwide, no salary
            paths = {entry["path"] for entry in catalog}
            self.assertNotIn("feeds/worldwide.xml", paths)
            self.assertNotIn("feeds/with-salary.xml", paths)
            self.assertFalse((root / "feeds" / "worldwide.xml").exists())


if __name__ == "__main__":
    unittest.main()
