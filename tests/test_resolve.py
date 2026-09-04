import unittest
from crawler.resolve import index_by_company, normalize_company, normalize_title, resolve

class ResolveTests(unittest.TestCase):
    def test_normalize_company_strips_suffix_and_punctuation(self): self.assertEqual(normalize_company("Acme, Inc."), "acme")
    def test_normalize_company_treats_llc_and_corp_the_same(self): self.assertEqual(normalize_company("Acme LLC"), normalize_company("Acme Corp."))
    def test_normalize_title_strips_remote_tag(self): self.assertEqual(normalize_title("Backend Engineer (Remote)"), "backend engineer")
    def test_normalize_title_case_and_space_insensitive(self): self.assertEqual(normalize_title("  Senior   Engineer "), "senior engineer")

    def test_matched_company_and_title_adds_provenance_not_a_new_row(self):
        canonical = [{"id": "c1", "company": "Acme Inc.", "title": "Senior Backend Engineer"}]
        discovered = [{"company": "Acme", "title": "Senior Backend Engineer (Remote)", "url": "https://weworkremotely.com/x", "region": "Anywhere", "publishedAt": "2026-09-01T00:00:00+00:00", "provider": "weworkremotely"}]
        standalone, unresolved = resolve(discovered, canonical)
        self.assertEqual((standalone, unresolved), ([], []))
        self.assertEqual(canonical[0]["discoveredVia"], [{"provider": "weworkremotely", "url": "https://weworkremotely.com/x", "firstSeenAt": "2026-09-01T00:00:00+00:00"}])

    def test_matching_is_idempotent_across_runs(self):
        canonical = [{"id": "c1", "company": "Acme", "title": "Engineer"}]
        item = {"company": "Acme", "title": "Engineer", "url": "https://weworkremotely.com/x", "region": "", "publishedAt": None, "provider": "weworkremotely"}
        resolve([item], canonical)
        resolve([item], canonical)
        self.assertEqual(len(canonical[0]["discoveredVia"]), 1)

    def test_known_company_unmatched_title_is_unresolved_not_a_new_row(self):
        canonical = [{"id": "c1", "company": "Acme", "title": "Support Specialist"}]
        discovered = [{"company": "Acme", "title": "Staff Machine Learning Engineer", "url": "https://weworkremotely.com/y", "region": "", "publishedAt": None, "provider": "weworkremotely"}]
        standalone, unresolved = resolve(discovered, canonical)
        self.assertEqual(len(standalone), 0)
        self.assertEqual(len(unresolved), 1)
        self.assertNotIn("discoveredVia", canonical[0])

    def test_unknown_company_becomes_a_standalone_noncanonical_row(self):
        discovered = [{"company": "Totally New Startup", "title": "Founding Engineer", "url": "https://weworkremotely.com/z", "region": "Anywhere in the World", "description": "This role is fully remote worldwide.", "publishedAt": "2026-09-01T00:00:00+00:00", "provider": "weworkremotely"}]
        standalone, unresolved = resolve(discovered, [])
        self.assertEqual(len(standalone), 1)
        job = standalone[0]
        self.assertEqual((job["canonical"], job["source"], job["discoveryProvider"], job["discoveryUrl"], job["company"]), (False, "weworkremotely", "weworkremotely", "https://weworkremotely.com/z", "Totally New Startup"))
        self.assertEqual(job["remoteType"], "worldwide")

    def test_standalone_row_drops_when_not_remote(self):
        discovered = [{"company": "New Co", "title": "Office Manager", "url": "https://weworkremotely.com/w", "region": "New York, NY", "description": "", "publishedAt": None, "provider": "weworkremotely"}]
        standalone, _ = resolve(discovered, [])
        self.assertEqual(standalone, [])

    def test_standalone_first_seen_persists_across_runs(self):
        item = {"company": "New Co", "title": "Founding Engineer", "url": "https://weworkremotely.com/p", "region": "Remote (Anywhere)", "description": "", "publishedAt": None, "provider": "weworkremotely"}
        first_run, _ = resolve([item], [])
        job_id = first_run[0]["id"]
        previous = [{"id": job_id, "firstSeenAt": "2026-01-01T00:00:00+00:00"}]
        second_run, _ = resolve([item], [], previous)
        self.assertEqual(second_run[0]["firstSeenAt"], "2026-01-01T00:00:00+00:00")

    def test_index_by_company_groups_by_normalized_name(self):
        jobs = [{"company": "Acme Inc."}, {"company": "acme"}, {"company": "Other Co"}]
        index = index_by_company(jobs)
        self.assertEqual(len(index[normalize_company("Acme")]), 2)

if __name__ == "__main__":
    unittest.main()
