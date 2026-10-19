#!/usr/bin/env python3
"""Build the static Vetting Radar site into dist/ from data/*.json, sources.json and newsletter/*.md."""
import json, os, shutil, html, datetime as dt, re, glob, hashlib, base64, sys
import markdown
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lessons as LS
import sire_lessons as SL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
DIST = P("dist")
e = lambda s: html.escape(str(s if s is not None else ""))
load = lambda p, d=None: json.load(open(p)) if os.path.exists(p) else d

sources = load(P("sources.json"))["sources"]
state = load(P("data", "state.json"), {})
changes = load(P("data", "changes.json"), [])
updates = load(P("data", "updates.json"), [])
calendar = load(P("data", "calendar.json"), [])
comp = load(P("data", "comparison.json"))
runlog = load(P("data", "run_log.json"), {})
TODAY = dt.date.today()
# --preview (or VR_PREVIEW=1): local review build. Also renders unreviewed safety lessons, each with a "Draft – awaiting review" badge.
# Never deploy a preview build: the workflow runs plain `build.py`, which publishes only lessons with reviewed=true and publish=true.
PREVIEW = "--preview" in sys.argv or os.environ.get("VR_PREVIEW") == "1"
LESSONS_ALL, LESSONS = LS.load(P("data", "lessons.json"), PREVIEW)
PSC_REF = load(P("data", "psc_codes.json"), {}).get("codes", {})
for _w in LS.check(LESSONS_ALL, set(PSC_REF)): print("lessons check:", _w)
LOTW = LS.lesson_of_week(LESSONS, TODAY)
# SIRE 2.0 lessons (data/sire_lessons.json): one SIRE 2.0 observation a week, shown beside the incident lesson of the week
SIRE_ALL, SIRE_VIS = SL.load(P("data", "sire_lessons.json"), PREVIEW)
for _w in SL.check(SIRE_ALL, set(PSC_REF)): print("SIRE lessons check:", _w)
SIRE_LOTW = SL.of_week(SIRE_VIS, TODAY) if LOTW else None
CHROME = next((c for c in (os.environ.get("VR_CHROME"), shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")) if c), None)
CAT = {"sire":"SIRE / OCIMF","tmsa":"TMSA","cdi":"CDI","vetting-criteria":"Vetting schemes","oil-major":"Oil majors","terminal":"Terminals & ports",
       "psc":"Port State Control","industry":"Industry bodies","news":"OCIMF news","regulation":"IMO"}
NAV = [("updates.html","Updates"),("table.html","Vetting Rules"),("calendar.html","Calendar")] + ([("lessons.html","Safety lessons")] if LESSONS else []) + [("newsletter.html","Newsletter")]
GROUP = {"sire":"scheme","cdi":"scheme","tmsa":"scheme","vetting-criteria":"scheme","oil-major":"major","terminal":"terminal","psc":"psc"}
GROUP_LABEL = {"scheme":"Inspection scheme","major":"Oil major","terminal":"Terminal","psc":"Port State Control"}
IMPACT_LABEL = {"high":"High impact","medium":"Medium impact","low":"Low impact"}

# inline SVG icons (stroke style)
_IC = {
 "bell":'<path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
 "columns":'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16M3 10h18"/>',
 "calendar":'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
 "arrow":'<path d="M5 12h14M13 6l6 6-6 6"/>',
 "radar":'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12 19 5"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/>',
 "link":'<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
 "shield":'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
 "check":'<path d="M20 6 9 17l-5-5"/>',
 "mail":'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
 "todo":'<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
 "pulse":'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
 "pin":'<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
 "chat":'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.6A8 8 0 1 1 21 12z"/><path d="M8.5 10.5h7M8.5 13.5h4.5"/>',
 "alert":'<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
 "menu":'<path d="M4 6h16M4 12h16M4 18h16"/>',
 "crew":'<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.6"/><path d="M15.5 14.2A5 5 0 0 1 21 19"/>',
}
def icon(n, cls="ico"): return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{_IC[n]}</svg>'
# Header/footer logo (icon). To swap: replace with the chosen concept's icon SVG (viewBox 0 0 64 64 works too); size is set in CSS (.brand svg).
_LOGO_SVG = open(P("site", "brand", "icon-on-navy.svg")).read().replace('width="64" height="64"', 'aria-hidden="true" focusable="false"')
def logo(uid):  # inline option-1 icon; unique gradient id per use (header + footer on one page)
    return _LOGO_SVG.replace("swa", f"sw{uid}")

def fmt_date(s):
    if not s: return ""
    try:
        if len(s) == 7: return dt.datetime.strptime(s, "%Y-%m").strftime("%b %Y")
        d = dt.date.fromisoformat(s[:10]); return f"{d.day} {d.strftime('%b %Y')}"
    except Exception: return s

CMP_TABS = [("table.html", "Requirements table", "columns"), ("compare-checklist.html", "Pre-screening checklist", "todo"),
            ("compare-frequency.html", "Inspection frequency", "calendar"), ("compare-terminals.html", "Terminals", "pin"), ("compare-crew.html", "Crew matrix", "crew"), ("reports.html", "Reader reports", "chat")]
# GoatCounter visitor stats (cookie-free); left off admin.html and the newsletter email copies
# Versioned script + SRI (https://www.goatcounter.com/help/countjs-versions): the browser refuses it if it ever changes.
GOATCOUNTER = ('<script data-goatcounter="https://vettingradar.goatcounter.com/count" async src="https://gc.zgo.at/count.v5.js" crossorigin="anonymous" '
               'integrity="sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ"></script>')
BH_ATTRIBUTION = '<script type="text/javascript" async src="https://subscribe-forms.beehiiv.com/attribution.js"></script>'
# ---------- security headers as <meta> (GitHub Pages cannot send headers) ----------
# Inline <script> blocks are allowed by hash (computed per page in page()), so no 'unsafe-inline' for scripts.
# Not possible in <meta>: frame-ancestors, report-uri, HSTS. admin/submit get a JS frame-buster instead of frame-ancestors.
SUPABASE_ORIGIN = "https://kfxroqikspadmpjqiwkl.supabase.co"
CSP = {
    # public pages: own files, Supabase, Beehiiv embed, GoatCounter, Turnstile (planned)
    "site": {"default-src": "'self'",
             "script-src": f"'self' https://cdn.jsdelivr.net https://subscribe-forms.beehiiv.com https://gc.zgo.at https://challenges.cloudflare.com",
             "style-src": "'self' 'unsafe-inline' https://subscribe-forms.beehiiv.com https://fonts.googleapis.com",
             "font-src": "'self' https://fonts.gstatic.com",
             "img-src": "'self' data: https:",
             "connect-src": f"'self' {SUPABASE_ORIGIN} https://vettingradar.goatcounter.com https://subscribe-forms.beehiiv.com",
             "frame-src": "https://subscribe-forms.beehiiv.com https://embeds.beehiiv.com https://challenges.cloudflare.com",
             "form-action": "'self' https://*.beehiiv.com", "base-uri": "'self'", "object-src": "'none'", "upgrade-insecure-requests": ""},
    # pages holding a Supabase session (admin.html, submit.html): no third-party script except SRI-pinned supabase-js / GoatCounter, and Turnstile
    "session": {"default-src": "'none'",
                "script-src": "'self' https://cdn.jsdelivr.net https://challenges.cloudflare.com https://gc.zgo.at",
                "style-src": "'self' 'unsafe-inline'", "img-src": "'self' data: https://vettingradar.goatcounter.com",
                "connect-src": f"{SUPABASE_ORIGIN} https://vettingradar.goatcounter.com", "frame-src": "https://challenges.cloudflare.com",
                "form-action": "'self'", "base-uri": "'none'", "object-src": "'none'", "upgrade-insecure-requests": ""},
}
FRAMEBUST = "<script>if(window.top!==window.self){document.documentElement.style.display='none';window.top.location=window.self.location.href;}</script>"
def _security_meta(doc, kind):
    hashes = " ".join("'sha256-%s'" % base64.b64encode(hashlib.sha256(m.encode()).digest()).decode()
                      for m in re.findall(r"<script>(.*?)</script>", doc, re.S))
    pol = dict(CSP[kind]); pol["script-src"] += (" " + hashes if hashes else "")
    if kind == "session": pol["script-src"] += " " + "'sha256-%s'" % base64.b64encode(hashlib.sha256(FRAMEBUST[8:-9].encode()).digest()).decode()
    csp = "; ".join((k + " " + v).strip() for k, v in pol.items())
    ref = "same-origin" if kind == "session" else "strict-origin-when-cross-origin"
    return f'<meta http-equiv="Content-Security-Policy" content="{csp}"><meta name="referrer" content="{ref}">' + (FRAMEBUST if kind == "session" else "")
# Contact address (footer on every page + About). Light anti-scraper measure without JS: the address is written as HTML character
# references in both the mailto: href and the text, so it shows and works normally in browsers but is not a plain-text match in the source.
CONTACT_EMAIL = "admin@vettingradar.com"
_CONTACT_ENC = "".join(f"&#{ord(c)};" for c in CONTACT_EMAIL)
CONTACT_LINK = f'<a href="&#109;&#97;&#105;&#108;&#116;&#111;&#58;{_CONTACT_ENC}">{_CONTACT_ENC}</a>'
def page(fname, title, body, desc="Vetting Radar tracks public tanker vetting rules (SIRE 2.0/OCIMF, CDI, RightShip, oil-major and terminal criteria) daily and shows what changed, with the source.", depth=0, full_title=None, section=None, head="", scripts="", stats=True, csp="site", cta="Subscribe"):
    pre = "../" * depth
    doc_title = full_title or f"{title} · Vetting Radar"
    base = os.path.basename(fname)
    def _nav(h, l):
        cls = " ".join(c for c in ("rrnav" if h == "reports.html" else "", "on" if h in (base, section) else "") if c)
        return f'<a href="{pre}{h}"{f" class=\"{cls}\"" if cls else ""}{" aria-current=\"page\"" if h == base else ""}>{l}</a>'
    nav = "".join(_nav(h, l) for h, l in NAV)
    cmp_links = "".join(f'<li><a href="{pre}{h}">{l}</a></li>' for h, l, _i in CMP_TABS)
    sub_href = f"{pre}index.html#subscribe"
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(doc_title)}</title><meta name="description" content="{e(desc)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="Vetting Radar"><meta property="og:title" content="{e(doc_title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{SITE_URL}/brand/og-image.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Vetting Radar: Know what changed before your next screening.">
<meta property="og:url" content="{SITE_URL}/{'' if fname=='index.html' else fname}">
<link rel="icon" href="{pre}brand/favicon.svg" type="image/svg+xml"><link rel="icon" href="{pre}brand/favicon-32.png" sizes="32x32" type="image/png"><link rel="icon" href="{pre}brand/favicon-16.png" sizes="16x16" type="image/png">
<link rel="apple-touch-icon" href="{pre}brand/apple-touch-icon.png">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{SITE_URL}/brand/og-image.png"><meta name="twitter:title" content="{e(doc_title)}"><meta name="twitter:description" content="{e(desc)}"><meta name="theme-color" content="#0b1a2c"><link rel="stylesheet" href="{pre}style.css">
<link rel="alternate" type="application/json" href="{pre}data/updates.json" title="Vetting Radar reviewed updates (JSON)">{head}{'<meta name="robots" content="noindex,nofollow">' if PREVIEW else ''}
<script>document.documentElement.classList.add("js")</script>
{BH_ATTRIBUTION if csp == "site" else ""}</head><body>
<a class="skip" href="#content">Skip to content</a>
{'<div class="previewbar">Preview build · not live · draft safety lessons awaiting review</div>' if PREVIEW else ''}<header class="site"><div class="wrap"><a class="brand" href="{pre}index.html" aria-label="Vetting Radar home">{logo("h")}<span>Vetting <span class="r">Radar</span></span></a>
<nav class="main" id="mnav" aria-label="Main">{nav}</nav><a class="btn sm" href="{sub_href}">{cta}</a>
<button class="navtoggle" type="button" aria-expanded="false" aria-controls="mnav" aria-label="Menu"><span></span><span></span><span></span></button></div></header>
<main id="content">{body}</main>
<footer class="site"><div class="wrap"><div class="cols">
<div><a class="brand" href="{pre}index.html">{logo("f")}<span>Vetting <span class="r">Radar</span></span></a><p class="fdisc">Independent tracker of public tanker vetting rules. Not affiliated with OCIMF, CDI, RightShip, any oil major, terminal or employer. Summaries of public documents, not legal text: <b>always verify at the linked source.</b></p><p class="tm">Logos are trademarks of their respective owners, used only to identify the source.</p></div>
<div><h4>Product</h4><ul><li><a href="{pre}updates.html">Updates</a></li><li><a href="{pre}calendar.html">Calendar</a></li>{f'<li><a href="{pre}lessons.html">Safety lessons</a></li>' if LESSONS else ''}<li><a href="{pre}newsletter.html">Newsletter</a></li><li><a href="{pre}sources.html">Sources</a></li></ul></div>
<div><h4>Vetting Rules</h4><ul>{cmp_links}</ul></div>
<div><h4>About</h4><ul><li><a href="{pre}about.html">About &amp; disclaimer</a></li>{f'<li><a href="{pre}lessons-policy.html">How we write safety lessons</a></li>' if LESSONS else ''}<li><a href="{pre}sponsor.html">Sponsor</a></li><li><a href="{pre}data/comparison.csv">Data (CSV)</a></li><li><a href="{pre}data/updates.json">Updates (JSON)</a></li></ul></div>
</div><div class="fine"><span class="fl"><span class="fi">© {TODAY.year} Vetting Radar</span> · <span class="fi">{CONTACT_LINK}</span> · <span class="fi">Public sources only</span></span><span>Last built {fmt_date(TODAY.isoformat())}</span></div></div></footer>
<script src="{pre}app.js"></script>{scripts}{GOATCOUNTER if stats else ""}</body></html>"""
    doc = doc.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + _security_meta(doc, csp), 1)  # CSP first, before any script
    path = os.path.join(DIST, fname); os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(doc)

# ---------- organisation logos (source identifiers only) ----------
ORG_LOGOS = load(P("assets", "logos", "manifest.json"), {})
ORG_RULES = [("ocimf","ocimf"),("cdi","cdi"),("rightship","rightship"),("paris","parismou"),("tokyo","tokyomou"),("intertanko","intertanko"),
 ("adnoc","adnoc"),("repsol","repsol"),("moeve","moeve"),("cepsa","moeve"),("braskem","braskem"),("exxon","exxonmobil"),("total","totalenergies"),
 ("trans mountain","transmountain"),("fujairah","fujairah"),("uscg","uscg"),("med mou","medmou"),("iomou","iomou"),("equasis","equasis"),
 ("aramco","aramco"),("sigtto","sigtto"),("amsa","amsa"),("emsa","emsa"),("imo","imo"),("bp","bp"),
 ("omv","omv"),("saras","saras"),("marathon","marathon"),("siot","siot"),("toros","toros"),("motor oil","moh"),("preem","preem"),
 ("enbridge","enbridge"),("tüpraş","tupras"),("tupras","tupras")]
def org_keys(owner):
    o = (owner or "").lower(); keys = []
    for needle, key in ORG_RULES:
        if (needle in o if len(needle) > 3 else re.search(rf"\b{needle}\b", o)) and key not in keys: keys.append(key)
    return keys[:2]
def initials(name):
    w = [x for x in re.split(r"[\s/–-]+", name) if x and x[0].isalnum()]
    return (w[0][:3] if len(w) == 1 or w[0].isupper() and len(w[0]) <= 4 else "".join(x[0] for x in w[:2])).upper()
def orglogo(owner, depth=0, size="", fixed=False):
    out = ""
    for k in org_keys(owner) or [None]:
        m = ORG_LOGOS.get(k, {}) if k else {}
        name = m.get("name") or owner
        if m.get("file"):
            out += f'<span class="olg {size}{" dark" if m.get("dark_bg") else ""}" title="{e(name)}"><img src="{"../"*depth}assets/logos/{e(m["file"])}" alt="{e(name)} logo" loading="lazy"></span>'
        else:
            out += f'<span class="olg fb {size}" title="{e(name)}" aria-label="{e(name)}">{e(initials(name))}</span>'
    n = len(org_keys(owner) or [None])
    return f'<span class="olgs{" fix" if fixed else ""}{" two" if fixed and n > 1 else ""}{(" " + size) if fixed and size else ""}">{out}</span>'

def pagehead(kicker, title, lede, cls=""):
    return f'<section class="pagehead{(" " + cls) if cls else ""}"><div class="wrap"><p class="kicker">{kicker}</p><h1>{title}</h1><p>{lede}</p></div></section>'

SITE_URL = "https://vettingradar.com"
BEEHIIV_URL = "https://vetting-radar.beehiiv.com"
BEEHIIV_SUBSCRIBE = BEEHIIV_URL + "/subscribe"
# Beehiiv's embed has no API-key-free endpoint we can post to (its form needs a CSRF token and bot cookies), so we keep the
# official embed and crop its built-in white padding (.bh-crop in style.css) so the e-mail field gets the full width.
# Safety net (.bh-fb, app.js): Beehiiv's loader draws nothing for visitors who already subscribed from this site
# (cookie bhv_<publication>_subscribed, 1 year) or when its iframe never reports a size; then a plain button shows instead.
def signup_html(label="Subscribe free"):
    return f"""<div class="signup" id="subscribe-form"><div class="bh-crop"><div class="bh-form"><script async src="https://subscribe-forms.beehiiv.com/v3/loader.js" data-beehiiv-form="3413678f-3b46-449d-a13a-1341817dd862"></script></div></div>
<div class="bh-fb"><p class="bh-fb-t"><b>The weekly brief</b>What changed in tanker vetting rules, every item sourced. Free, unsubscribe any time.</p>
<a class="btn bh-fb-b" href="{BEEHIIV_SUBSCRIBE}" rel="noopener">{icon("mail")}{label}</a></div>
<p class="note bh-fallback">Free · unsubscribe any time · <a href="{BEEHIIV_SUBSCRIBE}" rel="noopener">Form not loading? Subscribe on Beehiiv</a></p></div>"""
signup = signup_html()
signup_card = f'<div class="card signup" id="subscribe">{signup}</div>'

# ---------- update cards ----------
def _pub(c): return bool(c.get("reviewed") and c.get("publish"))
def ucard(u, depth=0):
    g = GROUP.get(u.get("category"), u.get("group", "scheme"))
    who = "".join(f'<span class="badge who">{e(w)}</span>' for w in u.get("affects", []))
    chips = "".join(f'<span class="chip">{e(k)}</span>' for k in u.get("key_numbers", []))
    bullets = "".join(f"<li>{e(b)}</li>" for b in u.get("changed", []))
    todo = f'<p class="todo">{icon("todo")}<span><b>What to do:</b> {e(u["what_to_do"])}</span></p>' if u.get("what_to_do") else ""
    return f"""<article class="card ucard g-{g}" id="{e(u['id'])}">
<div class="top"><span class="cat">{GROUP_LABEL[g]}</span><span class="badge {e(u['impact'])}" title="Impact: editor's assessment"><span class="dot"></span>{IMPACT_LABEL[u['impact']]}</span>{who}<span class="src-id">{orglogo(u['owner'], depth)}<span class="oname">{e(u['owner'])}</span></span><time datetime="{e(u['date'])}">{fmt_date(u['date'])}</time></div>
<h3>{e(u['headline'])}</h3>
{f'<div class="chips" aria-label="Key numbers">{chips}</div>' if chips else ''}
<ul class="changed">{bullets}</ul>{todo}
<details><summary>Details</summary><p>{e(u['summary'])}</p></details>
<div class="ufoot"><a href="{e(u['source_url'])}" rel="noopener">Source</a><span>·</span><span>Verified {fmt_date(u['verified_on'])}</span></div></article>"""
for _u in updates:  # tolerate older/minimal update records
    _u.setdefault("id", re.sub(r"[^a-z0-9]+", "-", _u["title"].lower()).strip("-")[:60])
    _u.setdefault("headline", _u.get("short_title") or _u["title"]); _u.setdefault("impact", "medium")
UPD = sorted(updates, key=lambda u: u["date"], reverse=True)
UPD_BY_ID = {u["id"]: u for u in updates}

# ---------- index ----------
ok_sources = sum(1 for s in sources if state.get(s["id"], {}).get("hash"))
last_run = runlog.get("run_at", "")
RUN_N = runlog.get("sources_checked") or len(sources)
_e = runlog.get("error", runlog.get("errors", 0)); RUN_ERR = len(_e) if isinstance(_e, (list, dict)) else int(_e or 0)
RUN_OK = RUN_N - RUN_ERR
MON_LINE = (f"Monitor checked {RUN_N} sources on {fmt_date(last_run)}: {RUN_OK} OK"
            + (f", {RUN_ERR} unreachable" if RUN_ERR else "") + ".") if last_run else f"{len(sources)} sources watched."
pending = [c for c in changes if not _pub(c)]
rows_html = "".join(f"""<li><a class="row" href="updates.html#{e(u['id'])}"><span class="lc-logo">{orglogo(u['owner'], fixed=True)}</span>
<span class="t">{e(u['headline'])}<small><span class="badge {e(u['impact'])}"><span class="dot"></span>{e(u['impact'].title())}</span> {e(u['owner'])}</small></span><time datetime="{e(u['date'])}">{fmt_date(u['date'])}</time></a></li>""" for u in UPD[:5])
mon = (f'{icon("pulse")}<span>{len(pending)} change{"s" if len(pending)!=1 else ""} detected by the monitor, awaiting review. <a href="updates.html#monitor">View</a></span>' if pending
       else f'{icon("check")}<span>{MON_LINE} No unreviewed changes.</span>')
nxt = sorted([c for c in calendar if c["date"] and len(c["date"]) == 10 and (c.get("end") or c["date"]) >= TODAY.isoformat()], key=lambda c: c["date"])
def calic(d):
    x = dt.date.fromisoformat(d); return f'<span class="cal-ic" aria-hidden="true"><span class="m">{x.strftime("%b")}</span><span class="d">{x.day}</span></span>'
def _ongoing(c): return c["date"] < TODAY.isoformat() <= (c.get("end") or "")
def calic2(c):
    return '<span class="cal-ic now" aria-hidden="true"><span class="m">Now</span><span class="d">●</span></span>' if _ongoing(c) else calic(c["date"])
def when(c):
    if _ongoing(c): return f"Ongoing · until {fmt_date(c['end'])}"
    return fmt_date(c["date"]) + (f" – {fmt_date(c['end'])}" if c.get("end") else "")
nxt = sorted(nxt, key=lambda c: (c["date"] if not _ongoing(c) else c["end"]))
dates_html = "".join(f"""<li class="card date">{calic2(c)}<div><b>{e(c['title'])}</b><span class="src-id">{orglogo(c['owner'], 0, 'xs', fixed=True)}{when(c)}</span></div></li>""" for c in nxt[:3])
nk = nxt[0] if nxt else None
up_key = [c for c in nxt if c["date"] > TODAY.isoformat()]
nk = up_key[0] if up_key else nk
HERO_H1 = "Know what changed before your next screening."
HERO_SUB = "We watch OCIMF, CDI, RightShip, oil-major and terminal criteria every day, and tell you what changed, with the source."

# ---------- updates ----------
mon_items = "".join(f"""<div class="card item"><div class="meta"><span class="tag auto">{'Reviewed' if _pub(c) else 'Detected · unreviewed'}</span><span>{fmt_date(c['detected_at'])}</span><span>{e(c['owner'])}</span></div>
<h3>Change detected: {e(c['source_name'])}</h3><p class="note">{e(c['summary']) if _pub(c) and c.get('summary') else 'Not yet reviewed. Check the source directly.'}</p>
<div class="src"><a href="{e(c['url'])}" rel="noopener">Source</a></div></div>""" for c in changes[:20])
if not mon_items:
    mon_items = f'<div class="card item"><div class="meta"><span class="tag auto">Monitor</span><span>{fmt_date(last_run)}</span></div><h3>No unreviewed changes</h3><p class="note">{MON_LINE} New text changes appear here first, then as reviewed updates.</p></div>'
N_MINOR_U = sum(1 for u in UPD if u["impact"] == "low")
legend = "".join(f'<span><i style="background:var(--c-{k})"></i>{v}</span>' for k, v in GROUP_LABEL.items())
page("updates.html", "Vetting rule updates", pagehead("Updates", "Vetting rule changes, in plain words",
     "Each update: what changed, who it affects, the key numbers and the source. Impact levels are our editorial view.") + f"""
<div class="wrap page"><div class="grid"><div><div class="legend" aria-label="Category colours">{legend}</div><div class="ucards">{''.join(ucard(u) for u in UPD if u["impact"] != "low")}</div>
{(f'<details class="minor"><summary>+{N_MINOR_U} minor change{"s" if N_MINOR_U != 1 else ""}</summary><div class="ucards">' + ''.join(ucard(u) for u in UPD if u["impact"] == "low") + '</div></details>') if N_MINOR_U else ''}</div>
<aside class="side"><div id="monitor"><h2 class="sm" style="margin-top:0">Monitor feed</h2><div class="feed">{mon_items}</div></div>
<h2 class="sm">Subscribe</h2>{signup_card}</aside></div></div>""")

# ---------- compare navigation ----------
CP = load(P("data", "compare_pages.json"))
def subnav(cur):
    return '<nav class="subnav" aria-label="Vetting Rules pages"><div class="wrap">' + "".join(
        f'<a href="{h}"{(" class=\"on rron\"" if h == "reports.html" else " class=\"on\"") + " aria-current=\"page\"" if h == cur else ""}{" class=\"rrtab\"" if h == "reports.html" and h != cur else ""}>{icon(i)}{l}</a>' for h, l, i in CMP_TABS) + "</div></nav>"

# ---------- reader reports (user submitted; never official data) ----------
RR_DISCLAIMER = ('<p class="rr-disclaimer"><span class="rr-mark">Reported in practice</span> is user-declared: members\' experiences, not verified and not the position of any oil major, '
                 'terminal or organisation.</p>')
RR_SCRIPTS = '<script src="config.js"></script><script src="reports.js"></script>'
RR_SHORT = {"fujairah": "Port of Fujairah", "totalenergies": "TotalEnergies"}
RR_OWNERS = [{"id": r["id"], "name": RR_SHORT.get(r["id"]) or CP["owners"].get(r["id"], {}).get("name") or re.split(r" \(| – ", r["requirement_owner"])[0],
              "type": r["owner_type"], "href": f'table.html#row-{r["id"]}', "logo": orglogo(r["requirement_owner"], fixed=True)} for r in comp["rows"]]
RR_OWNER_IDS = {o["id"] for o in RR_OWNERS}
RR_JSON = '<script id="vr-owners" type="application/json">' + json.dumps(RR_OWNERS, ensure_ascii=False).replace("</", "<\\/") + '</script>'

def _rr_published():
    """Published reader reports at build time (public view, anon key), so pages show real counts before scripts run.
    Returns None when offline or not configured; pages then show neutral text."""
    if os.environ.get("VR_OFFLINE") == "1": return None
    try:
        cfg = open(P("site", "config.js")).read()
        url = os.environ.get("VR_SUPABASE_URL") or re.search(r'SUPABASE_URL:\s*"([^"]+)"', cfg).group(1)
        key = os.environ.get("VR_SUPABASE_ANON_KEY") or re.search(r'SUPABASE_ANON_KEY:\s*"([^"]+)"', cfg).group(1)
        import urllib.request
        req = urllib.request.Request(url.rstrip("/") + "/rest/v1/published_reports?select=owner_id,owner_other,items",
                                     headers={"apikey": key, "Authorization": "Bearer " + key})
        return json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as ex:
        print("reader reports: build-time count unavailable:", type(ex).__name__); return None
RR_PUB = _rr_published()
def _okey(r): return "other:" + (r.get("owner_other") or "").lower() if r.get("owner_id") == "other" else r.get("owner_id")
RR_N = len(RR_PUB) if RR_PUB is not None else None
RR_OWNERS_N = len({_okey(r) for r in RR_PUB}) if RR_PUB else 0
RR_OUT_N = len({_okey(r) for r in RR_PUB if r.get("owner_id") not in RR_OWNER_IDS}) if RR_PUB else 0  # not in the comparison table
def rr_cover(html_n=True):
    """One wording everywhere (reports.js coverTxt matches): 'N reader reports covering K oil majors, charterers & terminals (X beyond the T in our comparison).'
    T is the comparison-table count shown in the trust strip as 'T oil majors, charterers & terminals compared', so the two numbers reconcile.
    'charterers' because not every entry is an oil major (e.g. BASF, Braskem, SHIPVET). Never call them 'owners'."""
    n = f'<b id="rr-home-n">{RR_N}</b>' if html_n else str(RR_N)
    return (f"{n} reader report{'s' if RR_N != 1 else ''} covering {RR_OWNERS_N} {'oil majors, charterers &amp; terminals' if RR_OWNERS_N != 1 else 'charterer'}"
            + (f" ({RR_OUT_N} beyond the {len(RR_OWNER_IDS)} in our comparison)" if RR_OUT_N else "") + ".")
RR_BY = {}
for _r in RR_PUB or []: RR_BY[_r["owner_id"]] = RR_BY.get(_r["owner_id"], 0) + 1
def rr_count_txt(oid):
    if RR_PUB is None: return ""
    n = RR_BY.get(oid, 0); return f"· {n}" if n else "· none yet"
def rrbox(owner_id):  # collapsed "Reported in practice" layer under an owner's official criteria; reports.js fills it
    n = RR_BY.get(owner_id, 0)
    return (f'<details class="rr{" has" if n else ""}" id="rr-{e(owner_id)}" data-owner="{e(owner_id)}"><summary><span class="rr-mark">Reported in practice</span>'
            f'<span class="rr-n">{rr_count_txt(owner_id)}</span><span class="rr-lbl">User-declared · not official</span></summary>'
            f'<div class="rr-body"><p class="rr-empty">{"Loading…" if n else "None yet."} <a href="submit.html?owner={e(owner_id)}">Add what you faced</a></p></div></details>')
RR_INVITE = ('<p class="rr-invite" id="rr-home"><span class="rr-mark">Reader reports</span> '
             f'<span id="rr-home-t">{rr_cover() if RR_N else "Requirements members met in practice, charterer by charterer."}</span> '
             '<span class="rr-lbl">User-declared · not official.</span> <a href="reports.html">See them</a> · <a href="submit.html">Add what you faced</a></p>')

# ---------- index page ----------
IMP_RANK = {"high": 0, "medium": 1, "low": 2}
TOP = [u for u in UPD if u["impact"] in ("high", "medium")][:3]  # the 3 latest high/medium updates (UPD is newest first); minor ones stay on updates.html
N_MINOR = sum(1 for u in UPD if u["impact"] == "low")
N_REST = len(UPD) - len(TOP) - N_MINOR
def topcard(u):
    chips = "".join(f'<span class="chip">{e(k)}</span>' for k in u.get("key_numbers", [])[:3])
    todo = f'<p class="todo">{icon("todo")}<span><b>What to do:</b> {e(u["what_to_do"])}</span></p>' if u.get("what_to_do") else ""
    return f"""<article class="card topc imp-{e(u['impact'])}"><div class="top"><span class="badge {e(u['impact'])}"><span class="dot"></span>{IMPACT_LABEL[u['impact']]}</span><span class="src-id">{orglogo(u['owner'], 0, 'sm')}<span class="oname">{e(u['owner'])}</span></span><time datetime="{e(u['date'])}">{fmt_date(u['date'])}</time></div>
<h3><a href="updates.html#{e(u['id'])}">{e(u['headline'])}</a></h3>{f'<div class="chips">{chips}</div>' if chips else ''}{todo}
<p class="tfoot"><a href="updates.html#{e(u['id'])}">Details</a><span>·</span><a href="{e(u['source_url'])}" rel="noopener">Source</a></p></article>"""
def latest_item(u):
    todo = f'<p class="lt-do"><b>What to do:</b> {e(u["what_to_do"])}</p>' if u.get("what_to_do") else ""
    return (f'<li class="lt imp-{e(u["impact"])}"><div class="lt-top"><span class="badge {e(u["impact"])}"><span class="dot"></span>{IMPACT_LABEL[u["impact"]]}</span>'
            f'<span class="src-id">{orglogo(u["owner"], 0, "xs")}<span class="oname">{e(u["owner"])}</span></span><time datetime="{e(u["date"])}">{fmt_date(u["date"])}</time></div>'
            f'<h3><a href="updates.html#{e(u["id"])}">{e(u["headline"])}</a></h3>{todo}</li>')
more_bits = ([f"{N_REST} more"] if N_REST else []) + ([f"+{N_MINOR} minor"] if N_MINOR else [])
TYPES_VP = [("oil", "Oil (crude / product)"), ("chemical", "Chemical"), ("lpg", "LPG"), ("lng", "LNG")]
ISSUES_MD = sorted(glob.glob(P("newsletter", "issue-*.md")))
def _fm(md):
    fm = {}; m = re.match(r"^---\n(.*?)\n---\n", open(md).read(), re.S)
    for ln in (m.group(1).splitlines() if m else []):
        k, _, v = ln.partition(":"); fm[k.strip()] = v.strip().strip('"')
    return fm
SAMPLE = (os.path.basename(ISSUES_MD[0])[:-3], _fm(ISSUES_MD[0])) if ISSUES_MD else None
# one source count everywhere: len(sources) (= what the monitor checks); the last run's reachability is shown as part of the same line
MON_SHORT = (f"last check {fmt_date(last_run)}: {RUN_OK} OK" + (f", {RUN_ERR} unreachable" if RUN_ERR else "")) if last_run else ""
TRUST = (f'<div class="trustbar"><div class="wrap"><p class="trust">{icon("radar")}<span><b>{len(sources)}</b> public sources watched daily{(" (" + MON_SHORT + ")") if MON_SHORT else ""} · '
         f'<b>{len(comp["rows"])}</b> oil majors, charterers &amp; terminals compared · <b>{len(updates)}</b> reviewed updates · every item sourced</span></p></div></div>')
# homepage building blocks
CHECK_HTML = f"""<div><div class="sechead"><div><h2>Check charterer requirements</h2><p class="note">Which oil majors' and terminals' criteria does your vessel meet?</p></div></div>
<form class="card vpmini" action="table.html" method="get"><label><span>Vessel type</span><select name="type">{''.join(f'<option value="{k}">{v}</option>' for k, v in TYPES_VP)}</select></label>
<label><span>Age (years)</span><input name="age" type="number" min="0" max="60" step="0.1" inputmode="decimal" placeholder="e.g. 17" required></label>
<label><span>DWT</span><input name="dwt" type="number" min="0" step="1" inputmode="numeric" placeholder="e.g. 50000"></label>
<button class="btn" type="submit">Check requirements {icon("arrow")}</button></form>
<p class="note">Or open the <a href="table.html">requirements table</a>.</p></div>
"""
DATES_HTML = f"""<div><div class="sechead"><div><h2>Next dates</h2></div><a href="calendar.html">Calendar →</a></div><ul class="dates">{dates_html}</ul></div>"""
NLB_HTML = f"""<section class="block tight"><div class="wrap"><div class="nlb card">
<div><h2>The weekly brief</h2><p>What changed in vetting rules, who it affects, the key numbers and what to do. Free, in your inbox.</p>
<p class="nl-acts"><a class="btn" href="#subscribe">{icon("mail")}Subscribe free</a>{f'<a class="btn light" href="newsletter/{SAMPLE[0]}.html">Read sample issue #{e(SAMPLE[1].get("issue", "1"))}</a>' if SAMPLE else ''}</p></div>
{f'<a class="nl-sample" href="newsletter/{SAMPLE[0]}.html"><span class="kicker">Sample · {fmt_date(SAMPLE[1].get("date", ""))}</span><b>{e(SAMPLE[1].get("title", ""))}</b><span class="go">Read it {icon("arrow")}</span></a>' if SAMPLE else ''}
</div></div></section>"""
NOW_DATES = f'<section class="block tight"><div class="wrap two">{CHECK_HTML}{DATES_HTML}</div></section>'
def latest_box(title="Latest changes", items=TOP, cls=""):
    return (f'<div class="latest{cls}"><div class="lh"><h2>{title}</h2><a href="updates.html">All updates{(" (" + ", ".join(more_bits) + ")") if more_bits else ""} →</a></div>'
            f'<ol class="lts">{"".join(latest_item(u) for u in items)}</ol></div>')
if LOTW:
    # Homepage "lessons first" (option C, chosen 2026-10-19): the lesson of the week leads, the signup sits beside it (below it on phones,
    # where a "Get the weekly brief" link under the intro jumps to it), then more lessons, the trust strip, rule changes, tools, newsletter, reader reports.
    # Toolbox links point at the PDF when headless Chrome can print it; after LS.build any missing PDF is swapped for the printable page (see below).
    def tb_href(l): return (f"lessons/{l['id']}-toolbox.pdf", LS.TOOLBOX_LABEL) if CHROME else (f"lessons/{l['id']}-toolbox.html", LS.TOOLBOX_LABEL_HTML)
    LOTW_TB, LOTW_TBL = tb_href(LOTW)
    # the next lessons after the lesson of the week: one per topic first, so the cards show the range
    _rest = [l for l in LESSONS if l is not LOTW]; NEXT_L = []
    for l in _rest:
        if l["topic"] != LOTW["topic"] and all(x["topic"] != l["topic"] for x in NEXT_L): NEXT_L.append(l)
    NEXT_L += [l for l in _rest if l not in NEXT_L]
    def stags(l, n=3): return "".join(f'<span class="stag">SIRE {e(t)}</span>' for t in l["sire2_tags"][:n])
    def lmini(l):  # small lesson card
        h, lab = tb_href(l)
        return (f'<article class="card lcard ho-lm"><div class="top"><span class="cat">{e(l["topic"])}</span><span class="badge who">{e(l.get("ship_type_label", ""))}</span></div>'
                f'<h3><a href="lessons/{e(l["id"])}.html">{e(l["title"])}</a></h3><div class="tags">{stags(l, 2)}</div>'
                f'<div class="lfoot"><span>{e(l["source_short"])}</span><span class="lf-i"><span class="sep" aria-hidden="true">·</span>'
                f'<a href="{e(h)}" data-goatcounter-click="dl-toolbox-{e(l["id"])}" data-goatcounter-title="Toolbox talk (home)">{e(lab)}</a></span></div></article>')
    _topics = [t for t in LS.TOPICS if any(l["topic"] == t for l in LESSONS)]
    TOPIC_CHIPS = ('<nav class="topicbar ho-chips" aria-label="Lesson topics">' + "".join(
        f'<a href="lessons.html?topic={LS.slug(t)}">{e(t)} <span class="n">{sum(1 for l in LESSONS if l["topic"] == t)}</span></a>' for t in _topics) + '</nav>')
    CHK = "".join(f"<li>{e(x)}</li>" for x in LOTW["check_on_board"][:4])
    SRC_L = f'Source: <a href="{e(LOTW["source_url"])}" rel="noopener">{e(LOTW["source_short"])}</a>, published {fmt_date(LOTW["source_published"])}'
    C_H1 = "Your next safety meeting, ready to print."
    C_SUB = ("One public incident report a week, in plain words, mapped to SIRE 2.0, CDI chapters and PSC codes, with a free one-page toolbox talk. "
             "Plus the vetting rule changes that matter.")
    c_tags = stags(LOTW) + "".join(f'<span class="ctag">CDI: {e(c)}</span>' for c in LOTW.get("cdi_tags", [])[:1]) + "".join(f'<span class="ptag">PMoU {e(c)}</span>' for c in LOTW.get("psc_codes", [])[:1])
    if SIRE_LOTW:
        C_SUB = ("Every week: one public incident report and one SIRE 2.0 observation, in plain words, each with a free one-page toolbox talk. "
                 "Plus the vetting rule changes that matter.")
    def sire_card(l):  # same format as the incident card, indigo accent (.sire)
        h, lab = tb_href(l)
        chk = "".join(f"<li>{e(x)}</li>" for x in l["check_on_board"][:4])
        return (f'<article class="card ho-c-lotw sire" id="sire-lotw"><div class="ho-c-k"><span class="kicker">SIRE 2.0 lesson of the week</span><span class="cat">{e(l["topic"])}</span><span class="badge who">{e(l["ship_type_label"])}</span></div>'
                f'<h2><a href="lessons/{e(l["id"])}.html">{e(l["title"])}</a></h2><p class="sum">{e(l["summary3"])}</p>'
                f'<div class="ho-c-chk"><h4>What to check on board</h4><ol>{chk}</ol></div>'
                f'<div class="tags">{SL.qtags(l, e)}{SL.rtags(l, e, 3)}{SL.ptags(l, e, 1)}</div>'
                f'<div class="btnrow ho-c-btns"><a class="btn big" href="{e(h)}" data-goatcounter-click="dl-toolbox-{e(l["id"])}" data-goatcounter-title="Toolbox talk (home, SIRE)">{icon("todo")}{e(lab)}</a><a class="btn light" href="lessons/{e(l["id"])}.html">Read the lesson</a></div>'
                f'<p class="note ho-c-src">One page · free to print, no sign-up · {e(l["source_line"])} · <a href="{e(l["guidance_url"])}" rel="noopener">{e(l["guidance"])}</a></p></article>')
    SIDE = (f'<aside class="ho-c-side"><div class="herobox" id="subscribe"><p class="hero-note">{icon("mail")}A new lesson and the rule changes, every week</p>{signup}</div></aside>'
            if not SIRE_LOTW else sire_card(SIRE_LOTW))
    # with two cards the signup leaves the hero column for a slim full-width bar right below them
    SBAR = (f'<div class="ho-sbar" id="subscribe"><div class="ho-sbar-t">{icon("mail")}<p><b>The weekly brief</b><span class="d">One incident lesson, one SIRE 2.0 observation and the vetting rule changes, every week. Free, unsubscribe any time.</span></p></div>'
            f'<div class="ho-sbar-f">{signup}</div></div>') if SIRE_LOTW else ""
    # hero kicker: with a SIRE lesson, each part in its card's colour (amber incident, indigo SIRE 2.0), "for tankers" neutral
    EYEBROW = ('<span class="eyebrow ho-eb2"><span class="eb-s"><span class="pulse"></span>Safety lessons</span><span class="eb-sep" aria-hidden="true">·</span>'
               '<span class="eb-g"><span class="eb-r"><span class="pulse"></span>SIRE 2.0 lessons</span><span class="eb-n">for tankers</span></span></span>') if SIRE_LOTW \
        else '<span class="eyebrow"><span class="pulse"></span>Safety lessons for tankers</span>'
    page("index.html", "Home", desc=C_SUB, full_title="Vetting Radar · " + C_H1.rstrip("."), head='<link rel="stylesheet" href="lessons.css"><link rel="stylesheet" href="home.css">', scripts=RR_SCRIPTS, body=f"""
<section class="hero ho-c{' ho-c2' if SIRE_LOTW else ''}"><div class="wrap">
<div class="ho-c-top">{EYEBROW}<h1>{C_H1}</h1><p class="sub">{C_SUB}</p>
<a class="ho-c-brief" href="#subscribe">{icon("mail")}Get the weekly brief, free <span aria-hidden="true">↓</span></a></div>
<div class="ho-c-main">
<article class="card ho-c-lotw" id="lotw"><div class="ho-c-k"><span class="kicker">Lesson of the week</span><span class="cat">{e(LOTW['topic'])}</span><span class="badge who">{e(LOTW.get('ship_type_label', ''))}</span></div>
<h2><a href="lessons/{e(LOTW['id'])}.html">{e(LOTW['title'])}</a></h2><p class="sum">{e(LOTW['summary3'])}</p>
<div class="ho-c-chk"><h4>What to check on board</h4><ol>{CHK}</ol></div>
<div class="tags">{c_tags}</div>
<div class="btnrow ho-c-btns"><a class="btn big" href="{e(LOTW_TB)}" data-goatcounter-click="dl-toolbox-{e(LOTW['id'])}" data-goatcounter-title="Toolbox talk (home)">{icon("todo")}{e(LOTW_TBL)}</a><a class="btn light" href="lessons/{e(LOTW['id'])}.html">Read the lesson</a></div>
<p class="note ho-c-src">One page · free to print, no sign-up · {SRC_L}</p></article>
{SIDE}
</div>{SBAR}</div></section>
<section class="block tight"><div class="wrap"><div class="sechead"><div><h2>Safety lessons by topic</h2></div><a href="lessons.html">All {len(LESSONS)} lessons →</a></div>
{TOPIC_CHIPS}<div class="ho-lms four">{"".join(lmini(l) for l in NEXT_L[:4])}</div></div></section>
{TRUST}
<section class="block tight"><div class="wrap">{latest_box("Vetting rule changes", TOP, " ho-flat")}</div></section>
{NOW_DATES}
{NLB_HTML}<section class="ho-rr"><div class="wrap">{RR_INVITE}</div></section>
{RR_JSON}""")
else:  # no published safety lessons: the rule-changes homepage
    page("index.html", "Home", desc=HERO_SUB, full_title="Vetting Radar · " + HERO_H1.rstrip("."), body=f"""
<section class="hero"><div class="wrap"><div class="hero-l">
<span class="eyebrow"><span class="pulse"></span>Tanker vetting intelligence</span>
<h1>{HERO_H1}</h1><p class="sub">{HERO_SUB}</p>
<div class="herobox" id="subscribe">{signup}</div></div>
<div class="hero-r"><div class="latest"><div class="lh"><h2>Latest changes</h2><a href="updates.html">All updates{(' (' + ', '.join(more_bits) + ')') if more_bits else ''} →</a></div>
<ol class="lts">{''.join(latest_item(u) for u in TOP)}</ol></div></div>
</div></section>
{TRUST}
{LS.lotw_block(LOTW, e, fmt_date, icon, f"lessons/{LOTW['id']}-toolbox.{'pdf' if CHROME else 'html'}" if LOTW else "")}
<section class="block tight"><div class="wrap two">
{CHECK_HTML}{DATES_HTML}</div></section>
{NLB_HTML}<div class="wrap">{RR_INVITE}</div>
{RR_JSON}""", scripts=RR_SCRIPTS, head='<link rel="stylesheet" href="lessons.css">' if LOTW else "")

# ---------- table: requirements lookup ----------
LK = load(P("data", "lookup.json"), {"owners": {}})["owners"]
COLS = [("age_limits", "age", "Vessel age"), ("sire_report_age", "sire", "SIRE / inspection"), ("cap_rules", "cap", "CAP"), ("other_criteria", "other", "Other criteria")]
def kcell(r, field, kk, label):
    full = r.get(field); key = LK.get(r["id"], {}).get("key", {}).get(kk)
    if not full:
        return f'<td class="kc ns" data-l="{label}"><span class="kv ns">Not stated in source</span></td>'
    return (f'<td class="kc" data-l="{label}"><span class="kv">{e(key or full)}</span>'
            f'<details class="more"><summary>Details</summary><p>{e(full)}</p></details></td>')
def clip(v, n=60, tag="span"):
    """Short value in the cell; the full text opens on tap (details). Cuts at a word boundary."""
    v = str(v or "")
    if len(v) <= n: return e(v)
    cut = v[:n].rsplit(" ", 1)[0].rstrip(",;:·(–-") or v[:n]
    return f'<details class="clip"><summary><span class="cs">{e(cut)}…</span><span class="cm"></span></summary><span class="cf">{e(v)}</span></details>'
def flagbtn(text):
    return (f'<button type="button" class="flg" aria-label="Source note: {e(text)}">{icon("alert")}<span class="pop" role="tooltip">{e(text)}</span></button>') if text else ""
types = sorted({r["owner_type"] for r in comp["rows"]})
trs = ""
for r in comp["rows"]:
    links = f'<a href="{e(r["source_url"])}" rel="noopener">Primary source</a>' + "".join(f' · <a href="{e(u)}" rel="noopener">Source {i+2}</a>' for i, u in enumerate(r["extra_source_urls"]))
    nm = RR_SHORT.get(r["id"]) or CP["owners"].get(r["id"], {}).get("name") or re.split(r" \(| – ", r["requirement_owner"])[0]
    trs += f"""<tr data-type="{e(r['owner_type'])}" id="row-{e(r['id'])}" data-id="{e(r['id'])}" class="off-row"><th scope="row" class="owner"><div class="ohd">{orglogo(r['requirement_owner'], fixed=True)}<div><b title="{e(r['requirement_owner'])}">{e(nm)}</b>{flagbtn(r['flags'])}<span class="pill">{e(r['owner_type'])}</span></div></div></th>
<td class="res" data-l="Your vessel"></td>{''.join(kcell(r, f, k, l) for f, k, l in COLS)}
<td class="srcc" data-l="Source"><span class="srcl">{links}</span><span class="note">{clip(r['document'], 48)}{(' · ' + e(r['document_date'])) if r['document_date'] else ''} · verified {fmt_date(r['verified_on'])}</span></td></tr>
<tr class="rr-row" data-type="{e(r['owner_type'])}" data-for="{e(r['id'])}"><td colspan="7"><div class="rr-stick">{rrbox(r['id'])}</div></td></tr>"""
gaps = "".join(f"<li><b>{e(g['owner'])}</b>: {e(g['note'])}</li>" for g in comp["not_found_publicly"])
LK_JSON = '<script id="vr-lookup" type="application/json">' + json.dumps({k: v["rules"] for k, v in LK.items()}, ensure_ascii=False).replace("</", "<\\/") + '</script>'
LK_SRC = '<script id="vr-src" type="application/json">' + json.dumps({r["id"]: r["source_url"] for r in comp["rows"]}).replace("</", "<\\/") + '</script>'
page("table.html", "Who requires what — tanker vetting criteria compared", f"""
""" + pagehead("Vetting Rules", "Who requires what", "Tanker acceptance criteria charterer by charterer, from cited public documents. Enter your vessel to see where it stands.") + subnav("table.html") + f"""<div class="wrap page widepage">
<form class="card vp" id="vp" action="table.html" method="get" novalidate>
<div class="vp-h"><h2>Check a vessel profile</h2><p class="note">Shows which oil majors' and terminals' public criteria the ship meets, fails or where the source can't decide. We never guess: unclear means check the source.</p></div>
<div class="vp-f">
<label><span>Vessel type</span><select name="type" id="vp-type">{''.join(f'<option value="{k}">{v}</option>' for k, v in TYPES_VP)}</select></label>
<label><span>Age (years)</span><input name="age" id="vp-age" type="number" min="0" max="60" step="0.1" inputmode="decimal" placeholder="e.g. 17"></label>
<label><span>DWT</span><input name="dwt" id="vp-dwt" type="number" min="0" step="1" inputmode="numeric" placeholder="e.g. 50000"></label>
<label><span>CAP rating <i>optional</i></span><select name="cap" id="vp-cap"><option value="">Not entered</option><option value="1">CAP 1</option><option value="2">CAP 2</option><option value="3">CAP 3</option><option value="4">CAP 4</option></select></label>
<label><span>SIRE report age <i>months, optional</i></span><input name="sire" id="vp-sire" type="number" min="0" max="60" step="0.5" inputmode="decimal" placeholder="e.g. 4"></label>
<div class="vp-b"><button class="btn" type="submit">Check</button><button class="btn light" type="reset" id="vp-clear">Clear</button></div></div>
<p class="vp-sum" id="vp-sum" aria-live="polite" hidden></p></form>
<div class="tbar"><input id="q" type="search" placeholder="Search oil majors, terminals or text: e.g. CAP 2, LNG, crew matrix" aria-label="Search"><select id="t" aria-label="Type"><option value="">All types</option>{''.join(f'<option>{e(t)}</option>' for t in types)}</select>
<span class="note">Showing <b id="cmp-count">{len(comp['rows'])}</b> of {len(comp['rows'])} · <a href="data/comparison.csv">CSV</a> · <a href="data/comparison.json">JSON</a></span></div>
<p class="vline">{icon("check")}Summaries of public documents, not legal text; charterers apply criteria case by case. <b>Always verify at the linked source.</b></p>
<div class="tablewrap lk"><table id="cmp" class="lk"><thead><tr><th scope="col" class="owner">Oil major / terminal</th><th scope="col" class="res">Your vessel</th>{''.join(f'<th scope="col">{l}</th>' for _f, _k, l in COLS)}<th scope="col">Source &amp; date</th></tr></thead><tbody>{trs}</tbody></table></div>
<details class="gaps"><summary>Not covered yet ({len(comp['not_found_publicly'])})</summary><ul>{gaps}</ul></details>
{RR_DISCLAIMER}</div>{RR_JSON}{LK_JSON}{LK_SRC}""", scripts=RR_SCRIPTS + '<script src="lookup.js"></script>')

# ---------- compare sub-pages (checklist, frequency, terminals, crew) ----------
def verified_bar(extra=""):
    return (f'<div class="vbar"><span>{icon("check")}Verified {fmt_date(CP["verified_on"])} against the linked public documents</span>'
            f'<span>{icon("link")}Every value links to its source</span><span>Summaries, not legal text. <b>Always verify at the linked source.</b></span>{extra}</div>')
OWN = CP["owners"]
def ohead(k):  # owner column header: logo + name, linked to the source
    o = OWN[k]
    return f'<th class="oh" scope="col"><a href="{e(o["url"])}" rel="noopener" title="{e(o["doc"])}">{orglogo(o["org"], fixed=True)}<span>{e(o["name"])}</span></a></th>'
def ocell(k, sub=""):  # owner row header
    o = OWN[k]
    return f'<th scope="row" class="orow"><div class="src-id">{orglogo(o["org"], fixed=True)}<b>{e(o["name"])}</b>{flagbtn(o.get("flag"))}</div><div class="note">{e(o["doc"])}</div>{sub}</th>'
def srclist(keys):
    return '<ol class="srcs">' + "".join(f'<li><span class="src-id">{orglogo(OWN[k]["org"], 0, "xs")}<b>{e(OWN[k]["name"])}</b></span> {e(OWN[k]["doc"])} · <a href="{e(OWN[k]["url"])}" rel="noopener">source</a>{(" · <i>" + e(OWN[k]["flag"]) + "</i>") if OWN[k].get("flag") else ""}</li>' for k in keys) + "</ol>"
LV = {"req": "Stated requirement", "cond": "Conditional / recommended", "ns": "Not stated in source"}
def lvlegend(levels, labels):
    return '<div class="lvlegend" aria-label="Legend">' + "".join(f'<span><i class="lv {k}"></i>{e(labels[k])}</span>' for k in levels) + "</div>"

# a. pre-screening checklist
ck = CP["checklist_owners"]
rows_ck = ""
for it in CP["checklist"]:
    tds = ""
    for k in ck:
        lv, txt = it["cells"].get(k, ["ns", ""])
        tds += f'<td class="lvc"><span class="lv {lv}">{e(txt) if txt else "—"}</span></td>' if lv != "ns" else '<td class="lvc"><span class="lv ns" title="Not stated in the cited source">—</span></td>'
    rows_ck += f'<tr><th scope="row" class="item"><b>{e(it["item"])}</b><div class="note">{e(it["hint"])}</div></th>{tds}</tr>'
def ck_card(k):
    o = OWN[k]; dl = ""
    for it in CP["checklist"]:
        lv, txt = it["cells"].get(k, ["ns", ""])
        dl += f'<div class="oc-r"><dt>{e(it["item"])}</dt><dd>' + (f'<span class="lv {lv}">{e(txt)}</span>' if lv != "ns" and txt else '<span class="lv ns">Not stated in source</span>') + '</dd></div>'
    return (f'<article class="card ocard"><header><span class="lc-logo">{orglogo(o["org"], fixed=True)}</span><div><h3>{e(o["name"])}</h3>'
            f'<a class="note" href="{e(o["url"])}" rel="noopener">{e(o["doc"])}</a></div></header><dl>{dl}</dl></article>')
ck_cards = "".join(ck_card(k) for k in ck)
page("compare-checklist.html", "Pre-screening checklist: what oil majors and terminals ask for", section="table.html",
     desc="The documents and conditions commonly required for oil-major and terminal clearance (SIRE recency, CAP, Q88/HVPQ, crew matrix, PSC, certificates), charterer by charterer, from public sources.",
     body=pagehead("Vetting Rules", "Pre-screening checklist", "The documents and conditions most often checked before a tanker is cleared, and which oil majors and terminals publicly require each one.") + subnav("compare-checklist.html") + f"""
<div class="wrap page widepage"><p class="intro">Use this as a checklist before you submit a vessel for clearance: inspection recency, CAP, questionnaire and crew-matrix freshness, PSC record, certificates and TMSA. Each column is one oil major, terminal or vetting scheme; the header links to the public document we read. A dash means the cited source does not say, not that there is no rule.</p>
{verified_bar()}
{lvlegend(["req","cond","ns"], LV)}
<div class="ocards" aria-label="Checklist by oil major or terminal">{ck_cards}</div>
<div class="tablewrap mxwrap mx-ck"><table class="mx" id="ck"><thead><tr><th class="item" scope="col">Check</th>{''.join(ohead(k) for k in ck)}</tr></thead><tbody>{rows_ck}</tbody></table></div>
<p class="note mx-hint">Scroll sideways for all {len(ck)} oil majors and terminals. Values are short summaries; size bands, gas carriers and exceptions are in the sources and on the <a href="table.html">requirements table</a>.</p>
<h2 class="sm">Sources</h2>{srclist(ck)}</div>""")

# b. inspection frequency by age
FQ = {"t3": "≤ 3–4 months", "t6": "≈ 6 months", "t12": "7–15 months", "scr": "Screening, no fixed interval", "no": "Not accepted", "ns": "Not stated"}
rows_fq = ""
for f in CP["frequency"]:
    tds = "".join(f'<td class="fq {lv}" data-l="{e(b)}"><span>{e(t) if t else "—"}</span></td>' for (lv, t), b in zip(f["cells"], CP["bands"]))
    rows_fq += f'<tr>{ocell(f["owner"], f"<div class=\"note fqn\">{e(f["note"])}</div>" if f.get("note") else "")}{tds}</tr>'
page("compare-frequency.html", "Inspection frequency by vessel age, charterer by charterer", section="table.html",
     desc="How fresh a SIRE or oil-major inspection must be at each vessel age band, for oil majors, vetting schemes and terminals, from public sources.",
     body=pagehead("Vetting Rules", "Inspection frequency by vessel age", "How recent the SIRE or oil-major inspection must be as a tanker gets older, and where each charterer stops accepting it.") + subnav("compare-frequency.html") + f"""
<div class="wrap page widepage"><p class="intro">Each row is one oil major, terminal or vetting scheme, each column an age band. Colours show how tight the inspection window is; dark cells mean the charterer's published age limit excludes the vessel. Bands are approximate: charterers draw the line at slightly different ages (e.g. 10.1 or 15.1 years), so check the exact wording at source.</p>
{verified_bar()}
<div class="lvlegend fqlegend" aria-label="Legend">{''.join(f'<span><i class="fq {k}"></i>{e(v)}</span>' for k, v in FQ.items())}</div>
<div class="tablewrap mxwrap mx-cards"><table class="mx fqt"><thead><tr><th scope="col">Oil major / terminal</th>{''.join(f'<th scope="col" class="band">{e(b)}</th>' for b in CP["bands"])}</tr></thead><tbody>{rows_fq}</tbody></table></div>
<p class="note">Oil and chemical tankers above 5,000 dwt unless noted. Gas carriers and small tankers often have higher age limits; see the sources.</p>
<h2 class="sm">Sources</h2>{srclist([f["owner"] for f in CP["frequency"]])}</div>""")

# c. terminal requirements
def tfield(label, v):
    return f'<div class="tf"><dt>{label}</dt><dd>{e(v) if v else "<span class=\"blank\">not stated in source</span>"}</dd></div>'
tcards = ""
RR_TERM = {"Saudi Aramco": "aramco", "Port of Fujairah": "fujairah", "Trans Mountain": "transmountain", "SARAS": "saras"}
for t in CP["terminals"]:
    rid = RR_TERM.get(t["org"]); rid = rid if rid in RR_OWNER_IDS else None
    links = f'<a href="{e(t["url"])}" rel="noopener">Primary source</a>' + "".join(f' · <a href="{e(u)}" rel="noopener">Source {i+2}</a>' for i, u in enumerate(t["extra"]))
    tcards += f"""<article class="card tcard"><header><span class="lc-logo">{orglogo(t['org'], fixed=True)}</span><div><h3>{e(t['name'])}</h3><span class="pill">{e(t['country'])}</span> <span class="note">{e(t['doc'])}{(' · ' + fmt_date(t['date'])) if t['date'] else ''}</span></div></header>
<dl>{tfield("Age limit", t["age"])}{tfield("SIRE / vetting", t["sire"])}{tfield("Pre-arrival &amp; documents", t["prearrival"])}{tfield("Escort &amp; tugs", t["escort"])}</dl>
<div class="tfoot">{flagbtn(t["flag"])}{links}<span>·</span><span>Verified {fmt_date(CP['verified_on'])}</span><span>·</span><span>Verify at source</span></div>{rrbox(rid) if rid else ''}</article>"""
page("compare-terminals.html", "Terminal requirements: age limits, SIRE, pre-arrival and escort rules", section="table.html",
     desc="Public terminal and port rules for tankers: age limits, SIRE/vetting, pre-arrival documents and escort tugs (Saudi Aramco, Fujairah, Trans Mountain, SIOT Trieste, Ceyhan, Brofjorden, Ingleside and more).",
     body=pagehead("Vetting Rules", "Terminal requirements", "What terminals publish about vessel age, SIRE or terminal vetting, pre-arrival documents and escort tugs.") + subnav("compare-terminals.html") + f"""
<div class="wrap page"><p class="intro">Terminals screen on top of the charterer's clearance. These cards summarise what each terminal's own public handbook or port notice says. Blank fields mean that document does not cover the point; other port rules or the charterer may still apply.</p>
{verified_bar()}
<div class="controls"><input id="tq" type="search" placeholder="Search terminals: e.g. escort, 25 years, Q88, H2S…"></div>
<div class="tcards" id="tcards">{tcards}</div>
<p class="note" style="margin-top:16px">Missing a terminal? Only terminals with a public document we could read are listed.</p>{RR_DISCLAIMER}</div>{RR_JSON}
<script>document.addEventListener('DOMContentLoaded',()=>{{const q=document.getElementById('tq');q.addEventListener('input',()=>{{const v=q.value.toLowerCase().trim();document.querySelectorAll('#tcards .tcard').forEach(c=>{{c.style.display=!v||c.innerText.toLowerCase().includes(v)?'':'none'}})}})}});</script>""", scripts=RR_SCRIPTS)

# d. crew matrix
def yrs(v, l=""): return f'<td class="yr" data-l="{e(l)}">{e(v)}</td>' if v else f'<td class="yr na" data-l="{e(l)}" title="Not stated in source">—</td>'
def txt(v, l=""): return f'<td data-l="{e(l)}">{clip(v, 56)}</td>' if v else f'<td data-l="{e(l)}"><span class="blank">—</span></td>'
CR_SUB = ["operator", "rank", "type", "all tankers"]
rows_cr = ""
for c in CP["crew"]:
    rows_cr += (f'<tr class="off-row">{ocell(c["owner"])}' + "".join(yrs(v, f"Master + C/O · {l}") for v, l in zip(c["m"], CR_SUB))
                + "".join(yrs(v, f"Chief + 2nd Eng. · {l}") for v, l in zip(c["e"], CR_SUB))
                + f'{txt(c["junior"], "Junior officers")}{txt(c["english"], "English")}{txt(c["nat"], "Nationalities")}{txt(c["fresh"], "Matrix freshness")}{txt(c["other"], "Other")}</tr>')
    if c["owner"] in RR_OWNER_IDS: rows_cr += f'<tr class="rr-row"><td colspan="14"><div class="rr-stick">{rrbox(c["owner"])}</div></td></tr>'
none = ", ".join(OWN[k]["name"] for k in CP["crew_none"])
SUB = '<th scope="col" class="yh">Operator</th><th scope="col" class="yh">Rank</th><th scope="col" class="yh">Type</th><th scope="col" class="yh">All tankers</th>'
page("compare-crew.html", "Crew-matrix requirements compared: officer experience, English, nationalities", section="table.html",
     desc="Officer experience minimums (years with operator, in rank, on type), English, nationality limits and crew-matrix freshness, charterer by charterer, from public sources.",
     body=pagehead("Vetting Rules", "Crew-matrix comparison", "Senior officer experience, English, nationality limits and how fresh the crew matrix must be, per oil major.") + subnav("compare-crew.html") + f"""
<div class="wrap page widepage"><p class="intro">Most oil majors check the OCIMF officer / crew matrix against combined ("aggregate") experience for the Master + Chief Officer and the Chief Engineer + Second (or First) Engineer. Figures are minimum years: calendar time with the operator, then sea time in rank, on the same tanker type and on all tankers. A dash means the cited source does not set that value.</p>
{verified_bar()}
<div class="tablewrap mxwrap mx-cards"><table class="mx crew"><thead>
<tr><th rowspan="2" scope="col">Oil major / terminal</th><th colspan="4" scope="colgroup" class="grp">Master + Chief Officer (years)</th><th colspan="4" scope="colgroup" class="grp">Chief Eng. + 2nd / 1st Eng. (years)</th><th rowspan="2" scope="col">Junior officers</th><th rowspan="2" scope="col">English</th><th rowspan="2" scope="col">Nationalities</th><th rowspan="2" scope="col">Matrix freshness</th><th rowspan="2" scope="col">Other</th></tr>
<tr>{SUB}{SUB}</tr></thead><tbody>{rows_cr}</tbody></table></div>
<p class="note">No public crew-matrix rules found in the sources reviewed for: {e(none)}. ExxonMobil values come from a 2017 edition on a third-party host and are shown for reference only.</p>
{f'<p class="note">Members have shared crew-matrix requirements they met for {RR_OWNERS_N} oil majors and terminals: see <a href="reports.html">reader reports</a>.</p>' if RR_OWNERS_N else ''}
<h2 class="sm">Sources</h2>{srclist([c["owner"] for c in CP["crew"]])}{RR_DISCLAIMER}</div>{RR_JSON}""", scripts=RR_SCRIPTS)

# ---------- reader reports pages ----------
RR_CATS = [("crew", "Crew experience"), ("vessel_age", "Vessel age"), ("inspections", "Inspections / SIRE"), ("terminal", "Terminal"), ("other", "Other")]
RR_VT = [("crude", "Crude tanker"), ("product", "Product tanker"), ("chemical", "Chemical tanker"), ("lpg", "LPG carrier"), ("lng", "LNG carrier"), ("other", "Other")]
_oopts = "".join(f'<option value="{e(o["id"])}">{e(o["name"])}</option>' for o in RR_OWNERS)
_copts = "".join(f'<option value="{k}">{v}</option>' for k, v in RR_CATS)
RR_SOON = '<div class="rr-soon" id="rr-soon"><p>Loading reader reports…</p></div>'
RR_KICK = '<span class="rr-mark">Reader reports</span><span class="rr-lbl">User-declared · not official</span>'
def rr_join(title, lede):
    return (f'<div class="card rr-card rr-accent" id="rr-join" hidden><h2>{title}</h2><p class="note">{lede}</p>'
            '<form class="rr-joinf" novalidate><label class="rr-l" for="rr-email">Email</label><div class="rr-inline"><input id="rr-email" name="email" type="email" autocomplete="email" required placeholder="you@example.com">'
            f'<button class="btn rr" type="submit">{icon("mail")}Email me a sign-in link</button></div><p class="rr-msg" role="status" hidden></p></form>'
            '<p class="note rr-small">No password. We use your email only to sign you in; it is never shown with your reports.</p></div>')

page("reports.html", "Reader reports: requirements members met in practice", section="reports.html",
     desc="Requirements tanker people say they met in practice, shared by members, reviewed before publishing, and kept separate from official vetting criteria.",
     body=pagehead(RR_KICK, "Reader reports", "Requirements members met in practice, charterer by charterer. Reviewed before publishing, never official.", "rr-head") + subnav("reports.html") + f"""
<div class="wrap page rr-page"><div class="rr-top"><p class="intro">{(rr_cover(False) + " ") if RR_N else ""}Open an oil major or terminal to see what members met. Vote if it matches yours.</p>
<a class="btn sm rr-o" href="submit.html">+ Add what you faced</a></div>
<div class="rr-filters" id="rr-filters" hidden><select id="rr-fo" aria-label="Oil major or terminal"><option value="">All oil majors &amp; terminals</option>{_oopts}<option value="other">Other</option></select><span class="note"><b id="rr-count">0</b> reports</span></div>
<div id="rr-list">{RR_SOON}</div>
{RR_DISCLAIMER}</div>{RR_JSON}""", scripts=RR_SCRIPTS)

page("submit.html", "Post a reader report", section="reports.html", csp="session",
     desc="Share a tanker vetting requirement you met in practice. Members only, reviewed before publishing.",
     body=pagehead(RR_KICK, "Add what you faced", "Share one requirement you met in practice. Members only, reviewed before it goes public.", "rr-head") + subnav("reports.html") + f"""
<div class="wrap page rr-narrow" id="rr-submit">{RR_SOON}
{rr_join("Join to post a report", "Membership is free. Enter your email and we'll send a one-time sign-in link.")}
<div id="rr-post" hidden><div class="rr-who note"></div>
<form class="card rr-card rr-accent rr-form" id="rr-form" novalidate>
<div class="rr-f"><label class="rr-l" for="rr-owner">Oil major or terminal</label><select id="rr-owner" name="owner" required><option value="">Select…</option>{_oopts}<option value="other">Other</option></select></div>
<div class="rr-f" id="rr-other" hidden><label class="rr-l" for="rr-oo">Which one?</label><input id="rr-oo" name="owner_other" maxlength="60" placeholder="Oil major or terminal name"></div>
<div class="rr-f"><label class="rr-l" for="rr-cat">Category</label><select id="rr-cat" name="category" required>{_copts}</select></div>
<div class="rr-f"><label class="rr-l" for="rr-req">Requirement you faced</label><textarea id="rr-req" name="requirement" maxlength="300" rows="4" required placeholder="e.g. Crew time onboard on the current contract no more than 10 months"></textarea><span class="note" id="rr-chars">0 / 300</span></div>
<div class="rr-row2"><div class="rr-f"><span class="rr-l" id="rr-when">When (month / year)</span><div class="rr-inline"><select name="month" aria-labelledby="rr-when">{''.join(f'<option value="{i}">{dt.date(2000, i, 1).strftime("%b")}</option>' for i in range(1, 13))}</select><select name="year" aria-label="Year"></select></div></div>
<div class="rr-f"><label class="rr-l" for="rr-vt">Vessel type <span class="note">(optional)</span></label><select id="rr-vt" name="vessel_type"><option value="">Not stated</option>{''.join(f'<option value="{k}">{v}</option>' for k, v in RR_VT)}</select></div></div>
<fieldset class="rr-rules"><legend>Posting rules</legend>
<label class="rr-chk"><input type="checkbox" name="rule_docs" required> No confidential documents or copied text (SIRE/CDI reports, charterer emails).</label>
<label class="rr-chk"><input type="checkbox" name="rule_names" required> No vessel, person or company names.</label></fieldset>
<button class="btn rr" type="submit">Submit for review</button><p class="rr-msg" id="rr-form-msg" role="status" hidden></p>
<p class="note rr-small">Reviewed by a bot check, then by the editor. Your name and email are never shown.</p></form>
<div class="card rr-card" id="rr-mine" hidden><h2 class="sm" style="margin-top:0">Your reports</h2><ul class="rr-mine"></ul></div></div>
{RR_DISCLAIMER}</div>{RR_JSON}""", scripts=RR_SCRIPTS)

page("admin.html", "Moderation", full_title="Moderation · Vetting Radar", stats=False, csp="session", head='<meta name="robots" content="noindex,nofollow">',
     body=f"""<section class="pagehead"><div class="wrap"><p class="kicker">Admin</p><h1>Reader reports moderation</h1><p>Admins only. Step 1: bot check (pending). Step 2: publish (bot-approved).</p></div></section>
<div class="wrap page" id="rr-admin">{RR_SOON}
{rr_join("Admin sign-in", "Only e-mails on the admin list can moderate.")}
<div class="notice" id="rr-denied" hidden>This account is not on the admin list.</div>
<div id="rr-queue" hidden><div class="rr-who note"></div>
<h2 class="sm">Step 2 · Ready to publish <span class="rr-qn"></span></h2><p class="note">Passed the bot check. Approve publishes the report.</p><div class="rr-q" id="rr-q2"></div>
<h2 class="sm">Step 1 · Waiting for bot check <span class="rr-qn"></span></h2><p class="note">Approve here passes the check manually; it still needs step 2.</p><div class="rr-q" id="rr-q1"></div></div></div>{RR_JSON}""", scripts=RR_SCRIPTS)

# ---------- calendar ----------
def evrow(c):
    d = fmt_date(c["date"]) + (f" – {fmt_date(c['end'])}" if c.get("end") else "")
    past = c["date"] and (c.get("end") or c["date"]) < TODAY.isoformat()[:len(c["date"])]
    return f"""<div class="card ev {'past' if past else ''}"><div class="d">{d or 'TBA'}</div><div><b>{e(c['title'])}</b> <span class="pill">{e(c['kind'])}</span>
<div class="note src-id">{orglogo(c['owner'], 0, 'sm')}<span>{e(c['owner'])}{(' · ' + e(c['note'])) if c.get('note') else ''}</span></div><div class="src"><a href="{e(c['source_url'])}" rel="noopener">Source</a> · verified {fmt_date(c['verified_on'])}</div></div></div>"""
dated = sorted([c for c in calendar if c["date"]], key=lambda c: c["date"])
up = [c for c in dated if (c.get("end") or c["date"]) >= TODAY.isoformat()[:len(c["date"])]]
past = [c for c in dated if c not in up]
tba = [c for c in calendar if not c["date"]]
page("calendar.html", "Vetting deadlines & campaigns calendar", pagehead("Calendar", "Key dates", "Effective dates, launches, campaigns and consultation deadlines, each linked to its source.") + f"""<div class="wrap page">
<h2 class="sm" style="margin-top:0">Upcoming &amp; ongoing</h2><div class="cal">{''.join(map(evrow, up))}</div>
<h2 class="sm">Announced, no date yet</h2><div class="cal">{''.join(map(evrow, tba))}</div>
<h2 class="sm">Recent past</h2><div class="cal">{''.join(map(evrow, reversed(past)))}</div></div>""")

# ---------- sources ----------
rows = ""
for s in sorted(sources, key=lambda s: (s["category"], s["owner"], s["name"])):
    st = state.get(s["id"], {})
    status = '<span class="pill err">fetch error</span>' if st.get("last_error") else ('<span class="pill ok">watching</span>' if st.get("hash") else '<span class="pill">pending</span>')
    rows += f"""<tr data-cat="{e(s['category'])}"><td><a href="{e(s['url'])}" rel="noopener">{e(s['name'])}</a>{('<div class="note">' + e(s['note']) + '</div>') if s.get('note') else ''}</td>
<td><span class="src-id">{orglogo(s['owner'], 0, 'sm')}<span>{e(s['owner'])}</span></span></td><td>{e(CAT.get(s['category'], s['category']))}</td><td>{e(s['type'])}</td><td>{status}</td>
<td class="note">{e(st.get('last_checked','')[:16].replace('T',' '))}</td><td class="note">verified {e(s['verified_at'])}</td></tr>"""
cats = sorted({s["category"] for s in sources})
page("sources.html", "Sources watched", pagehead("Sources", f"{len(sources)} public sources, checked daily", "Each page or PDF is fetched, its text hashed and compared with the last snapshot.") + f"""<div class="wrap page">
<div class="controls"><input id="sq" type="search" placeholder="Search sources…"><select id="sc"><option value="">All categories</option>{''.join(f'<option value="{c}">{e(CAT.get(c,c))}</option>' for c in cats)}</select></div>
<p class="note">Showing <b id="src-count">{len(sources)}</b> · Machine-readable: <a href="data/sources.json">sources.json</a></p>
<div class="tablewrap"><table id="src"><thead><tr><th>Source</th><th>Published by</th><th>Category</th><th>Type</th><th>Status</th><th>Last checked (Athens)</th><th>URL verified</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<script>document.addEventListener('DOMContentLoaded',()=>vrFilter('src','sq','sc','cat'));</script>""")

# ---------- newsletter ----------
issues = []
for md in sorted(glob.glob(P("newsletter", "issue-*.md"))):
    raw = open(md).read()
    fm = {}
    m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
    if m:
        for ln in m.group(1).splitlines():
            k, _, v = ln.partition(":"); fm[k.strip()] = v.strip().strip('"')
        raw = raw[m.end():]
    # {{update:<id>}} shortcodes render the structured update card
    cards = {}
    def _sc(m):
        k = f"VRCARD{len(cards)}X"; cards[k] = ucard(UPD_BY_ID[m.group(1)], depth=1); return f"\n\n{k}\n\n"
    raw = re.sub(r"\{\{update:([\w-]+)\}\}", _sc, raw)
    body = markdown.markdown(raw, extensions=["tables", "md_in_html"])
    for k, v in cards.items(): body = body.replace(f"<p>{k}</p>", v).replace(k, v)
    name = os.path.basename(md)[:-3]
    issues.append((name, fm))
    page(f"newsletter/{name}.html", fm.get("title", name), f'<div class="wrap page prose issue">{body}{signup_card}</div>', depth=1)
    if not PREVIEW: open(P("newsletter", name + ".html"), "w").write(open(os.path.join(DIST, "newsletter", name + ".html")).read().replace('href="../', 'href="../dist/').replace(GOATCOUNTER, ""))
arch = "".join(f'<li><a class="row" href="newsletter/{n}.html"><span class="badge org">#{e(fm.get("issue",""))}</span><span class="t">{e(fm.get("title", n))}</span><time>{fmt_date(fm.get("date",""))}</time></a></li>' for n, fm in reversed(issues))
page("newsletter.html", "Newsletter", pagehead("Newsletter", "The weekly brief", "What changed in vetting rules, who it affects and the dates ahead. Five minutes, every item sourced.") + f"""<div class="wrap page grid"><div>
<h2 class="sm" style="margin-top:0">Archive</h2><ul class="card list">{arch}</ul><p class="note" style="margin-top:14px">Issues are also sent and archived on <a href="{BEEHIIV_URL}" rel="noopener">Beehiiv</a>.</p></div><aside class="side">{signup_card}</aside></div>""")

# ---------- sponsor ----------
page("sponsor.html", "Sponsor Vetting Radar", pagehead("Sponsor", "Sponsor Vetting Radar", "Reach the people who prepare tankers for SIRE 2.0, CDI and oil-major vetting.") + """<div class="wrap page prose">
<div class="notice">Placeholder page. Packages and prices are not live yet; no bookings are being taken.</div>
<p>Vetting Radar is read by people who prepare tankers for SIRE 2.0, CDI and oil-major vetting: vetting managers, marine &amp; technical superintendents, DPAs, QHSE teams and masters.</p>
<h2>Planned placements</h2><ul><li><b>Newsletter sponsor</b>: one clearly labelled slot per weekly issue.</li><li><b>Comparison table sponsor</b>: "Sponsored by" line above the who-requires-what table, monthly.</li><li><b>Calendar sponsor</b>: logo on the calendar page, monthly.</li></ul>
<h2>Editorial independence</h2><p>Sponsors never influence which changes are reported or how criteria are summarised. Sponsored content is always labelled. We do not accept sponsorship from organisations whose rules we track (e.g. OCIMF members' vetting departments, terminals) for placements next to their own criteria.</p>
<p>Interested? Contact details will be published soon.</p></div>""")

# ---------- about ----------
page("about.html", "About & disclaimer", pagehead("About", "About Vetting Radar", "Independent, free and built only from public documents.") + f"""<div class="wrap page prose">
<p>Vetting Radar is an independent, free tracker of public tanker-vetting rulebooks. It watches {len(sources)} public pages and documents (OCIMF, CDI, RightShip, oil-major clearance pages, terminal and port notices, PSC MoUs, INTERTANKO public news, IMO) and reports what changed, with a link and date on every data point.</p>
<h2>Who runs Vetting Radar</h2><p>Vetting Radar is run by Orestis Perilis, a Tanker Vetting Manager. It's an independent personal project built on public sources only, and isn't affiliated with or endorsed by any employer, oil major, terminal or vetting scheme.</p>
<h2>Contact</h2><p>Questions, suggestions or something we should track? Email {CONTACT_LINK}. For corrections to a specific item, see <a href="#corrections">Corrections</a> below.</p>
<h2>How it works</h2><ol><li>A script fetches each source, extracts the text (PDFs via pdftotext), stores a snapshot and a SHA-256 hash.</li>
<li>On the next run it diffs against the last snapshot. Any change creates a change record with the diff excerpt.</li>
<li>A human reviews each change, writes a one-paragraph summary, and decides whether it goes into the feed and newsletter.</li></ol>
<h2>Disclaimer</h2>
<div class="notice"><p style="margin-top:0"><b>Independent.</b> Vetting Radar is not affiliated with, endorsed by or speaking for OCIMF, CDI, RightShip, INTERTANKO, any oil major, terminal, port authority, PSC regime or employer.</p>
<p><b>Public information only.</b> Content is compiled solely from publicly available documents. No confidential SIRE/CDI reports, inspection data, charterer correspondence or employer information is used or accepted.</p>
<p><b>No advice, no guarantee.</b> Summaries can be incomplete or out of date; charterers and terminals apply their criteria case by case and may change them without notice. Nothing here is legal, commercial or technical advice.</p>
<p><b>Logos.</b> Logos are trademarks of their respective owners, used only to identify the source. Vetting Radar is independent and not endorsed by them.</p>
<p style="margin-bottom:0"><b>Verify at source.</b> Every item links to its source and shows the date it was verified. Always check the source before acting.</p></div>
<h2 id="corrections">Corrections</h2><p>Spotted an error or a stale value? Email <a href="mailto:customer@vettingradar.com?subject=Correction">customer@vettingradar.com</a> (subject "Correction").</p></div>""")

# ---------- static assets & data ----------
for f in ("style.css", "home.css", "app.js", "reports.js", "lookup.js", "lessons.css", "lessons.js"): shutil.copy(P("site", f), os.path.join(DIST, f))
# reader reports config: VR_SUPABASE_URL / VR_SUPABASE_ANON_KEY (+ optional VR_TURNSTILE_SITE_KEY, VR_VOTE_FUNCTION) override site/config.js
if os.environ.get("VR_SUPABASE_URL") and os.environ.get("VR_SUPABASE_ANON_KEY"):
    _cfg = {"SUPABASE_URL": os.environ["VR_SUPABASE_URL"], "SUPABASE_ANON_KEY": os.environ["VR_SUPABASE_ANON_KEY"],
            "TURNSTILE_SITE_KEY": os.environ.get("VR_TURNSTILE_SITE_KEY", ""), "VOTE_FUNCTION": os.environ.get("VR_VOTE_FUNCTION", "") in ("1", "true")}
    open(os.path.join(DIST, "config.js"), "w").write("window.VR_CONFIG = " + json.dumps(_cfg) + ";\n")
else:
    shutil.copy(P("site", "config.js"), os.path.join(DIST, "config.js"))
shutil.copytree(P("site", "brand"), os.path.join(DIST, "brand"), dirs_exist_ok=True)
shutil.copytree(P("assets", "logos"), os.path.join(DIST, "assets", "logos"), dirs_exist_ok=True, ignore=shutil.ignore_patterns("manifest.json"))
shutil.copy(P("site", "brand", "favicon.ico"), os.path.join(DIST, "favicon.ico"))
os.makedirs(os.path.join(DIST, "data"), exist_ok=True)
# public changes feed: unreviewed entries are reduced to "change detected" metadata (no diff text, no draft summary)
pub_changes = []
for c in changes:
    keep = {k: c.get(k) for k in ("id", "source_id", "source_name", "owner", "category", "url", "detected_at", "reviewed", "publish")}
    if _pub(c): keep.update(summary=c.get("summary"), significance=c.get("significance"))
    pub_changes.append(keep)
with open(os.path.join(DIST, "data", "changes.json"), "w") as f: json.dump(pub_changes, f, indent=2, ensure_ascii=False)
for f in ("comparison.json", "comparison.csv", "compare_pages.json", "updates.json", "calendar.json", "lookup.json"):
    if os.path.exists(P("data", f)): shutil.copy(P("data", f), os.path.join(DIST, "data", f))
shutil.copy(P("sources.json"), os.path.join(DIST, "data", "sources.json"))
# local review only: VR_SEED_PREVIEW=1 copies the (unpublished, git-ignored) seed reports for ?demo=1 on localhost
_seed = P("supabase", "seed_editor_reports.json")
if os.environ.get("VR_SEED_PREVIEW") == "1" and os.path.exists(_seed): shutil.copy(_seed, os.path.join(DIST, "data", "seed_preview.json"))
elif os.path.exists(os.path.join(DIST, "data", "seed_preview.json")): os.remove(os.path.join(DIST, "data", "seed_preview.json"))

# ---------- safety lessons (after static assets: the toolbox PDFs are printed from the built pages) ----------
for _old in glob.glob(os.path.join(DIST, "lessons", "*")) + glob.glob(os.path.join(DIST, "_preview", "*")): os.remove(_old)
for _f in ("lessons.html", "lessons-policy.html", os.path.join("data", "lessons.json")):
    if os.path.exists(os.path.join(DIST, _f)): os.remove(os.path.join(DIST, _f))
if LESSONS:
    # SIRE 2.0 lesson pages + toolbox talks first (lessons/ was just cleared), so their PDF links are known when the hub lists them
    _rs = {"pages": 0, "pdfs": 0, "cards": []}
    if SIRE_LOTW:
        _rs = SL.build({"page": page, "e": e, "fmt_date": fmt_date, "icon": icon, "DIST": DIST, "SITE_URL": SITE_URL, "logo": logo, "pmou": PSC_REF,
                        "chrome": CHROME, "pdf_ok": bool(CHROME), "head": lambda d: f'<link rel="stylesheet" href="{"../" * d}lessons.css">'}, SIRE_VIS, PREVIEW)
        print(f"SIRE 2.0 lessons: {_rs['pages']} rendered, {_rs['pdfs']} toolbox PDFs" + (" [PREVIEW]" if PREVIEW else ""))
    _r = LS.build({"extra_cards": _rs["cards"], "extra_chapters": sorted({q["q"].split(".")[0] for l in (SIRE_VIS if SIRE_LOTW else []) for q in l["sire_questions"]}),"page": page, "e": e, "fmt_date": fmt_date, "icon": icon, "DIST": DIST, "P": P, "signup_card": signup_card, "SITE_URL": SITE_URL,
                   "pagehead": pagehead, "logo": logo, "pmou": PSC_REF, "chrome": CHROME, "pdf_ok": bool(CHROME),
                   "head": lambda d: f'<link rel="stylesheet" href="{"../" * d}lessons.css">'}, LESSONS, PREVIEW, LOTW)
    # homepage: any toolbox PDF that could not be printed -> link the printable page instead, with its label
    _ix = os.path.join(DIST, "index.html"); _t = open(_ix).read()
    for _l in LESSONS + (SIRE_VIS if SIRE_LOTW else []):
        if not os.path.exists(os.path.join(DIST, "lessons", _l["id"] + "-toolbox.pdf")):
            _t = re.sub(r'(<a [^>]*href="lessons/' + re.escape(_l["id"]) + r'-toolbox\.)pdf("[^>]*>(?:<svg.*?</svg>)?)' + re.escape(LS.TOOLBOX_LABEL) + '</a>',
                        lambda m: m.group(1) + "html" + m.group(2) + LS.TOOLBOX_LABEL_HTML + "</a>", _t)
            _t = _t.replace(f'lessons/{_l["id"]}-toolbox.pdf', f'lessons/{_l["id"]}-toolbox.html')
    open(_ix, "w").write(_t)
    print(f"safety lessons: {_r['pages']} rendered ({sum(1 for l in LESSONS if not LS.is_pub(l))} drafts), {_r['pdfs']} toolbox PDFs" + (" [PREVIEW]" if PREVIEW else ""))
else:
    print(f"safety lessons: none published ({len(LESSONS_ALL)} drafts in data/lessons.json; run with --preview to review them)")
# old homepage mockups (home-options branch, review only): never ship stale copies left in dist/
for _old in ("home-a.html", "home-b.html", "home-c.html", "home-options.css"):
    if os.path.exists(os.path.join(DIST, _old)): os.remove(os.path.join(DIST, _old))
print("built", sorted(os.listdir(DIST)))
