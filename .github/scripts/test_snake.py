import unittest
import xml.etree.ElementTree as ET

import snake as sn

# A tiny 3-week x 7-day grid, easier to reason about than a real 53-week year.
WEEKS = [
    {"contributionDays": [{"date": f"2026-01-0{d+1}", "contributionCount": c, "weekday": d}
                           for d, c in enumerate([0, 0, 1, 0, 0, 0, 0])]},
    {"contributionDays": [{"date": f"2026-01-0{d+8}", "contributionCount": c, "weekday": d}
                           for d, c in enumerate([0, 3, 0, 0, 6, 0, 0])]},
    {"contributionDays": [{"date": f"2026-01-{d+15}", "contributionCount": c, "weekday": d}
                           for d, c in enumerate([0, 0, 0, 2, 0, 0, 0])]},
]


class GridTests(unittest.TestCase):
    def test_grid_shape_matches_weeks_and_days(self):
        grid = sn.build_grid(WEEKS)
        self.assertEqual(len(grid), 3)
        self.assertEqual(len(grid[0]), 7)

    def test_level_thresholds(self):
        # GitHub-style buckets: 0, 1-3, 4-6, 7-9, 10+
        self.assertEqual(sn.level(0), 0)
        self.assertEqual(sn.level(1), 1)
        self.assertEqual(sn.level(3), 1)
        self.assertEqual(sn.level(4), 2)
        self.assertEqual(sn.level(6), 2)
        self.assertEqual(sn.level(7), 3)
        self.assertEqual(sn.level(9), 3)
        self.assertEqual(sn.level(10), 4)
        self.assertEqual(sn.level(999), 4)


class PathTests(unittest.TestCase):
    def test_serpentine_path_visits_every_cell_exactly_once(self):
        grid = sn.build_grid(WEEKS)
        path = sn.serpentine_path(grid)
        self.assertEqual(len(path), 3 * 7)
        self.assertEqual(len(set(path)), len(path))  # no repeats
        for week, day in path:
            self.assertTrue(0 <= week < 3)
            self.assertTrue(0 <= day < 7)

    def test_serpentine_alternates_direction_by_column(self):
        grid = sn.build_grid(WEEKS)
        path = sn.serpentine_path(grid)
        col0_days = [day for week, day in path if week == 0]
        col1_days = [day for week, day in path if week == 1]
        self.assertEqual(col0_days, list(range(7)))       # top to bottom
        self.assertEqual(col1_days, list(range(6, -1, -1)))  # bottom to top


class SvgTests(unittest.TestCase):
    def _parse(self, svg):
        return ET.fromstring(svg)

    def test_valid_animated_svg_both_themes(self):
        grid = sn.build_grid(WEEKS)
        for theme in ("dark", "light"):
            svg = sn.render_snake_svg(grid, theme)
            root = self._parse(svg)
            self.assertTrue(root.tag.endswith("svg"))
            self.assertIn("@keyframes", svg)

    def test_cell_count_matches_grid(self):
        grid = sn.build_grid(WEEKS)
        svg = sn.render_snake_svg(grid, "dark")
        self.assertEqual(svg.count("class=\"cell"), 3 * 7)

    def test_animation_delay_follows_path_order(self):
        grid = sn.build_grid(WEEKS)
        svg = sn.render_snake_svg(grid, "dark")
        # first-visited cell (0,0) should have a smaller delay than the
        # last-visited cell (2,3) in the snake's own eating order.
        path = sn.serpentine_path(grid)
        first_id = f'cell-{path[0][0]}-{path[0][1]}'
        last_id = f'cell-{path[-1][0]}-{path[-1][1]}'
        first_pos = svg.index(first_id)
        last_pos = svg.index(last_id)
        self.assertLess(first_pos, last_pos)


if __name__ == "__main__":
    unittest.main()
