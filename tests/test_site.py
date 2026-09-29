import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicSiteTests(unittest.TestCase):
    def test_board_has_visible_payment_path(self):
        page = (ROOT / "index.html").read_text()
        self.assertGreaterEqual(page.count('data-revenue="support"'), 3)
        self.assertIn("https://ko-fi.com/mindpalacegarden", page)
        self.assertIn("RemoteCurrent is made possible by readers like you.", page)
        self.assertIn("one-time or monthly &middot; no donor-only listings", page)

    def test_support_links_are_safe_external_links(self):
        page = (ROOT / "index.html").read_text()
        for fragment in page.split('href="https://ko-fi.com/mindpalacegarden"')[1:]:
            tag = fragment.split(">", 1)[0]
            self.assertIn('target="_blank"', tag)
            self.assertIn('rel="noopener noreferrer"', tag)

    def test_about_page_has_support_anchor(self):
        page = (ROOT / "about.html").read_text()
        self.assertIn('<h2 id="support">Support RemoteCurrent</h2>', page)

    def test_secondary_page_readouts_are_navigation(self):
        story = (ROOT / "story.html").read_text()
        about = (ROOT / "about.html").read_text()
        self.assertIn('<nav class="readout" aria-label="Project sections">', story)
        self.assertIn('<a href="./">Open index</a>', story)
        self.assertIn('<a href="about.html#pledge">Free forever</a>', story)
        self.assertIn('<a href="story.html" aria-current="page">The story</a>', story)
        self.assertIn('<h2 id="pledge">The pledge</h2>', about)


if __name__ == "__main__":
    unittest.main()
