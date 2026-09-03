import unittest
from unittest.mock import MagicMock, patch
from crawler.pipeline import apply_overrides, classify_employment, classify_experience, classify_remote, collect, jsonld, microsoft, parse_salary, phenom, plain_text, recruitee, smartrecruiters, workday

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
    def test_executive_assistant_is_not_executive_level(self): self.assertEqual(classify_experience("Executive Assistant to the CEO"), "unspecified")
    def test_seniority_prefers_manager_over_senior(self): self.assertEqual(classify_experience("Senior Engineering Manager"), "manager")
    def test_management_is_not_manager_level(self): self.assertEqual(classify_experience("Product Management Specialist"), "unspecified")
    def test_structured_experience_wins(self): self.assertEqual(classify_experience("Engineer", "entry_level"), "entry")
    def test_employment_category(self): self.assertEqual(classify_employment("Full-time permanent"), "full_time")
    @patch("crawler.pipeline.fetch_json")
    def test_recruitee_remote_country(self, fetch):
        fetch.return_value={"offers":[{"slug":"writer","title":"Writer","location":"Remote job","country_code":"US","remote":True,"careers_url":"https://example.com/writer"}]}
        self.assertEqual(recruitee({"name":"Example","type":"recruitee","key":"example"})[0]["remoteType"], "country_restricted")
    @patch("crawler.pipeline.fetch_json")
    def test_smartrecruiters_structured_remote(self, fetch):
        fetch.return_value={"content":[{"id":"1","name":"Engineer","releasedDate":"2026-01-01T00:00:00Z","location":{"fullLocation":"Germany, REMOTE","remote":True,"hybrid":False}}],"totalFound":1}
        self.assertEqual(smartrecruiters({"name":"Example","type":"smartrecruiters","key":"Example"})[0]["remoteType"], "country_restricted")
    @patch("crawler.pipeline.fetch_json")
    def test_workday_uses_detail_for_classification(self, fetch):
        fetch.side_effect=[
            {"total":1,"jobPostings":[{"title":"Staff Engineer","externalPath":"/job/US--REMOTE/Staff-Engineer_R1","locationsText":"US - Remote","bulletFields":["R1"]}]},
            {"jobPostingInfo":{"title":"Staff Engineer","jobDescription":"<p>This position is fully remote within the United States.</p>","location":"US - Remote","additionalLocations":[],"startDate":"2026-01-02","timeType":"Full time","jobReqId":"R1","externalUrl":"https://coke.wd1.myworkdayjobs.com/job/R1"}}]
        job=workday({"name":"Coca-Cola","type":"workday","key":"coke","host":"coke.wd1.myworkdayjobs.com","tenant":"coke","site":"coca-cola-careers"})[0]
        self.assertEqual((job["source"],job["remoteType"],job["postedAt"]),("workday","country_restricted","2026-01-02T00:00:00+00:00"))
    @patch("crawler.pipeline.fetch_json")
    def test_workday_skips_postings_without_remote_hint(self, fetch):
        fetch.return_value={"total":1,"jobPostings":[{"title":"Line Cook","externalPath":"/job/Chicago/Line-Cook_R2","locationsText":"Chicago, IL","bulletFields":["R2"]}]}
        self.assertEqual(workday({"name":"Coca-Cola","type":"workday","key":"coke","host":"h","tenant":"coke","site":"s"}), [])
    @patch("crawler.pipeline.fetch_json")
    def test_phenom_classifies_from_text(self, fetch):
        fetch.return_value={"totalCount":1,"jobs":[{"data":{"req_id":"P1","title":"Data Analyst","full_location":"Remote, United States","description":"This role is fully remote.","posted_date":"2026-01-01T00:00:00+0000","apply_url":"https://www.pepsicojobs.com/job/P1","category":[" Analytics "]}}]}
        job=phenom({"name":"PepsiCo","type":"phenom","key":"pepsico","host":"www.pepsicojobs.com"})[0]
        self.assertEqual((job["source"],job["remoteType"],job["department"],job["postedAt"]),("phenom","country_restricted","Analytics","2026-01-01T00:00:00+00:00"))
    @patch("crawler.pipeline.fetch_json")
    def test_microsoft_workplace_flexibility_marks_remote(self, fetch):
        fetch.return_value={"operationResult":{"result":{"totalJobs":1,"jobs":[{"jobId":"123","title":"Software Engineer","postingDate":"2026-01-01T00:00:00Z","properties":{"primaryLocation":"Redmond, Washington, United States","workSiteFlexibility":"Up to 100% work from home","employmentType":"Full-Time"}}]}}}
        job=microsoft({"name":"Microsoft","type":"microsoft","key":"microsoft"})[0]
        self.assertEqual((job["source"],job["remoteType"],job["remoteConfidence"]),("microsoft","country_restricted",0.93))
    def test_override_drop_removes_listing(self):
        jobs=[{"id":"keep","remoteType":"worldwide"},{"id":"gone","remoteType":"worldwide"}]
        kept=apply_overrides(jobs,[{"id":"gone","action":"drop","reason":"Hybrid, not remote","addedAt":"2026-09-03"}])
        self.assertEqual([j["id"] for j in kept],["keep"])
    def test_override_set_scope_pins_classification(self):
        jobs=[{"id":"x","remoteType":"worldwide","remoteConfidence":0.82,"remoteEvidence":"Remote"}]
        job=apply_overrides(jobs,[{"id":"x","action":"set_scope","value":"region_restricted","reason":"EMEA only.","addedAt":"2026-09-03"}])[0]
        self.assertEqual((job["remoteType"],job["remoteConfidence"],job["correction"]["reason"]),("region_restricted",1.0,"EMEA only."))
    @patch("crawler.pipeline.fetch_text")
    def test_jsonld_telecommute_is_remote(self, fetch):
        fetch.return_value='''<html><head>
          <script type="application/ld+json">{"@type":"JobPosting","title":"Backend Engineer",
            "identifier":"J-42","url":"https://acme.example/jobs/42","datePosted":"2026-02-01",
            "employmentType":"FULL_TIME","jobLocationType":"TELECOMMUTE",
            "applicantLocationRequirements":{"@type":"Country","name":"United States"},
            "description":"<p>Fully remote engineering role.</p>",
            "baseSalary":{"currency":"USD","value":{"minValue":150000,"maxValue":190000}}}</script>
        </head></html>'''
        job=jsonld({"name":"Acme","type":"jsonld","key":"acme","url":"https://acme.example/careers"})[0]
        self.assertEqual((job["source"],job["remoteType"],job["url"],job["postedAt"]),("jsonld","country_restricted","https://acme.example/jobs/42","2026-02-01"))
        self.assertEqual((job["experienceInferred"],job["salaryMin"]),(True,150000))
    @patch("crawler.pipeline.fetch_text")
    def test_jsonld_walks_itemlist_and_dedupes(self, fetch):
        fetch.return_value='''<script type="application/ld+json">{"@type":"ItemList","itemListElement":[
          {"@type":"ListItem","item":{"@type":"JobPosting","title":"A","identifier":"1","jobLocationType":"TELECOMMUTE"}},
          {"@type":"ListItem","item":{"@type":"JobPosting","title":"B","identifier":"1","jobLocationType":"TELECOMMUTE"}},
          {"@type":"ListItem","item":{"@type":"JobPosting","title":"C","identifier":"2","jobLocation":{"address":{"addressCountry":"Anywhere"}},"applicantLocationRequirements":{"name":"Worldwide"}}}
        ]}</script>'''
        jobs=jsonld({"name":"Acme","type":"jsonld","key":"acme","url":"https://acme.example/careers"})
        self.assertEqual([j["title"] for j in jobs],["A","C"])
    def test_collect_reports_per_source_health(self):
        rows=[
            {"id":"1","remoteType":"worldwide","remoteConfidence":0.9,"postedAt":"2026-01-02T00:00:00+00:00","company":"Acme"},
            {"id":"2","remoteType":"not_remote","remoteConfidence":0.96,"postedAt":"2026-01-01T00:00:00+00:00","company":"Acme"},
        ]
        with patch.dict("crawler.pipeline.ADAPTERS", {"greenhouse": MagicMock(return_value=rows)}):
            visible,errors,reports=collect([{"name":"Acme","type":"greenhouse","key":"acme"}])
        self.assertEqual((len(visible),errors),(1,[]))
        self.assertEqual((reports[0]["ok"],reports[0]["fetched"],reports[0]["visible"],reports[0]["avgConfidence"]),(True,2,1,0.9))
    def test_collect_records_adapter_failure(self):
        with patch.dict("crawler.pipeline.ADAPTERS", {"greenhouse": MagicMock(side_effect=RuntimeError("HTTP 500"))}):
            visible,errors,reports=collect([{"name":"Acme","type":"greenhouse","key":"acme"}])
        self.assertEqual((visible,len(errors)),([],1))
        self.assertEqual((reports[0]["ok"],reports[0]["error"]),(False,"HTTP 500"))

if __name__ == "__main__": unittest.main()
