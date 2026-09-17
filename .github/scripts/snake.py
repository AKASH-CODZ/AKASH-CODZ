"""Draws a snake eating the GitHub contribution graph, as a self-contained animated SVG.

Runs in GitHub Actions (see .github/workflows/snake.yml). Standard library only —
this repo's Actions settings only allow GitHub-owned actions, so a third-party
renderer (the usual Platane/snk action) can't run here; this replaces it with
a small one committed alongside the code, in the same spirit as profile_cards.py.
"""

import argparse
import json
import os
import urllib.request
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"

THEMES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "empty": "#161b22",
             "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"], "snake": "#00c6ff"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "empty": "#ebedf0",
              "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "snake": "#0969da"},
}

CELL = 11
GAP = 3


def fetch_weeks(user, token):
    query = {
        "query": "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{"
                 "weeks{contributionDays{date contributionCount weekday}}}}}}",
        "variables": {"u": user},
    }
    req = urllib.request.Request(
        API, data=json.dumps(query).encode(),
        headers={"Authorization": f"Bearer {token}", "User-Agent": "snake", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]


def build_grid(weeks):
    """weeks -> grid[week_index][weekday] = contributionCount (0 for a short first/last week)."""
    grid = []
    for week in weeks:
        col = [0] * 7
        for day in week["contributionDays"]:
            col[day["weekday"]] = day["contributionCount"]
        grid.append(col)
    return grid


def level(count):
    """GitHub's own bucket boundaries: 0, 1-3, 4-6, 7-9, 10+."""
    if count <= 0:
        return 0
    if count <= 3:
        return 1
    if count <= 6:
        return 2
    if count <= 9:
        return 3
    return 4


def serpentine_path(grid):
    """Visits every cell exactly once, boustrophedon-style: down column 0, up column 1,
    down column 2, and so on — the shape that makes it read as a snake eating the grid
    left to right rather than jumping back to the top of each new week."""
    path = []
    for w, col in enumerate(grid):
        rows = range(7) if w % 2 == 0 else range(6, -1, -1)
        for d in rows:
            path.append((w, d))
    return path


def render_snake_svg(grid, theme):
    t = THEMES[theme]
    weeks = len(grid)
    width = weeks * (CELL + GAP) + GAP
    height = 7 * (CELL + GAP) + GAP
    path = serpentine_path(grid)
    n = len(path)

    cells = []
    for i, (w, d) in enumerate(path):
        x = GAP + w * (CELL + GAP)
        y = GAP + d * (CELL + GAP)
        lvl = level(grid[w][d])
        color = t["levels"][lvl]
        delay = 0.35 + (i / max(n - 1, 1)) * 6.5
        cells.append(
            f'<rect id="cell-{w}-{d}" class="cell" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="2" fill="{escape(color)}" style="animation-delay:{delay:.3f}s"/>'
        )
        if lvl > 0:
            # A bright ring flashes over each non-empty cell right as the snake reaches it —
            # this is what actually reads as "eating" rather than a static heatmap.
            cells.append(
                f'<rect class="bite" x="{x - 1.5}" y="{y - 1.5}" width="{CELL + 3}" height="{CELL + 3}" '
                f'rx="3" fill="none" stroke="{t["snake"]}" stroke-width="2" '
                f'style="animation-delay:{delay:.3f}s"/>'
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="A snake eating the GitHub contribution graph">
<style>
  .cell {{ opacity: 0.35; animation: wake 0.4s ease-out forwards; }}
  .bite {{ opacity: 0; animation: flash 0.6s ease-out forwards; }}
  @keyframes wake {{ to {{ opacity: 1; }} }}
  @keyframes flash {{ 0% {{ opacity: 0; }} 35% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}
</style>
<rect x="0.5" y="0.5" rx="8" width="{width - 1}" height="{height - 1}" fill="{t['bg']}" stroke="{t['border']}"/>
{chr(10).join(cells)}
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", default="assets/generated")
    args = ap.parse_args()

    weeks = fetch_weeks(args.user, os.environ["GITHUB_TOKEN"])
    grid = build_grid(weeks)
    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(args.out, f"snake-{theme}.svg")
        with open(path, "w") as f:
            f.write(render_snake_svg(grid, theme))
        print("wrote", path)


if __name__ == "__main__":
    main()
