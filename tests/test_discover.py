import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crawler import discover


class DiscoverTests(unittest.TestCase):
    def test_slug_regexes_extract_tenant(self):
        cases = {
            "greenhouse": ("https://boards.greenhouse.io/stripe/jobs/12", "stripe"),
            "lever": ("https://jobs.lever.co/palantir/abc-def", "palantir"),
            "ashby": ("https://jobs.ashbyhq.com/openai?utm=1", "openai"),
        }
        for ats, (url, want) in cases.items():
            match = discover.ATS[ats]["slug_re"].search(url)
            self.assertIsNotNone(match, ats)
            self.assertEqual(match.group(1).lower(), want, ats)

    def test_greenhouse_embed_form_extracts_slug(self):
        match = discover.ATS["greenhouse"]["slug_re"].search("https://boards.greenhouse.io/embed/job_board?for=notion")
        self.assertEqual(match.group(1).lower(), "notion")

    def test_discover_skips_known_and_dead_slugs(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "companies.json"
            registry.write_text(json.dumps([{"name": "Stripe", "type": "greenhouse", "key": "stripe"}]))
            live = {"newco"}  # only this slug validates
            harvested = {
                "https://boards.greenhouse.io/stripe/jobs/1",   # already in registry
                "https://boards.greenhouse.io/newco/jobs/2",    # new + live
                "https://boards.greenhouse.io/ghostco/jobs/3",  # new + dead
            }
            with patch.object(discover, "REGISTRY", registry), \
                 patch.dict(discover.HARVESTERS, {"wayback": lambda host, limit: harvested}), \
                 patch.object(discover, "validate", side_effect=lambda ats, slug: {"name": slug, "type": ats, "key": slug} if slug in live else None):
                found = discover.discover("greenhouse", "wayback", limit=50, apply=True, sleep=0)
            self.assertEqual(found, 1)
            merged = json.loads(registry.read_text())
            self.assertEqual([e["key"] for e in merged], ["stripe", "newco"])


if __name__ == "__main__":
    unittest.main()
