#!/usr/bin/env python3
"""Download each organisation's own site icon (apple-touch-icon / SVG / PNG favicon) into assets/logos/.
Logos are used only as source identifiers. Run manually; results are committed. Writes assets/logos/manifest.json."""
import io, json, os, re, sys, urllib.parse, requests
from bs4 import BeautifulSoup
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "logos"); os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
ORGS = {  # key: (display name, official homepage)
 "ocimf": ("OCIMF", "https://www.ocimf.org/"), "cdi": ("CDI", "https://www.cdim.org/"), "rightship": ("RightShip", "https://rightship.com/"),
 "parismou": ("Paris MoU", "https://parismou.org/"), "tokyomou": ("Tokyo MOU", "https://www.tokyo-mou.org/"), "bp": ("bp", "https://www.bp.com/"),
 "adnoc": ("ADNOC", "https://www.adnoc.ae/"), "repsol": ("Repsol", "https://www.repsol.com/"), "moeve": ("Moeve", "https://www.moeveglobal.com/"),
 "braskem": ("Braskem", "https://www.braskem.com/"), "exxonmobil": ("ExxonMobil", "https://corporate.exxonmobil.com/"),
 "totalenergies": ("TotalEnergies", "https://totalenergies.com/"), "transmountain": ("Trans Mountain", "https://www.transmountain.com/"),
 "fujairah": ("Port of Fujairah", "https://fujairahport.ae/"), "intertanko": ("INTERTANKO", "https://www.intertanko.com/"), "imo": ("IMO", "https://www.imo.org/"),
 "uscg": ("USCG", "https://www.uscg.mil/"), "medmou": ("Med MoU", "https://www.medmou.org/"), "iomou": ("IOMOU", "https://www.iomou.org/"),
 "equasis": ("Equasis", "https://www.equasis.org/"), "aramco": ("Saudi Aramco", "https://www.aramco.com/"), "sigtto": ("SIGTTO", "https://www.sigtto.org/"),
 "amsa": ("AMSA", "https://www.amsa.gov.au/"), "emsa": ("EMSA", "https://www.emsa.europa.eu/"),
 "omv": ("OMV", "https://www.omv.com/"), "saras": ("SARAS", "https://www.saras.it/"), "marathon": ("Marathon Petroleum", "https://www.marathonpetroleum.com/"),
 "siot": ("SIOT / TAL", "https://www.tal-oil.com/"), "toros": ("Toros Terminal", "https://www.torosterminal.com.tr/"), "moh": ("Motor Oil Hellas", "https://www.moh.gr/"),
 "preem": ("Preem", "https://www.preem.se/"), "enbridge": ("Enbridge", "https://www.enbridge.com/"), "tupras": ("Tüpraş", "https://www.tupras.com.tr/"),
}
def score(link):
    rel = " ".join(link.get("rel", [])).lower(); href = link.get("href", ""); sizes = link.get("sizes", "")
    m = re.search(r"(\d+)x\d+", sizes or ""); sz = int(m.group(1)) if m else 0
    if href.lower().endswith(".svg") or "svg" in (link.get("type") or ""): return 1000
    if "apple-touch-icon" in rel: return 500 + sz
    if "icon" in rel: return sz or 16
    return -1
def candidates(home):
    out = []
    try:
        r = requests.get(home, headers=UA, timeout=25); r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        links = [l for l in soup.find_all("link", href=True) if score(l) >= 0]
        out = [urllib.parse.urljoin(r.url, l["href"]) for l in sorted(links, key=score, reverse=True)]
        base = r.url
    except Exception as e:
        print("  home failed:", type(e).__name__, str(e)[:80]); base = home
    out += [urllib.parse.urljoin(base, "/apple-touch-icon.png"), urllib.parse.urljoin(base, "/favicon.ico")]
    return out
