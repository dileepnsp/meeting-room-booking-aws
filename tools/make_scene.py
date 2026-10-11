"""Generate the boardroom-with-sea-view background (day + night) as animated SVG.

  python tools/make_scene.py   ->  frontend/assets/scene-day.svg, scene-night.svg

Animation uses SMIL (<animate>/<animateTransform>) and presentation attributes only, never <style>:
the site's CSP (style-src 'self') also applies to the SVG files and would block inline styles.
"""
import pathlib
import random

OUT = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "assets"
W, H = 1600, 1000
HORIZON, SILL = 560, 700

PALETTES = {
    "day": dict(
        sky=["#5ea8ec", "#9fd0f7", "#dcefff", "#ffe8d2"], sun="#fff6d8", glow="#ffe7a8",
        cloud="#ffffff", cloud_op=.9, far="#9db8cf", near="#7f9db8", sea=["#5f9fd1", "#2f6f9f", "#1f4f78"],
        glint="#fff7e0", frame="#2a2f36", ceiling="#e9e6e1", lamp="#fff2cc", lamp_glow=.25,
        floor=["#cdbfae", "#a8957f"], wall_light="#ffffff", table=["#8a5a3b", "#6b4229"], table_edge="#b07a52",
        chair="#2b2f35", plane="#f4f6f8", plane_shadow="#9aa6b2", trail="#ffffff", boat="#ffffff",
        stars=False, city=False, interior_shade=0,
    ),
    "night": dict(
        sky=["#070b1d", "#111a3d", "#28305e", "#4b3e6e"], sun="#f3f1e6", glow="#c9d4ff",
        cloud="#8892c4", cloud_op=.18, far="#1d2445", near="#161c38", sea=["#1c2650", "#111834", "#0a0f22"],
        glint="#dfe6ff", frame="#0d0f14", ceiling="#2a2b33", lamp="#ffd27a", lamp_glow=.45,
        floor=["#3a3430", "#26211e"], wall_light="#ffd9a0", table=["#5a3a26", "#3e2718"], table_edge="#8a5d3d",
        chair="#121418", plane="#cfd6e6", plane_shadow="#5a6380", trail="#aab4d8", boat="#c9cfe0",
        stars=True, city=True, interior_shade=.18,
    ),
}


