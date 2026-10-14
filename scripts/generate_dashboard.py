#!/usr/bin/env python3
"""Gera assets/dashboard.svg com os dados do GitHub (ou dados de exemplo com --mock)."""
import json
import math
import os
import sys
import textwrap
import urllib.request
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = json.load(open(os.path.join(ROOT, "dashboard-config.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "assets", "dashboard.svg")

FALLBACK = ["#1E90FF", "#87CEFA", "#4169E1", "#00BFFF", "#6A5ACD", "#5F9EA0"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    u = data["data"]["user"]
    cc = u["contributionsCollection"]
    langs = {}
    stars = 0
    for repo in u["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            if n in CONFIG.get("exclude_languages", []):
                continue
            cur = langs.setdefault(n, {"size": 0, "color": e["node"]["color"]})
            cur["size"] += e["size"]
    total = sum(v["size"] for v in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1]["size"])[:6]
    languages = [(n, v["size"] * 100 / total, v["color"]) for n, v in top]
    return {
        "commits": cc["totalCommitContributions"],
        "stars": stars,
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "repos": u["repositories"]["totalCount"],
        "languages": languages,
    }


def mock():
    return {
        "commits": 87, "stars": 1, "prs": 0, "issues": 0, "repos": 5,
        "languages": [
            ("JavaScript", 36.0, "#f1e05a"), ("HTML", 24.0, "#e34c26"),
            ("CSS", 20.0, "#663399"), ("Java", 12.0, "#b07219"),
            ("TypeScript", 8.0, "#3178c6"),
        ],
    }


def radar(cx, cy, r, focus):
    keys = list(focus)
    n = len(keys)
    if n < 3:
        return ""
    mx = max(focus.values()) or 1
    ang = [-math.pi / 2 + 2 * math.pi * i / n for i in range(n)]
    out = []
    for k in (1 / 3, 2 / 3, 1):
        pts = " ".join(f"{cx + r * k * math.cos(a):.1f},{cy + r * k * math.sin(a):.1f}" for a in ang)
        out.append(f'<polygon points="{pts}" fill="none" stroke="#1e2d45" stroke-width="1"/>')
    for a in ang:
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{cx + r * math.cos(a):.1f}" y2="{cy + r * math.sin(a):.1f}" stroke="#1e2d45"/>')
    pts = " ".join(
        f"{cx + r * (focus[k] / mx) * math.cos(a):.1f},{cy + r * (focus[k] / mx) * math.sin(a):.1f}"
        for k, a in zip(keys, ang)
    )
    out.append(f'<polygon class="pulse" points="{pts}" fill="#1E90FF" fill-opacity=".25" stroke="#1E90FF" stroke-width="1.5"/>')
    for k, a in zip(keys, ang):
        lx = cx + (r + 16) * math.cos(a)
        ly = cy + (r + 16) * math.sin(a) + 4
        anchor = "middle" if abs(math.cos(a)) < 0.3 else ("start" if math.cos(a) > 0 else "end")
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" class="tag" text-anchor="{anchor}">{escape(k)}</text>')
        out.append(f'<text x="{lx:.1f}" y="{ly + 12:.1f}" class="sub" text-anchor="{anchor}">({focus[k]})</text>')
    return "\n".join(out)


STYLE = """<defs>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<style>
text{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace}
.card{fill:#0d1520;stroke:#16233a;stroke-width:1}
.head{font-size:11px;letter-spacing:3px;fill:#4a6fa5}
.num{font-size:32px;font-weight:700;fill:#ffffff}
.lbl{font-size:11px;fill:#5c7da8}
.lang{font-size:12px;fill:#b7c6e0}
.pct{font-size:11px;fill:#5c7da8}
.tag{font-size:10px;fill:#1E90FF}
.sub{font-size:9px;fill:#5c7da8}
.pname{font-size:15px;font-weight:700;fill:#ffffff}
.pdesc{font-size:10.5px;fill:#8fa3c4}
.pill{font-size:10px;fill:#87CEFA}
.bar{transform-box:fill-box;transform-origin:left;animation:grow 1.4s ease-out both}
.fade{animation:fade 1s ease-out both}
.pulse{animation:pulse 3s ease-in-out infinite}
.dot{animation:blink 1.6s ease-in-out infinite}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pulse{0%,100%{opacity:.7}50%{opacity:1}}
@keyframes blink{0%,100%{opacity:.3}50%{opacity:1}}
</style>
<rect width="800" height="570" fill="#05080f"/>"""


def build(d):
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="570" viewBox="0 0 800 570" role="img" aria-label="Painel de estatisticas do GitHub">', STYLE]

    # Card 1: numeros
    p.append('<rect class="card" x="20" y="20" width="760" height="120" rx="8"/>')
    p.append('<text x="44" y="48" class="head">MISSION TELEMETRY</text>')
    stats = [(d["commits"], "Commits"), (d["stars"], "Stars"), (d["prs"], "PRs"), (d["issues"], "Issues"), (d["repos"], "Repos")]
    for i, (v, label) in enumerate(stats):
        cx = 20 + 76 + 152 * i
        p.append(f'<g class="fade" style="animation-delay:{0.15 * i}s">'
                 f'<text x="{cx}" y="92" class="num" text-anchor="middle" filter="url(#glow)">{v}</text>'
                 f'<text x="{cx}" y="118" class="lbl" text-anchor="middle">{escape(label)}</text></g>')
        if i:
            p.append(f'<line x1="{20 + 152 * i}" y1="62" x2="{20 + 152 * i}" y2="124" stroke="#16233a"/>')

    # Card 2: linguagens + radar
    p.append('<rect class="card" x="20" y="160" width="760" height="220" rx="8"/>')
    p.append('<text x="44" y="190" class="head">LANGUAGE TELEMETRY</text>')
    p.append('<line x1="420" y1="180" x2="420" y2="362" stroke="#16233a"/>')
    p.append('<text x="444" y="190" class="head">FOCUS SECTORS</text>')
    for i, (name, pct, color) in enumerate(d["languages"]):
        y = 224 + i * 26
        w = max(6, pct / 100 * 170)
        c = color or FALLBACK[i % len(FALLBACK)]
        p.append(f'<text x="44" y="{y}" class="lang">{escape(name)}</text>')
        p.append(f'<rect class="bar" style="animation-delay:{0.1 * i}s" x="150" y="{y - 10}" width="{w:.1f}" height="10" rx="3" fill="{c}"/>')
        p.append(f'<text x="396" y="{y}" class="pct" text-anchor="end">{pct:.1f}%</text>')
    p.append(radar(600, 282, 58, CONFIG.get("focus", {})))

    # Card 3: projetos
    projs = CONFIG.get("projects", [])[:3]
    p.append('<rect class="card" x="20" y="400" width="760" height="152" rx="8"/>')
    p.append('<text x="44" y="428" class="head">FEATURED SYSTEMS</text>')
    p.append('<circle class="dot" cx="206" cy="424" r="3" fill="#00BFFF"/>')
    p.append(f'<text x="756" y="428" class="head" text-anchor="end" style="letter-spacing:2px;font-size:10px">SYS {len(projs)}/{len(projs)} ONLINE</text>')
    n = max(1, len(projs))
    gap = 20
    w = (712 - gap * (n - 1)) / n
    for i, pr in enumerate(projs):
        x = 44 + i * (w + gap)
        cx = x + w / 2
        url = pr.get("url")
        if url:
            p.append(f'<a href="{escape(url)}" target="_blank">')
        p.append(f'<g class="fade" style="animation-delay:{0.2 * i}s">')
        p.append(f'<rect x="{x:.1f}" y="442" width="{w:.1f}" height="96" rx="8" fill="#0a111c" stroke="#16233a"/>')
        p.append(f'<circle class="pulse" cx="{cx:.1f}" cy="458" r="7" fill="none" stroke="#1E90FF" stroke-width="1.5"/>')
        p.append(f'<circle cx="{cx:.1f}" cy="458" r="2.5" fill="#87CEFA"/>')
        p.append(f'<text x="{cx:.1f}" y="484" class="pname" text-anchor="middle">{escape(pr["name"])}</text>')
        for j, ln in enumerate(textwrap.wrap(pr.get("description", ""), max(20, int(w / 6.3)))[:2]):
            p.append(f'<text x="{cx:.1f}" y="{499 + j * 12}" class="pdesc" text-anchor="middle">{escape(ln)}</text>')
        tag = pr.get("tag", "")
        if tag:
            tw = len(tag) * 6.5 + 22
            p.append(f'<rect x="{cx - tw / 2:.1f}" y="517" width="{tw:.1f}" height="16" rx="8" fill="#0f2a4d" stroke="#1E90FF" stroke-opacity=".5"/>')
            p.append(f'<text x="{cx:.1f}" y="528" class="pill" text-anchor="middle">{escape(tag)}</text>')
        p.append("</g>")
        if url:
            p.append("</a>")
    p.append("</svg>")
    return "\n".join(p)


def main():
    if "--mock" in sys.argv:
        d = mock()
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("Defina GH_TOKEN ou GITHUB_TOKEN (ou use --mock).")
        d = fetch(CONFIG["username"], token)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build(d))
    print("Gerado:", OUT)


if __name__ == "__main__":
    main()
