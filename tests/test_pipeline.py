import unittest
from crawler.pipeline import classify_remote, parse_salary, plain_text

class PipelineTests(unittest.TestCase):
    def test_plain_text_decodes_markup(self): self.assertEqual(plain_text("&lt;p&gt;Hello &amp; goodbye&lt;/p&gt;"), "Hello & goodbye")
    def test_structured_remote_region(self): self.assertEqual(classify_remote("Europe", "", True, "Remote")["type"], "region_restricted")
    def test_remote_country(self): self.assertEqual(classify_remote("Remote, Italy", "")["type"], "country_restricted")
    def test_remote_global(self): self.assertEqual(classify_remote("Remote, Global", "")["type"], "worldwide")
    def test_location_region_beats_global_description(self): self.assertEqual(classify_remote("Remote, EMEA, Europe", "Join our global remote company", True, "Remote")["type"], "region_restricted")
    def test_location_country_beats_region_description(self): self.assertEqual(classify_remote("Remote India", "We work throughout APAC", True, "Remote")["type"], "country_restricted")
    def test_amer_is_a_region(self): self.assertEqual(classify_remote("Remote, AMER", "")["type"], "region_restricted")
    def test_us_city_is_country_restricted(self): self.assertEqual(classify_remote("Remote, San Francisco", "")["type"], "country_restricted")
    def test_named_country_beats_description_region(self): self.assertEqual(classify_remote("Remote Ireland", "Candidates across EMEA", True, "Remote")["type"], "country_restricted")
    def test_hybrid_is_not_remote(self): self.assertEqual(classify_remote("London (Hybrid)", "")["type"], "hybrid")
    def test_null_workplace_type(self): self.assertEqual(classify_remote("Remote, US", "", True, None)["type"], "country_restricted")
    def test_salary_range(self): self.assertEqual((parse_salary("Salary $120,000–$150,000")["min"], parse_salary("Salary $120,000–$150,000")["max"]), (120000, 150000))

if __name__ == "__main__": unittest.main()
