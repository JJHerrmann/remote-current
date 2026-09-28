import unittest

from crawler.dates import listing_date, listing_datetime


class ListingDateTests(unittest.TestCase):
    def test_normal_listing_uses_employer_posted_date(self):
        job = {
            "postedAt": "2026-09-27T08:00:00+00:00",
            "firstSeenAt": "2026-09-27T09:00:00+00:00",
        }
        self.assertEqual(listing_date(job), job["postedAt"])

    def test_republished_listing_keeps_original_first_seen_age(self):
        job = {
            "postedAt": "2026-09-28T06:53:04+00:00",
            "firstSeenAt": "2026-09-07T16:28:27+00:00",
        }
        self.assertEqual(listing_date(job), job["firstSeenAt"])

    def test_missing_dates_sort_oldest(self):
        self.assertEqual(listing_datetime({}).year, 1)


if __name__ == "__main__":
    unittest.main()