def svg(mode):
    p = PALETTES[mode]
    rnd = random.Random(7)
    o = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" '
      f'role="img" aria-label="Boardroom with floor-to-ceiling windows overlooking the sea">')
    a("<defs>")
    stops = "".join(f'<stop offset="{i / (len(p["sky"]) - 1):.2f}" stop-color="{c}"/>' for i, c in enumerate(p["sky"]))
    a(f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">{stops}</linearGradient>')
    a(f'<linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">'
      f'<stop offset="0" stop-color="{p["sea"][0]}"/><stop offset=".5" stop-color="{p["sea"][1]}"/>'
      f'<stop offset="1" stop-color="{p["sea"][2]}"/></linearGradient>')
    a(f'<radialGradient id="glow"><stop offset="0" stop-color="{p["glow"]}" stop-opacity=".85"/>'
      f'<stop offset="1" stop-color="{p["glow"]}" stop-opacity="0"/></radialGradient>')
    a(f'<linearGradient id="glint" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["glint"]}" stop-opacity=".75"/>'
      f'<stop offset="1" stop-color="{p["glint"]}" stop-opacity="0"/></linearGradient>')
    a(f'<radialGradient id="glintR" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{p["glint"]}" stop-opacity=".45"/>'
      f'<stop offset="1" stop-color="{p["glint"]}" stop-opacity="0"/></radialGradient>')
    a(f'<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["floor"][0]}"/>'
      f'<stop offset="1" stop-color="{p["floor"][1]}"/></linearGradient>')
    a(f'<linearGradient id="table" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["table"][0]}"/>'
      f'<stop offset="1" stop-color="{p["table"][1]}"/></linearGradient>')
    a(f'<linearGradient id="spill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["wall_light"]}" stop-opacity=".28"/>'
      f'<stop offset="1" stop-color="{p["wall_light"]}" stop-opacity="0"/></linearGradient>')
    a(f'<radialGradient id="lamp"><stop offset="0" stop-color="{p["lamp"]}" stop-opacity="{p["lamp_glow"]}"/>'
      f'<stop offset="1" stop-color="{p["lamp"]}" stop-opacity="0"/></radialGradient>')
    a(f'<linearGradient id="trail" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="{p["trail"]}" stop-opacity=".8"/>'
      f'<stop offset="1" stop-color="{p["trail"]}" stop-opacity="0"/></linearGradient>')
    a("</defs>")

    # --- sky, stars, sun/moon
    a(f'<rect width="{W}" height="{HORIZON + 2}" fill="url(#sky)"/>')
    if p["stars"]:
        for _ in range(90):
            x, y, r = rnd.uniform(0, W), rnd.uniform(0, HORIZON - 80), rnd.uniform(.6, 1.8)
            dur, beg = rnd.uniform(2.5, 6), rnd.uniform(0, 5)
            a(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#fff" opacity=".8">'
              f'<animate attributeName="opacity" values=".9;.25;.9" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/></circle>')
    sx, sy = 1130, 330 if mode == "day" else 210
    a(f'<circle cx="{sx}" cy="{sy}" r="190" fill="url(#glow)"/>')
    if mode == "night":   # crescent: the moon disc with an offset disc masked out
        a(f'<mask id="crescent"><rect width="{W}" height="{H}" fill="#fff"/>'
          f'<circle cx="{sx + 16}" cy="{sy - 10}" r="36" fill="#000"/></mask>')
        a(f'<circle cx="{sx}" cy="{sy}" r="40" fill="{p["sun"]}" mask="url(#crescent)"/>')
    else:
        a(f'<circle cx="{sx}" cy="{sy}" r="54" fill="{p["sun"]}"/>')

    # --- clouds (drift)
    for i, (cx, cy, s, dur) in enumerate([(200, 170, 1.2, 140), (760, 110, .9, 180), (1380, 230, 1.1, 160), (520, 300, .7, 120)]):
        blobs = "".join(f'<ellipse cx="{dx * s:.0f}" cy="{dy * s:.0f}" rx="{rx * s:.0f}" ry="{ry * s:.0f}"/>'
                        for dx, dy, rx, ry in [(0, 0, 90, 28), (-55, 8, 60, 22), (60, 6, 70, 24), (10, -18, 55, 26)])
        a(f'<g fill="{p["cloud"]}" opacity="{p["cloud_op"]}" transform="translate({cx} {cy})"><g>{blobs}'
          f'<animateTransform attributeName="transform" type="translate" values="0 0;{120 + i * 30} 0;0 0" '
          f'dur="{dur}s" repeatCount="indefinite"/></g></g>')

    # --- plane with contrail, crossing the window every 26s
    plane = (f'<path d="M0 0 L-46 -3 L-60 -16 L-66 -16 L-58 -2 L-80 0 L-58 2 L-66 16 L-60 16 L-46 3 Z" fill="{p["plane"]}"/>'
             f'<path d="M-30 -1 L-12 -24 L-4 -24 L-14 -1 Z M-30 1 L-12 24 L-4 24 L-14 1 Z" fill="{p["plane_shadow"]}"/>'
             f'<rect x="-460" y="-2" width="390" height="4" rx="2" fill="url(#trail)"/>')
    if mode == "night":
        plane += ('<circle cx="-14" cy="-23" r="2.4" fill="#ff4d4d"><animate attributeName="opacity" values="1;0;1" dur="1.2s" repeatCount="indefinite"/></circle>'
                  '<circle cx="-14" cy="23" r="2.4" fill="#4dff88"><animate attributeName="opacity" values="1;0;1" dur="1.2s" repeatCount="indefinite"/></circle>')
    a(f'<g><g transform="rotate(-6) scale(.9)">{plane}</g>'
      f'<animateTransform attributeName="transform" type="translate" values="-300 300;1900 140" dur="26s" repeatCount="indefinite"/></g>')

    # --- islands, city lights, sea, glint, boats
    a(f'<path d="M0 {HORIZON} L0 520 Q120 470 260 505 Q360 455 470 498 Q560 480 640 {HORIZON} Z" fill="{p["far"]}"/>')
    a(f'<path d="M980 {HORIZON} Q1080 500 1210 520 Q1300 470 1420 512 Q1520 490 1600 520 L1600 {HORIZON} Z" fill="{p["near"]}"/>')
    if p["city"]:
        for _ in range(55):
            x = rnd.choice([rnd.uniform(20, 620), rnd.uniform(1000, 1590)])
            y = rnd.uniform(HORIZON - 22, HORIZON - 3)
            a(f'<rect x="{x:.0f}" y="{y:.0f}" width="2.2" height="2.2" fill="#ffd27a" opacity=".85">'
              f'<animate attributeName="opacity" values=".9;.4;.9" dur="{rnd.uniform(2, 5):.1f}s" repeatCount="indefinite"/></rect>')
    a(f'<rect y="{HORIZON}" width="{W}" height="{SILL - HORIZON + 40}" fill="url(#sea)"/>')
    a(f'<clipPath id="water"><rect y="{HORIZON}" width="{W}" height="{SILL - HORIZON}"/></clipPath>')
    a(f'<ellipse cx="{sx}" cy="{HORIZON}" rx="64" ry="{SILL - HORIZON}" fill="url(#glintR)" clip-path="url(#water)"/>')
    for i in range(16):
        y = HORIZON + 8 + i * 9
        w = rnd.uniform(30, 120)
        x = sx - w / 2 + rnd.uniform(-40, 40)
        a(f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="2" rx="1" fill="{p["glint"]}" opacity=".7">'
          f'<animate attributeName="opacity" values=".8;.15;.8" dur="{rnd.uniform(1.5, 3.5):.1f}s" begin="{rnd.uniform(0, 2):.1f}s" repeatCount="indefinite"/></rect>')
    for bx, by, s, dur in [(380, 600, 1, 9), (1420, 585, .7, 11)]:
        a(f'<g transform="translate({bx} {by}) scale({s})"><g>'
          f'<path d="M-30 0 L30 0 L22 9 L-22 9 Z" fill="{p["chair"]}"/>'
          f'<path d="M2 -2 L2 -58 L30 -4 Z" fill="{p["boat"]}"/><path d="M-2 -4 L-2 -44 L-24 -4 Z" fill="{p["boat"]}" opacity=".85"/>'
          f'<animateTransform attributeName="transform" type="translate" values="0 0;0 -3;0 0" dur="{dur / 3:.1f}s" repeatCount="indefinite"/>'
          f'</g></g>')

    # --- interior: window frame, ceiling + pendant lights
    a(f'<rect y="{SILL}" width="{W}" height="{H - SILL}" fill="url(#floor)"/>')
    for x in range(0, W + 1, 400):
        a(f'<rect x="{x - 11}" y="0" width="22" height="{SILL + 6}" fill="{p["frame"]}"/>')
    a(f'<rect y="{SILL - 6}" width="{W}" height="18" fill="{p["frame"]}"/>')
    a(f'<rect y="0" width="{W}" height="64" fill="{p["ceiling"]}"/><rect y="64" width="{W}" height="10" fill="{p["frame"]}"/>')
    for lx in (600, 1000):
        a(f'<line x1="{lx}" y1="74" x2="{lx}" y2="150" stroke="{p["frame"]}" stroke-width="2"/>')
        a(f'<circle cx="{lx}" cy="190" r="120" fill="url(#lamp)"/>')
        a(f'<path d="M{lx - 34} 172 Q{lx} 136 {lx + 34} 172 Z" fill="{p["frame"]}"/>')
        a(f'<ellipse cx="{lx}" cy="173" rx="30" ry="4" fill="{p["lamp"]}"/>')

    # --- conference table and chairs
    for cx in range(520, 1100, 112):                       # far-side chairs (backs visible)
        a(f'<rect x="{cx - 34}" y="742" width="68" height="74" rx="18" fill="{p["chair"]}"/>')
    a(f'<polygon points="420,806 1180,806 1330,1000 270,1000" fill="url(#table)"/>')
    a(f'<polygon points="420,806 1180,806 1186,816 414,816" fill="{p["table_edge"]}"/>')
    for x, y, w, h in [(520, 850, 70, 44), (760, 862, 84, 50), (1010, 850, 70, 44), (640, 930, 90, 54)]:
        a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#ffffff" opacity="{.42 if mode == "day" else .16}"/>')
        a(f'<rect x="{x + 6}" y="{y + 6}" width="{w - 12}" height="{h - 12}" rx="2" fill="{p["chair"]}" opacity=".35"/>')
    for x, flip in [(300, 1), (1300, -1)]:                  # side chairs
        a(f'<rect x="{x - 40}" y="820" width="80" height="140" rx="22" fill="{p["chair"]}" transform="skewX({8 * flip})"/>')

    # --- plant in the corner
    a(f'<rect x="88" y="880" width="80" height="90" rx="10" fill="{p["chair"]}"/>')
    for ang, ln in [(-40, 140), (-15, 170), (10, 160), (35, 130), (-60, 110), (55, 105)]:
        a(f'<ellipse cx="128" cy="{880 - ln / 2}" rx="16" ry="{ln / 2}" fill="#3f7d4f" '
          f'opacity="{.95 if mode == "day" else .6}" transform="rotate({ang} 128 880)"/>')

    if p["interior_shade"]:
        a(f'<rect y="{SILL}" width="{W}" height="{H - SILL}" fill="#000" opacity="{p["interior_shade"]}"/>')
    a("</svg>")
    return "".join(o)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for mode in PALETTES:
        path = OUT / f"scene-{mode}.svg"
        path.write_text(svg(mode), encoding="utf-8")
        print(f"{path.name}: {path.stat().st_size // 1024} KB")
