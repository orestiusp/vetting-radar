#!/usr/bin/env python3
"""Brand assets for Vetting Radar (logo option 1, 'Sweep & Blip'): icon SVGs, favicons, apple-touch-icon, og:image.
Writes to site/brand/. PNGs are rendered with headless Chrome + Pillow (run locally; outputs are committed)."""
import os, subprocess, tempfile, io
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site", "brand"); os.makedirs(OUT, exist_ok=True)
NAVY, NAVY2, TEAL, TEAL_L, WHITE = "#0b1a2c", "#12304f", "#0b6e8f", "#5fd3f3", "#ffffff"

def icon(uid, ring=TEAL_L, ink=WHITE, small=False):
    """64x64 radar-sweep icon with a tanker blip. small=True: simplified for 16-32 px."""
    rings = "" if small else f'''<circle cx="32" cy="32" r="18" fill="none" stroke="{ring}" stroke-width="1.6" opacity=".4"/>
<circle cx="32" cy="32" r="9" fill="none" stroke="{ring}" stroke-width="1.6" opacity=".4"/>'''
    halo = "" if small else f'<circle class="vr-blip" cx="41.5" cy="15" r="11" fill="{ring}" opacity=".12"/>'
    ship = (f'<g fill="{ink}"><path d="M30.5 16 H52 L48 23 H32.6 Z"/><rect x="31.6" y="9.6" width="7" height="7.4" rx=".8"/></g>' if small else
            f'<g fill="{ink}"><path d="M31.5 15.8 H51 L47.4 21.4 H33.4 Z"/><path d="M46.4 15.8 V13.9 H50.4 V15.8 Z"/><rect x="32.4" y="10" width="5.6" height="6.2" rx=".7"/><rect x="34" y="7.3" width="2.4" height="3.2" rx=".4"/></g>')
    return f'''<defs><linearGradient id="sw{uid}" x1="32" y1="32" x2="50" y2="8" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{ring}" stop-opacity="0"/><stop offset="1" stop-color="{ring}" stop-opacity="{'.6' if small else '.45'}"/></linearGradient></defs>
<circle cx="32" cy="32" r="28" fill="none" stroke="{ring}" stroke-width="{4.6 if small else 3}"/>{rings}
<g class="vr-sweep"><path d="M32 32 L32 4 A28 28 0 0 1 56.25 18 Z" fill="url(#sw{uid})"/>
<path d="M32 32 L56.25 18" stroke="{ring}" stroke-width="{3.6 if small else 2.6}" stroke-linecap="round"/></g>{halo}{ship}
<circle cx="32" cy="32" r="{3.4 if small else 2.6}" fill="{ring}"/>'''

def svg(inner, vb="0 0 64 64", w=64, h=64): return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{w}" height="{h}">{inner}</svg>'
def tile(uid, small):  # icon on a navy rounded tile (favicons / touch icon)
    pad = 4 if small else 8
    return svg(f'<rect width="64" height="64" rx="{14 if small else 12}" fill="{NAVY}"/><g transform="translate({pad} {pad}) scale({(64-2*pad)/64})">{icon(uid, small=small)}</g>')

files = {
 "icon-on-navy.svg": svg(icon("a")),
 "icon-on-white.svg": svg(icon("b", ring=TEAL, ink=NAVY)),
 "favicon.svg": tile("f", small=True),
}
for k, v in files.items(): open(os.path.join(OUT, k), "w").write(v)

def chrome_png(html, w, h, path, transparent=True):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f: f.write(html); src = f.name
    args = ["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tempfile.mkdtemp()}",
            f"--window-size={w},{h}", f"--screenshot={path}"] + (["--default-background-color=00000000"] if transparent else []) + ["file://" + src]
    subprocess.run(args, capture_output=True, timeout=60); os.unlink(src)

from PIL import Image
big = os.path.join(tempfile.mkdtemp(), "big.png")
for name, small, size in (("favicon-16.png", True, 16), ("favicon-32.png", True, 32), ("apple-touch-icon.png", False, 180)):
    chrome_png(f'<html><body style="margin:0;background:transparent">{tile("p", small).replace("width=\"64\" height=\"64\"", "width=\"512\" height=\"512\"", 1)}</body></html>', 512, 512, big)
    im = Image.open(big).convert("RGBA").crop((0, 0, 512, 512))
    if name == "apple-touch-icon.png":  # iOS applies its own mask: full-bleed navy, no transparency
        bg = Image.new("RGBA", im.size, NAVY); bg.alpha_composite(im); im = bg
    im.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, name))
Image.open(os.path.join(OUT, "favicon-32.png")).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32)])

# og:image 1200x630
og = f'''<html><head><style>
body{{margin:0;width:1200px;height:630px;overflow:hidden;font-family:Inter,sans-serif;background:radial-gradient(900px 420px at 88% -10%,rgba(95,211,243,.22),transparent 60%),linear-gradient(160deg,{NAVY},{NAVY2});color:#fff;position:relative}}
.bg{{position:absolute;right:-110px;top:52%;transform:translateY(-50%);opacity:.2}}
.c{{position:absolute;left:84px;top:78px;right:420px}}
.brand{{display:flex;align-items:center;gap:20px;font-size:40px;font-weight:700;letter-spacing:-.01em}}.brand b{{color:{TEAL_L};font-weight:700}}
.eb{{margin-top:70px;font-size:20px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:{TEAL_L}}}
h1{{margin:16px 0 0;font-size:66px;line-height:1.06;letter-spacing:-.025em;font-weight:800}}
.f{{position:absolute;left:84px;bottom:56px;font-size:22px;color:#9fb6c8}}.f span{{color:#fff;font-weight:600}}
.bar{{position:absolute;left:0;right:0;bottom:0;height:8px;background:linear-gradient(90deg,{TEAL},{TEAL_L})}}
</style></head><body>
<div class="bg">{svg(icon("o1"), w=620, h=620)}</div>
<div class="c"><div class="brand">{svg(icon("o2"), w=72, h=72)}<span>Vetting <b>Radar</b></span></div>
<div class="eb">Tanker vetting intelligence</div><h1>Know what changed before your next screening.</h1></div>
<div class="f"><span>vettingradar.com</span> · OCIMF · CDI · RightShip · oil-major &amp; terminal criteria, watched daily</div><div class="bar"></div></body></html>'''
chrome_png(og, 1200, 630, os.path.join(OUT, "og-image.png"), transparent=False)
print("brand assets:", sorted(os.listdir(OUT)))
