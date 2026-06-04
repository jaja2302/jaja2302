#!/usr/bin/env python3
"""
Contribution Harvest  -  an original animated GitHub contribution graph.
Built from scratch (no third-party graph generators).

A little harvester drone sweeps across your contribution grid; each column
"ripens" and flashes as the drone passes over it. Colours go from dark soil
to ripe gold based on how active that day was.

Usage (in GitHub Actions):
    GH_TOKEN=<token> USERNAME=<login> python harvest.py
Local test (no token -> uses random demo data):
    python harvest.py
"""

import os
import json
import random
import urllib.request

# ----- config -----
USERNAME = os.environ.get("USERNAME", "demo-user")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT_PATH = os.environ.get("OUT_PATH", "assets/harvest.svg")

CELL = 12
STEP = 15
X0 = 26
Y0 = 60
LOOP = 14.0          # seconds for one full sweep
FLASH_W = 0.016      # half-width of each column's flash, as fraction of loop

# soil -> sprout -> leaf -> lush -> ripe gold
PALETTE = ["#15231a", "#2c5e3a", "#3f9d4f", "#74c365", "#f4c430"]


def fetch_weeks():
    """Return list of weeks; each week is a list of {count} for up to 7 days."""
    if not TOKEN:
        # demo data so the script runs locally without credentials
        return [[{"count": random.choice([0, 0, 0, 1, 2, 3, 5, 8, 12, 15])}
                 for _ in range(7)] for _ in range(53)]

    query = """
    query($login:String!){
      user(login:$login){
        contributionsCollection{
          contributionCalendar{
            weeks{ contributionDays{ contributionCount } }
          }
        }
      }
    }"""
    body = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": "harvest-generator"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    weeks_raw = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[{"count": d["contributionCount"]} for d in w["contributionDays"]] for w in weeks_raw]