FORCE_FALLBACK = {"cdi", "uscg", "transmountain", "saras", "marathon", "tupras"}  # only 16px or blocked: use neutral initials badge
manifest = {}
only = sys.argv[1:]
for key, (name, home) in ORGS.items():
    if (only and key not in only) or key in FORCE_FALLBACK: continue
    print(key, home); got = None
    for u in candidates(home):
        try:
            r = requests.get(u, headers=UA, timeout=25)
            if r.status_code != 200 or len(r.content) < 100: continue
            data = r.content; ct = r.headers.get("content-type", "")
            if data.lstrip()[:5] in (b"<?xml", b"<svg ") or "svg" in ct:
                if b"<svg" not in data[:2000]: continue
                p = os.path.join(OUT, key + ".svg"); open(p, "wb").write(data); got = (u, key + ".svg", "svg"); break
            im = Image.open(io.BytesIO(data))
            if getattr(im, "n_frames", 1) > 1 or im.format == "ICO":
                sizes = sorted(im.info.get("sizes", [im.size]), key=lambda s: s[0])
                if im.format == "ICO": im.size = sizes[-1]; im.load()
            im = im.convert("RGBA")
            if im.width < 16: continue
            im.thumbnail((128, 128), Image.LANCZOS)
            p = os.path.join(OUT, key + ".png"); im.save(p); got = (u, key + ".png", f"png {im.width}x{im.height}"); break
        except Exception as e:
            continue
    if got:
        for ext in ("svg", "png"):  # remove stale other-format file
            q = os.path.join(OUT, f"{key}.{ext}")
            if ext not in got[1] and os.path.exists(q): os.remove(q)
        manifest[key] = {"name": name, "file": got[1], "source_url": got[0], "kind": got[2], "homepage": home}
        print("  ->", got[2], got[0])
    else:
        manifest[key] = {"name": name, "file": None, "homepage": home}; print("  -> none (fallback initials)")
old = json.load(open(os.path.join(OUT, "manifest.json"))) if os.path.exists(os.path.join(OUT, "manifest.json")) else {}
old.update(manifest); json.dump(old, open(os.path.join(OUT, "manifest.json"), "w"), indent=2)

# ---- second pass: header-logo overrides (official site assets) where the site icon is tiny or missing ----
OVERRIDES = {
 "exxonmobil": "https://www.exxonmobil.com/favicon.ico",
 "fujairah": "https://fujairahport.ae/wp-content/uploads/2026/08/LogoBlue-Transperent.png",
 "braskem": "https://www.braskem.com/portal/Principal/2022/img/braskem.webp",
 "totalenergies": "https://totalenergies.com/themes/custom/totalenergies_com/dist/img/logo_totalenergies.png",
 "amsa": "https://www.amsa.gov.au/themes/custom/amsad10/logo.svg",
 "adnoc": "https://www.adnoc.ae/-/media/adnoc-v2/images/logo/adnoc-logo-updated.ashx?la=en&hash=7E6BA2973EF7B0D87F130C52C8D2FD97",
 "rightship": "https://rightship.com/hubfs/logo.svg",
 "omv": "https://www.omv.com/assets/img/logos/omv-logo-blue.svg",
  "iomou": "https://www.iomou.org/HOMEPAGE/images/home4/logo.png",
 "intertanko": "https://www.intertanko.com/templates/intertanko-template/images/intertanko_logo_01.svg", "medmou": "https://www.medmou.org/images/loogoo.png", "sigtto": "https://www.sigtto.org/favicon.ico",
}
def save_any(key, u):
    r = requests.get(u, headers=UA, timeout=30); r.raise_for_status(); data = r.content
    if b"<svg" in data[:3000]:
        open(os.path.join(OUT, key + ".svg"), "wb").write(data); return key + ".svg", "svg"
    im = Image.open(io.BytesIO(data))
    if im.format == "ICO":
        big = max(im.ico.sizes()); im = im.ico.getimage(big)
    im = im.convert("RGBA"); bbox = im.getbbox()
    if bbox: im = im.crop(bbox)  # trim transparent margins of wordmarks
    im.thumbnail((400, 96), Image.LANCZOS)
    im.save(os.path.join(OUT, key + ".png")); return key + ".png", f"png {im.width}x{im.height}"
if __name__ == "__main__" and (not only or "--overrides" in only):
    man = json.load(open(os.path.join(OUT, "manifest.json")))
    for key, u in OVERRIDES.items():
        try:
            f, kind = save_any(key, u)
            for ext in ("svg", "png"):
                q = os.path.join(OUT, f"{key}.{ext}")
                if not f.endswith(ext) and os.path.exists(q): os.remove(q)
            man[key].update(file=f, source_url=u, kind=kind); print("override", key, kind)
        except Exception as e:
            print("override failed", key, type(e).__name__, str(e)[:80])
    json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=2)
