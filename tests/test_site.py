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

    def test_board_has_accessible_search_controls(self):
        page = (ROOT / "index.html").read_text()
        self.assertIn('class="skip-link" href="#results"', page)
        self.assertIn('id="clearFilters"', page)
        self.assertIn('id="resultStatus" role="status" aria-live="polite"', page)
        self.assertNotIn('class="rows" id="rows" aria-live=', page)

    def test_about_page_documents_methodology_feedback_and_privacy(self):
        page = (ROOT / "about.html").read_text()
        self.assertIn('<h2 id="methodology">How it works, precisely</h2>', page)
        self.assertIn('No generative-AI model selects jobs', page)
        self.assertIn('<h2 id="feedback">Corrections and feedback</h2>', page)
        self.assertIn('<h2 id="privacy">What it does not collect</h2>', page)

    def test_all_public_pages_use_the_evergreen_share_card(self):
        share_url = "https://remotecurrent.rook.works/assets/og-image-evergreen.jpg"
        for name in ("index.html", "story.html", "about.html", "sources.html"):
            page = (ROOT / name).read_text()
            self.assertIn(f'<meta property="og:image" content="{share_url}">', page)
            self.assertIn(f'<meta name="twitter:image" content="{share_url}">', page)
            self.assertIn('<meta property="og:image:width" content="1200">', page)
            self.assertIn('<meta property="og:image:height" content="630">', page)
            self.assertNotIn('assets/og-image.jpg', page)


if __name__ == "__main__":
    unittest.main()
