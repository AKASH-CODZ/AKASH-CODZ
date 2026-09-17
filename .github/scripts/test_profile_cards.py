import unittest
import xml.etree.ElementTree as ET

import profile_cards as pc

REPOS = [
    {"name": "Voice-Ai", "fork": False, "stargazers_count": 2, "pushed_at": "2026-09-07T10:00:00Z",
     "description": "Talk to it", "html_url": "https://github.com/x/Voice-Ai", "language": "Python"},
    {"name": "old-fork", "fork": True, "stargazers_count": 50, "pushed_at": "2026-09-10T10:00:00Z",
     "description": None, "html_url": "https://github.com/x/old-fork", "language": "C"},
    {"name": "calib", "fork": False, "stargazers_count": 1, "pushed_at": "2026-04-11T10:00:00Z",
     "description": None, "html_url": "https://github.com/x/calib", "language": "Python"},
]
LANGS = {"Voice-Ai": {"Python": 700, "TypeScript": 300}, "calib": {"Python": 1000}}


class SummaryTests(unittest.TestCase):
    def test_summary_skips_forks(self):
        s = pc.summarize(REPOS, LANGS, contributions=321)
        self.assertEqual(s["repos"], 2)
        self.assertEqual(s["stars"], 3)
        self.assertEqual(s["contributions"], 321)

    def test_languages_sorted_and_sum_to_100(self):
        s = pc.summarize(REPOS, LANGS, contributions=None)
        names = [n for n, _ in s["languages"]]
        self.assertEqual(names, ["Python", "TypeScript"])
        self.assertAlmostEqual(sum(p for _, p in s["languages"]), 100.0, places=1)

    def test_recent_is_newest_first_without_forks(self):
        s = pc.summarize(REPOS, LANGS, contributions=None)
        self.assertEqual([r["name"] for r in s["recent"]], ["Voice-Ai", "calib"])


class SvgTests(unittest.TestCase):
    def setUp(self):
        self.s = pc.summarize(REPOS, LANGS, contributions=321)

    def _parse(self, svg):
        return ET.fromstring(svg)

    def test_stats_svg_is_valid_animated_xml(self):
        for theme in ("dark", "light"):
            svg = pc.render_stats_svg(self.s, theme)
            root = self._parse(svg)
            self.assertTrue(root.tag.endswith("svg"))
            self.assertIn("@keyframes", svg)
            self.assertIn(">321<", svg)

    def test_stats_svg_without_contributions_has_no_none(self):
        s = pc.summarize(REPOS, LANGS, contributions=None)
        svg = pc.render_stats_svg(s, "dark")
        self._parse(svg)
        self.assertNotIn("None", svg)

    def test_langs_svg_valid(self):
        svg = pc.render_langs_svg(self.s, "light")
        self._parse(svg)
        self.assertIn("Python", svg)
        self.assertIn("85.0%", svg)  # Python: (700 + 1000) / 2000 bytes

    def test_text_is_escaped(self):
        s = dict(self.s)
        s["languages"] = [("C<&>", 100.0)]
        self._parse(pc.render_langs_svg(s, "dark"))


class ReadmeTests(unittest.TestCase):
    TEXT = "head\n<!-- recent:start -->\nold\n<!-- recent:end -->\ntail\n"

    def test_replaces_only_between_markers(self):
        out = pc.update_readme_section(self.TEXT, "new line")
        self.assertIn("head\n", out)
        self.assertIn("\ntail\n", out)
        self.assertIn("new line", out)
        self.assertNotIn("old", out)

    def test_idempotent(self):
        once = pc.update_readme_section(self.TEXT, "x")
        self.assertEqual(once, pc.update_readme_section(once, "x"))

    def test_missing_markers_leaves_text(self):
        self.assertEqual(pc.update_readme_section("no markers", "x"), "no markers")

    def test_recent_block_lists_links(self):
        s = pc.summarize(REPOS, LANGS, contributions=None)
        block = pc.render_recent_block(s)
        self.assertIn("[Voice-Ai](https://github.com/x/Voice-Ai)", block)
        self.assertIn("2026-09-07", block)


if __name__ == "__main__":
    unittest.main()