def level(count):
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 9:
        return 3
    return 4


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def build_svg(weeks):
    cols = len(weeks)
    width = X0 + cols * STEP + 20
    height = Y0 + 7 * STEP + 46
    grid_bottom = Y0 + 7 * STEP

    # sweep geometry: drone travels from off-left to off-right
    x_start, x_end = -40, width + 40
    span = x_end - x_start

    drone_y = Y0 - 16
    beam_h = grid_bottom - drone_y

    parts = []
    parts.append(
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="\'Segoe UI\',Helvetica,Arial,sans-serif">'
    )

    # defs: gradients + filters
    parts.append('<defs>')
    parts.append(
        '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#0d1b2a"/>'
        '<stop offset="100%" stop-color="#12241a"/></linearGradient>'
    )
    parts.append(
        '<linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#ffe08a" stop-opacity="0.45"/>'
        '<stop offset="100%" stop-color="#ffe08a" stop-opacity="0"/></linearGradient>'
    )
    parts.append(
        '<filter id="soft" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur stdDeviation="2.2"/></filter>'
    )
    parts.append('</defs>')

    # background
    parts.append(f'<rect width="{width}" height="{height}" rx="10" fill="url(#sky)"/>')

    # title
    parts.append(
        f'<text x="{X0}" y="30" font-size="17" font-weight="800" fill="#eaf3ec">'
        f'Contribution Harvest</text>'
    )
    parts.append(
        f'<text x="{X0}" y="48" font-size="11" fill="#7fae8c" letter-spacing="1">'
        f'@{USERNAME} &#183; a field tended one commit at a time</text>'
    )

    total = sum(d["count"] for w in weeks for d in w)
    parts.append(
        f'<text x="{width-20}" y="30" text-anchor="end" font-size="15" '
        f'font-weight="800" fill="#f4c430">{total}</text>'
    )
    parts.append(
        f'<text x="{width-20}" y="46" text-anchor="end" font-size="9" '
        f'fill="#7fae8c" letter-spacing="1">CONTRIBUTIONS</text>'
    )

    # cells + synced flash overlay
    for ci, week in enumerate(weeks):
        cx = X0 + ci * STEP
        col_center = cx + CELL / 2
        frac = clamp((col_center - x_start) / span, 0.02, 0.98)
        t1 = clamp(frac - FLASH_W, 0.005, frac - 0.002)
        t3 = clamp(frac + FLASH_W, frac + 0.002, 0.995)
        for di, day in enumerate(week):
            lv = level(day["count"])
            cy = Y0 + di * STEP
            color = PALETTE[lv]
            # base cell
            parts.append(
                f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{color}" opacity="0.9"/>'
            )
            # flash overlay (brighter when the cell is more active)
            peak = round(0.12 + lv * 0.16, 3)
            parts.append(
                f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="2.5" fill="#fff5cc">'
                f'<animate attributeName="opacity" values="0;0;{peak};0;0" '
                f'keyTimes="0;{t1:.4f};{frac:.4f};{t3:.4f};1" '
                f'dur="{LOOP}s" repeatCount="indefinite"/></rect>'
            )

    # the harvester drone (drawn at local origin, then swept across X)
    drone = []
    drone.append('<g>')
    # beam pointing down at the column below
    drone.append(
        f'<polygon points="-5,9 5,9 11,{beam_h} -11,{beam_h}" fill="url(#beam)">'
        f'<animate attributeName="opacity" values="0.5;1;0.5" dur="0.9s" repeatCount="indefinite"/>'
        f'</polygon>'
    )
    # soft glow
    drone.append('<circle cx="0" cy="0" r="13" fill="#ffe08a" opacity="0.25" filter="url(#soft)"/>')
    # rotors (quick spin)
    drone.append(
        '<g stroke="#cfe9d6" stroke-width="2" stroke-linecap="round">'
        '<line x1="-16" y1="-7" x2="-4" y2="-7"/>'
        '<line x1="4" y1="-7" x2="16" y2="-7">'
        '</line></g>'
    )
    drone.append('<line x1="-10" y1="-7" x2="-10" y2="-2" stroke="#cfe9d6" stroke-width="1.5"/>')
    drone.append('<line x1="10" y1="-7" x2="10" y2="-2" stroke="#cfe9d6" stroke-width="1.5"/>')
    # spinning blades
    drone.append(
        '<g>'
        '<ellipse cx="-10" cy="-7" rx="9" ry="2" fill="#9bd3a8" opacity="0.7">'
        '<animateTransform attributeName="transform" type="scale" values="1 1;0.2 1;1 1" '
        'dur="0.18s" repeatCount="indefinite" additive="sum"/></ellipse>'
        '</g>'
    )
    # body
    drone.append('<rect x="-12" y="-4" width="24" height="11" rx="5.5" fill="#3fa34d"/>')
    drone.append('<rect x="-12" y="-4" width="24" height="5" rx="2.5" fill="#54c065"/>')
    drone.append('<circle cx="0" cy="2" r="2.4" fill="#0d1b2a"/>')  # lens
    drone.append('</g>')
    drone_inner = "".join(drone)

    # bob + sweep
    parts.append(
        f'<g>'
        f'<animateTransform attributeName="transform" type="translate" '
        f'values="{x_start} {drone_y};{x_end} {drone_y}" dur="{LOOP}s" '
        f'calcMode="linear" repeatCount="indefinite"/>'
        f'<g><animateTransform attributeName="transform" type="translate" '
        f'values="0 0;0 -3;0 0" dur="2.2s" repeatCount="indefinite" additive="sum"/>'
        f'{drone_inner}</g></g>'
    )

    # legend
    ly = grid_bottom + 26
    parts.append(f'<text x="{X0}" y="{ly+4}" font-size="9" fill="#7fae8c">Less</text>')
    lx = X0 + 34
    for i, c in enumerate(PALETTE):
        parts.append(f'<rect x="{lx + i*16}" y="{ly-7}" width="11" height="11" rx="2.5" fill="{c}"/>')
    parts.append(f'<text x="{lx + len(PALETTE)*16 + 4}" y="{ly+4}" font-size="9" fill="#7fae8c">More</text>')

    parts.append('</svg>')
    return "".join(parts)


def main():
    weeks = fetch_weeks()
    svg = build_svg(weeks)
    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {OUT_PATH} ({len(svg)} bytes, {len(weeks)} weeks)")


if __name__ == "__main__":
    main()
