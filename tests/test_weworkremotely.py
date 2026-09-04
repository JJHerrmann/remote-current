import unittest
from unittest.mock import patch
from crawler.weworkremotely import fetch_category, fetch_listings

_FEED = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title>Samsara: Staff Software Engineer</title>
  <region>Anywhere in the World</region>
  <category>Full-Stack Programming</category>
  <description>&lt;p&gt;This role is fully remote.&lt;/p&gt;</description>
  <pubDate>Mon, 17 Aug 2026 13:57:14 +0000</pubDate>
  <guid>https://weworkremotely.com/remote-jobs/samsara-staff-software-engineer</guid>
  <link>https://weworkremotely.com/remote-jobs/samsara-staff-software-engineer</link>
</item>
<item>
  <title>Sponsored blurb with no colon</title>
  <region>Anywhere</region>
  <description></description>
  <pubDate>Mon, 17 Aug 2026 13:57:14 +0000</pubDate>
  <link>https://weworkremotely.com/sponsored</link>
</item>
</channel></rss>'''

class WeWorkRemotelyTests(unittest.TestCase):
    @patch("crawler.weworkremotely.fetch_text", return_value=_FEED)
    def test_parses_company_and_title_from_the_colon_convention(self, _fetch):
        listings = fetch_category("remote-programming-jobs")
        self.assertEqual(len(listings), 1)
        listing = listings[0]
        self.assertEqual((listing["company"], listing["title"], listing["provider"]), ("Samsara", "Staff Software Engineer", "weworkremotely"))
        self.assertEqual(listing["url"], "https://weworkremotely.com/remote-jobs/samsara-staff-software-engineer")
        self.assertEqual(listing["publishedAt"], "2026-08-17T13:57:14+00:00")

    @patch("crawler.weworkremotely.fetch_text", return_value=_FEED)
    def test_rows_without_a_colon_title_are_skipped(self, _fetch):
        # the fixture's second <item> has no "Company: Title" colon and must not appear
        listings = fetch_category("remote-programming-jobs")
        self.assertEqual([l["title"] for l in listings], ["Staff Software Engineer"])

    @patch("crawler.weworkremotely.fetch_text", return_value=_FEED)
    def test_fetch_listings_dedupes_the_same_url_across_categories(self, _fetch):
        listings = fetch_listings(["remote-programming-jobs", "remote-design-jobs"])
        self.assertEqual(len(listings), 1)

if __name__ == "__main__":
    unittest.main()
