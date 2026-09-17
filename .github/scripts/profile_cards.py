"""Build the animated stats/language cards and the "recently pushed" list for the profile README.

Runs in GitHub Actions (see .github/workflows/profile-cards.yml). Standard library only.
Works without a token (public REST API); with GITHUB_TOKEN it also reads the yearly
contribution count via GraphQL.
"""

import argparse
import json
import os
import re
import urllib.request
from xml.sax.saxutils import escape

API = "https://api.github.com"

THEMES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "title": "#00c6ff", "text": "#c9d1d9", "muted": "#8b949e", "track": "#21262d"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "title": "#0969da", "text": "#1f2328", "muted": "#656d76", "track": "#eaeef2"},
}

LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Java": "#b07219",
    "HTML": "#e34c26", "CSS": "#663399", "Shell": "#89e051", "Dockerfile": "#384d54",
    "Makefile": "#427819", "HCL": "#844FBA", "Jupyter Notebook": "#DA5B0B",
}

MARK_START = "<!-- recent:start -->"
MARK_END = "<!-- recent:end -->"


def _get(url, token=None, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-cards"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch(user, token=None):
    repos = _get(f"{API}/users/{user}/repos?per_page=100&type=owner", token)
    langs = {r["name"]: _get(r["languages_url"], token) for r in repos if not r["fork"]}
    contributions = None
    if token:
        query = {"query": "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions}}}}",
                 "variables": {"u": user}}
        try:
            res = _get(f"{API}/graphql", token, json.dumps(query).encode())
            contributions = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        except (OSError, KeyError, TypeError) as exc:
            # The card still renders without this row; say why in the job log.
            print(f"contributions unavailable: {exc}")
    return repos, langs, contributions


def summarize(repos, langs, contributions, top=6):
    own = [r for r in repos if not r["fork"]]
    totals = {}
    for per_repo in langs.values():
        for name, size in per_repo.items():
            totals[name] = totals.get(name, 0) + size
    grand = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top]
    languages = [(name, round(size * 100 / grand, 1)) for name, size in ranked]
    recent = sorted(own, key=lambda r: r["pushed_at"], reverse=True)
    return {
        "repos": len(own),
        "stars": sum(r["stargazers_count"] for r in own),
        "contributions": contributions,
        "languages": languages,
        "recent": recent,
    }


def _frame(width, height, theme, title, body):
    t = THEMES[theme]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
<style>
  .t {{ font: 600 17px 'Segoe UI', Ubuntu, sans-serif; fill: {t['title']}; }}
  .l {{ font: 400 14px 'Segoe UI', Ubuntu, sans-serif; fill: {t['muted']}; }}
  .v {{ font: 700 15px 'Segoe UI', Ubuntu, sans-serif; fill: {t['text']}; }}
  .row {{ opacity: 0; animation: rise .6s ease-out forwards; }}
  .bar {{ transform-box: fill-box; transform-origin: left; transform: scaleX(0); animation: grow 1.1s cubic-bezier(.2,.8,.2,1) forwards; }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
  @keyframes grow {{ to {{ transform: scaleX(1); }} }}
</style>
<rect x="0.5" y="0.5" rx="10" width="{width - 1}" height="{height - 1}" fill="{t['bg']}" stroke="{t['border']}"/>
<text class="t" x="24" y="36">{escape(title)}</text>
{body}
</svg>
"""


def render_stats_svg(s, theme):
    rows = [("Public repositories", s["repos"]), ("Stars earned", s["stars"])]
    if s["contributions"] is not None:
        rows.append(("Contributions, last 12 months", s["contributions"]))
    if s["languages"]:
        rows.append(("Most used language", s["languages"][0][0]))
    body = []
    for i, (label, value) in enumerate(rows):
        # 42px rows make a 4-row card as tall as the 6-language card, so they sit side by side evenly.
        y = 80 + i * 42
        body.append(
            f'<g class="row" style="animation-delay:{0.15 + i * 0.15:.2f}s">'
            f'<text class="l" x="24" y="{y}">{escape(label)}</text>'
            f'<text class="v" x="336" y="{y}" text-anchor="end">{escape(str(value))}</text></g>'
        )
    height = 80 + (len(rows) - 1) * 42 + 44
    return _frame(360, height, theme, "GitHub at a glance", "\n".join(body))


def render_langs_svg(s, theme):
    t = THEMES[theme]
    body = []
    for i, (name, pct) in enumerate(s["languages"]):
        y = 64 + i * 30
        color = LANG_COLORS.get(name, t["title"])
        width = max(2.0, 200 * pct / 100)
        delay = 0.15 + i * 0.12
        body.append(
            f'<g class="row" style="animation-delay:{delay:.2f}s">'
            f'<text class="l" x="24" y="{y + 11}">{escape(name)}</text>'
            f'<rect x="130" y="{y}" width="200" height="12" rx="6" fill="{t["track"]}"/>'
            f'<rect class="bar" style="animation-delay:{delay + 0.1:.2f}s" x="130" y="{y}" width="{width:.1f}" height="12" rx="6" fill="{color}"/>'
            f'<text class="v" x="396" y="{y + 11}" text-anchor="end">{pct:.1f}%</text></g>'
        )
    height = 64 + len(s["languages"]) * 30 + 6
    return _frame(420, height, theme, "Languages across my repos", "\n".join(body))


def render_recent_block(s, limit=5):
    lines = []
    for r in s["recent"][:limit]:
        desc = f" · {r['description'].strip()}" if r.get("description") else ""
        lines.append(f"- [{r['name']}]({r['html_url']}) <sub>{r['pushed_at'][:10]}</sub>{desc}")
    return "\n".join(lines)


def update_readme_section(text, block):
    pattern = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), re.S)
    if not pattern.search(text):
        return text
    return pattern.sub(lambda _: f"{MARK_START}\n{block}\n{MARK_END}", text, count=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", default="assets/generated")
    ap.add_argument("--readme", default=None)
    args = ap.parse_args()

    repos, langs, contributions = fetch(args.user, os.environ.get("GITHUB_TOKEN"))
    s = summarize(repos, langs, contributions)
    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(args.out, f"stats-{theme}.svg"), "w") as f:
            f.write(render_stats_svg(s, theme))
        with open(os.path.join(args.out, f"languages-{theme}.svg"), "w") as f:
            f.write(render_langs_svg(s, theme))
    if args.readme:
        with open(args.readme) as f:
            text = f.read()
        new = update_readme_section(text, render_recent_block(s))
        if new != text:
            with open(args.readme, "w") as f:
                f.write(new)
    print(f"repos={s['repos']} stars={s['stars']} contributions={s['contributions']} langs={s['languages']}")


if __name__ == "__main__":
    main()
