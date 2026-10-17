#!/usr/bin/env python3
"""Build the static Vetting Radar site into dist/ from data/*.json, sources.json and newsletter/*.md."""
import json, os, shutil, html, datetime as dt, re, glob
import markdown

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
CAT = {"sire":"SIRE / OCIMF","tmsa":"TMSA","cdi":"CDI","vetting-criteria":"Vetting schemes","oil-major":"Oil majors","terminal":"Terminals & ports",
       "psc":"Port State Control","industry":"Industry bodies","news":"OCIMF news","regulation":"IMO"}
NAV = [("updates.html","Updates"),("table.html","Compare"),("calendar.html","Calendar"),("sources.html","Sources"),("newsletter.html","Newsletter")]
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
        return dt.date.fromisoformat(s[:10]).strftime("%d %b %Y")
    except Exception: return s

def page(fname, title, body, desc="Vetting Radar tracks public tanker vetting rules (SIRE 2.0/OCIMF, CDI, RightShip, oil-major and terminal criteria) daily and shows what changed, with the source.", depth=0, full_title=None, section=None, head="", scripts=""):
    pre = "../" * depth
    doc_title = full_title or f"{title} · Vetting Radar"
    base = os.path.basename(fname)
    nav = "".join(f'<a href="{pre}{h}"{" class=\"on\" aria-current=\"page\"" if h==base else (" class=\"on\"" if h==section else "")}>{l}</a>' for h, l in NAV)
    sub_href = f"{pre}index.html#subscribe"
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(doc_title)}</title><meta name="description" content="{e(desc)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="Vetting Radar"><meta property="og:title" content="{e(doc_title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{SITE_URL}/brand/og-image.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Vetting Radar: Know what changed before your next screening.">
<meta property="og:url" content="{SITE_URL}/{'' if fname=='index.html' else fname}">
<link rel="icon" href="{pre}brand/favicon.svg" type="image/svg+xml"><link rel="icon" href="{pre}brand/favicon-32.png" sizes="32x32" type="image/png"><link rel="icon" href="{pre}brand/favicon-16.png" sizes="16x16" type="image/png">
<link rel="apple-touch-icon" href="{pre}brand/apple-touch-icon.png">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{SITE_URL}/brand/og-image.png"><meta name="twitter:title" content="{e(doc_title)}"><meta name="twitter:description" content="{e(desc)}"><meta name="theme-color" content="#0b1a2c"><link rel="stylesheet" href="{pre}style.css">
<link rel="alternate" type="application/json" href="{pre}data/changes.json">{head}
<script type="text/javascript" async src="https://subscribe-forms.beehiiv.com/attribution.js"></script></head><body>
<a class="skip" href="#content">Skip to content</a>
<header class="site"><div class="wrap"><a class="brand" href="{pre}index.html" aria-label="Vetting Radar home">{logo("h")}<span>Vetting <span class="r">Radar</span></span></a>
<nav class="main" aria-label="Main">{nav}</nav><a class="btn sm" href="{sub_href}">Subscribe</a></div></header>
<main id="content">{body}</main>
<footer class="site"><div class="wrap"><div class="cols">
<div><a class="brand" href="{pre}index.html" style="margin-bottom:10px">{logo("f")}<span>Vetting <span class="r">Radar</span></span></a><p style="margin:0;max-width:420px">Independent tracker of public tanker vetting rules. Not affiliated with OCIMF, CDI, RightShip, any oil major, terminal or employer. Summaries only. <b style="color:#fff">Always verify at source.</b></p><p class="tm">Logos are trademarks of their respective owners, used only to identify the source. Vetting Radar is independent and not endorsed by them.</p></div>
<div><h4>Product</h4><ul><li><a href="{pre}updates.html">Updates</a></li><li><a href="{pre}table.html">Compare requirements</a></li><li><a href="{pre}compare-checklist.html">Pre-screening checklist</a></li><li><a href="{pre}compare-terminals.html">Terminal requirements</a></li><li><a href="{pre}reports.html">Reader reports</a></li><li><a href="{pre}calendar.html">Calendar</a></li><li><a href="{pre}newsletter.html">Newsletter</a></li></ul></div>
<div><h4>About</h4><ul><li><a href="{pre}about.html">About &amp; disclaimer</a></li><li><a href="{pre}sources.html">Sources</a></li><li><a href="{pre}sponsor.html">Sponsor</a></li><li><a href="{pre}data/comparison.csv">Data (CSV)</a></li></ul></div>
</div><div class="fine"><span>© {TODAY.year} Vetting Radar · Public sources only</span><span>Last built {fmt_date(TODAY.isoformat())}</span></div></div></footer>
<script src="{pre}app.js"></script>{scripts}</body></html>"""
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

def pagehead(kicker, title, lede):
    return f'<section class="pagehead"><div class="wrap"><p class="kicker">{kicker}</p><h1>{title}</h1><p>{lede}</p></div></section>'

SITE_URL = "https://vettingradar.com"
BEEHIIV_URL = "https://vetting-radar.beehiiv.com"
BEEHIIV_SUBSCRIBE = BEEHIIV_URL + "/subscribe"
signup = f"""<div class="signup" id="subscribe-form"><div class="bh-form"><script async src="https://subscribe-forms.beehiiv.com/v3/loader.js" data-beehiiv-form="3413678f-3b46-449d-a13a-1341817dd862"></script></div>
<p class="note bh-fallback"><a href="{BEEHIIV_SUBSCRIBE}" rel="noopener">Subscribe on Beehiiv</a> · free, unsubscribe any time.</p></div>"""
signup_card = f'<div class="card signup" style="padding:10px 12px" id="subscribe">{signup}</div>'

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
pending = [c for c in changes if not _pub(c)]
rows_html = "".join(f"""<li><a class="row" href="updates.html#{e(u['id'])}"><span class="lc-logo">{orglogo(u['owner'], fixed=True)}</span>
<span class="t">{e(u['headline'])}<small><span class="badge {e(u['impact'])}"><span class="dot"></span>{e(u['impact'].title())}</span> {e(u['owner'])}</small></span><time datetime="{e(u['date'])}">{fmt_date(u['date'])}</time></a></li>""" for u in UPD[:5])
mon = (f'{icon("pulse")}<span>{len(pending)} change{"s" if len(pending)!=1 else ""} detected by the monitor, awaiting review. <a href="updates.html#monitor">View</a></span>' if pending
       else f'{icon("check")}<span>Monitor checked {ok_sources} sources on {fmt_date(last_run)}. No unreviewed changes.</span>')
nxt = sorted([c for c in calendar if c["date"] and len(c["date"]) == 10 and (c.get("end") or c["date"]) >= TODAY.isoformat()], key=lambda c: c["date"])
def calic(d):
    x = dt.date.fromisoformat(d); return f'<span class="cal-ic" aria-hidden="true"><span class="m">{x.strftime("%b")}</span><span class="d">{x.day}</span></span>'
dates_html = "".join(f"""<li class="card date">{calic(c['date'])}<div><b>{e(c['title'])}</b><span class="src-id">{orglogo(c['owner'], 0, 'xs', fixed=True)}{fmt_date(c['date'])}{(' – ' + fmt_date(c['end'])) if c.get('end') else ''}</span></div></li>""" for c in nxt[:3])
nk = nxt[0] if nxt else None
up_key = [c for c in nxt if c["date"] > TODAY.isoformat()]
nk = up_key[0] if up_key else nk
HERO_H1 = "Know what changed before your next screening."
HERO_SUB = "We watch OCIMF, CDI, RightShip, oil-major and terminal criteria every day, and tell you what changed, with the source."
page("index.html", "Home", desc=HERO_SUB, full_title="Vetting Radar · " + HERO_H1.rstrip("."), body=f"""
<section class="hero"><div class="wrap"><div>
<span class="eyebrow"><span class="pulse"></span>Tanker vetting intelligence</span>
<h1>{HERO_H1}</h1><p class="sub">{HERO_SUB}</p>
<div class="ctas"><a class="btn" href="#subscribe">{icon("mail")}Get the weekly brief</a><a class="btn ghost" href="table.html">Compare requirements {icon("arrow")}</a></div></div>
<div class="panel" aria-label="Monitor status"><h2>{icon("radar")}Monitor status</h2>
<div class="kpis"><div class="kpi"><b>{len(sources)}</b><span>sources watched</span></div><div class="kpi"><b>{len(comp['rows'])}</b><span>owners compared</span></div>
<div class="kpi"><b>{len(updates)}</b><span>reviewed updates</span></div><div class="kpi"><b>{dt.date.fromisoformat(last_run[:10]).strftime('%d %b') if last_run else '—'}</b><span>last check</span></div></div>
{f'<div class="nextup">{icon("calendar")}<span>Next: <b>{e(nk["title"])}</b> · {fmt_date(nk["date"])}</span></div>' if nk else ''}</div>
</div></section>
<section><div class="wrap"><div class="tiles">
<a class="card tile" href="updates.html"><span class="ic">{icon("bell")}</span><h3>Change alerts</h3><p>Rule changes from OCIMF, CDI, RightShip and oil majors, in plain words.</p><span class="go">See updates {icon("arrow")}</span></a>
<a class="card tile" href="table.html"><span class="ic">{icon("columns")}</span><h3>Who requires what</h3><p>Age, SIRE and CAP limits side by side, with sources.</p><span class="go">Compare {icon("arrow")}</span></a>
<a class="card tile" href="calendar.html"><span class="ic">{icon("calendar")}</span><h3>Key dates</h3><p>Effective dates, launches, campaigns and consultation deadlines.</p><span class="go">Open calendar {icon("arrow")}</span></a>
</div></div></section>
<section class="block"><div class="wrap two">
<div><div class="sechead"><div><p class="kicker">Reviewed</p><h2>Latest changes</h2></div><a href="updates.html">See all updates →</a></div>
<div class="card"><ul class="list">{rows_html}</ul><div class="monitor-note">{mon}</div></div></div>
<div><div class="sechead"><div><p class="kicker">Coming up</p><h2>Next dates</h2></div><a href="calendar.html">Calendar →</a></div><ul class="dates">{dates_html}</ul></div>
</div></section>
<div class="wrap"><div class="trust" role="list"><span role="listitem">{icon("radar")}{len(sources)} sources watched daily</span><span role="listitem">{icon("link")}Every item linked to its source</span><span role="listitem">{icon("shield")}Independent</span></div></div>
<section class="block" style="padding-top:8px" id="subscribe"><div class="wrap"><div class="subscribe">
<div><p class="kicker">Free weekly brief</p><h2>One email. Every vetting rule change.</h2><p style="margin:0">Read in five minutes, every item sourced.</p>
<ul><li>{icon("check")}What changed and who it affects</li><li>{icon("check")}Key numbers and what to do</li><li>{icon("check")}Dates coming up</li></ul></div>
<div class="formbox">{signup}</div></div></div></section>
""")

# ---------- updates ----------
mon_items = "".join(f"""<div class="card item"><div class="meta"><span class="tag auto">{'Reviewed' if _pub(c) else 'Detected · unreviewed'}</span><span>{fmt_date(c['detected_at'])}</span><span>{e(c['owner'])}</span></div>
<h3>Change detected: {e(c['source_name'])}</h3><p class="note">{e(c['summary']) if _pub(c) and c.get('summary') else 'Not yet reviewed. Check the source directly.'}</p>
<div class="src"><a href="{e(c['url'])}" rel="noopener">Source</a></div></div>""" for c in changes[:20])
if not mon_items:
    mon_items = f'<div class="card item"><div class="meta"><span class="tag auto">Monitor</span><span>{fmt_date(last_run)}</span></div><h3>No unreviewed changes</h3><p class="note">{ok_sources} sources checked. New text changes appear here first, then as reviewed updates.</p></div>'
legend = "".join(f'<span><i style="background:var(--c-{k})"></i>{v}</span>' for k, v in GROUP_LABEL.items())
page("updates.html", "Vetting rule updates", pagehead("Updates", "Vetting rule changes, in plain words",
     "Each update: what changed, who it affects, the key numbers and the source. Impact levels are our editorial view.") + f"""
<div class="wrap page"><div class="grid"><div><div class="legend" aria-label="Category colours">{legend}</div><div class="ucards">{''.join(ucard(u) for u in UPD)}</div></div>
<aside class="side"><div id="monitor"><h2 class="sm" style="margin-top:0">Monitor feed</h2><div class="feed">{mon_items}</div></div>
<h2 class="sm">Subscribe</h2>{signup_card}</aside></div></div>""")

# ---------- compare navigation ----------
CP = load(P("data", "compare_pages.json"))
CMP_TABS = [("table.html", "Requirements table", "columns"), ("compare-checklist.html", "Pre-screening checklist", "todo"),
            ("compare-frequency.html", "Inspection frequency", "calendar"), ("compare-terminals.html", "Terminals", "pin"), ("compare-crew.html", "Crew matrix", "crew"), ("reports.html", "Reader reports", "chat")]
def subnav(cur):
    return '<nav class="subnav" aria-label="Compare pages"><div class="wrap">' + "".join(
        f'<a href="{h}"{" class=\"on\" aria-current=\"page\"" if h == cur else ""}{" class=\"rrtab\"" if h == "reports.html" and h != cur else ""}>{icon(i)}{l}</a>' for h, l, i in CMP_TABS) + "</div></nav>"

# ---------- reader reports (user submitted; never official data) ----------
RR_DISCLAIMER = ('<p class="rr-disclaimer"><span class="rr-badge">User report</span> Reader reports are personal experiences shared by members. '
                 'They are not verified and do not represent the position of any oil major, terminal or organisation. Always check official requirements.</p>')
RR_SCRIPTS = '<script src="config.js"></script><script src="reports.js"></script>'
RR_SHORT = {"fujairah": "Port of Fujairah", "totalenergies": "TotalEnergies"}
RR_OWNERS = [{"id": r["id"], "name": RR_SHORT.get(r["id"]) or CP["owners"].get(r["id"], {}).get("name") or re.split(r" \(| – ", r["requirement_owner"])[0],
              "type": r["owner_type"], "href": f'table.html#row-{r["id"]}', "logo": orglogo(r["requirement_owner"], fixed=True)} for r in comp["rows"]]
RR_OWNER_IDS = {o["id"] for o in RR_OWNERS}
RR_JSON = '<script id="vr-owners" type="application/json">' + json.dumps(RR_OWNERS, ensure_ascii=False).replace("</", "<\\/") + '</script>'
def rrbox(owner_id):  # collapsed box below an owner's official criteria; reports.js fills it
    return (f'<details class="rr" id="rr-{e(owner_id)}" data-owner="{e(owner_id)}"><summary><span class="rr-badge">User report</span>'
            f'<b>Reader reports <span class="rr-n">· coming soon</span></b><span class="rr-sub">Reported by users, not official</span></summary>'
            '<div class="rr-body"><p class="rr-empty">Reader reports coming soon.</p></div>'
            '<p class="rr-fine">Personal experiences, not verified. Not official requirements.</p></details>')
RR_STRIP = ('<div class="rr-strip" id="rr-strip"><span class="rr-badge">User report</span><span><b>Reader reports</b> · Reported by users, not official. '
            '<span class="rr-strip-n">Coming soon.</span></span><a href="reports.html">See reader reports →</a></div>')

# ---------- table ----------
def cell(v):
    return e(v) if v else '<span class="blank">not stated in source</span>'
types = sorted({r["owner_type"] for r in comp["rows"]})
trs = ""
for r in comp["rows"]:
    links = f'<a href="{e(r["source_url"])}" rel="noopener">Primary source</a>' + "".join(f'<br><a href="{e(u)}" rel="noopener">Source {i+2}</a>' for i, u in enumerate(r["extra_source_urls"]))
    flag = f'<span class="flag">⚠ {e(r["flags"])}</span>' if r["flags"] else ""
    trs += f"""<tr data-type="{e(r['owner_type'])}" id="row-{e(r['id'])}" class="off-row"><td class="owner"><div style="margin-bottom:6px">{orglogo(r['requirement_owner'])}</div><b>{e(r['requirement_owner'])}</b><br><span class="pill">{e(r['owner_type'])}</span>
<div class="note" style="margin-top:6px">{e(r['document'])}{(' · dated ' + e(r['document_date'])) if r['document_date'] else ''}</div>{flag}</td>
<td class="wide">{cell(r['age_limits'])}</td><td class="wide">{cell(r['sire_report_age'])}</td><td class="wide">{cell(r['cap_rules'])}</td><td class="wide">{cell(r['other_criteria'])}</td>
<td>{links}<div class="note">Verified {fmt_date(r['verified_on'])}</div><div class="note">Verify at source</div></td></tr>
<tr class="rr-row" data-type="{e(r['owner_type'])}"><td colspan="6"><div class="rr-stick">{rrbox(r['id'])}</div></td></tr>"""
gaps = "".join(f"<li><b>{e(g['owner'])}</b>: {e(g['note'])}</li>" for g in comp["not_found_publicly"])
page("table.html", "Who requires what — tanker vetting criteria compared", f"""
""" + pagehead("Compare", "Who requires what", "Tanker acceptance criteria side by side. Built only from cited public documents; blank means the source doesn't say.") + subnav("table.html") + f"""<div class="wrap page">
<div class="notice">Summaries, not legal text. Owners apply criteria case by case and change them without notice. <b>Always verify at the linked source before relying on any value.</b></div>
<div class="controls"><input id="q" type="search" placeholder="Search: e.g. CAP 2, 20 years, crew matrix, LNG…"><select id="t"><option value="">All owner types</option>{''.join(f'<option>{e(t)}</option>' for t in types)}</select></div>
<p class="note">Showing <b id="cmp-count">{len(comp['rows'])}</b> of {len(comp['rows'])} · Download <a href="data/comparison.csv">CSV</a> · <a href="data/comparison.json">JSON</a></p>
<div class="tablewrap"><table id="cmp"><thead><tr><th>Requirement owner</th><th>Vessel age limits</th><th>Required SIRE / inspection age</th><th>CAP / condition assessment</th><th>Other notable criteria</th><th>Source &amp; date</th></tr></thead><tbody>{trs}</tbody></table></div>
<h2 class="sm">Not covered yet</h2><ul>{gaps}</ul>
<h2 class="sm">More comparisons</h2><div class="tiles mini">
<a class="card tile" href="compare-checklist.html"><span class="ic">{icon("todo")}</span><h3>Pre-screening checklist</h3><p>SIRE recency, CAP, Q88/HVPQ, crew matrix, PSC and certificates, owner by owner.</p></a>
<a class="card tile" href="compare-frequency.html"><span class="ic">{icon("calendar")}</span><h3>Inspection frequency by age</h3><p>Colour grid of inspection windows across age bands.</p></a>
<a class="card tile" href="compare-terminals.html"><span class="ic">{icon("pin")}</span><h3>Terminal requirements</h3><p>Age limits, SIRE, pre-arrival documents and escort tugs.</p></a>
<a class="card tile" href="compare-crew.html"><span class="ic">{icon("crew")}</span><h3>Crew matrix</h3><p>Officer experience, English, nationalities and matrix freshness.</p></a></div>{RR_DISCLAIMER}</div>{RR_JSON}
<script>document.addEventListener('DOMContentLoaded',()=>vrFilter('cmp','q','t','type'));</script>""", scripts=RR_SCRIPTS)

# ---------- compare sub-pages (checklist, frequency, terminals, crew) ----------
def verified_bar(extra=""):
    return (f'<div class="vbar"><span>{icon("check")}Verified {fmt_date(CP["verified_on"])} against the linked public documents</span>'
            f'<span>{icon("link")}Every value links to its source</span>{extra}</div>'
            '<div class="notice">Summaries, not legal text. Owners apply criteria case by case and change them without notice. <b>Always verify at the linked source before relying on any value.</b></div>')
OWN = CP["owners"]
def ohead(k):  # owner column header: logo + name, linked to the source
    o = OWN[k]
    return f'<th class="oh" scope="col"><a href="{e(o["url"])}" rel="noopener" title="{e(o["doc"])}">{orglogo(o["org"], fixed=True)}<span>{e(o["name"])}</span></a></th>'
def ocell(k, sub=""):  # owner row header
    o = OWN[k]; fl = f'<span class="flag">⚠ {e(o["flag"])}</span>' if o.get("flag") else ""
    return f'<th scope="row" class="orow"><div class="src-id">{orglogo(o["org"], fixed=True)}<b>{e(o["name"])}</b></div><div class="note">{e(o["doc"])}</div>{sub}{fl}</th>'
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
page("compare-checklist.html", "Pre-screening checklist: what oil majors and terminals ask for", section="table.html",
     desc="The documents and conditions commonly required for oil-major and terminal clearance (SIRE recency, CAP, Q88/HVPQ, crew matrix, PSC, certificates), owner by owner, from public sources.",
     body=pagehead("Compare", "Pre-screening checklist", "The documents and conditions most often checked before a tanker is cleared, and which owners publicly require each one.") + subnav("compare-checklist.html") + f"""
<div class="wrap page widepage"><p class="intro">Use this as a checklist before you submit a vessel for clearance: inspection recency, CAP, questionnaire and crew-matrix freshness, PSC record, certificates and TMSA. Each column is one requirement owner; the header links to the public document we read. A dash means the cited source does not say, not that there is no rule.</p>
{verified_bar()}
{lvlegend(["req","cond","ns"], LV)}
<div class="tablewrap mxwrap"><table class="mx" id="ck"><thead><tr><th class="item" scope="col">Check</th>{''.join(ohead(k) for k in ck)}</tr></thead><tbody>{rows_ck}</tbody></table></div>
<p class="note">Scroll sideways for all {len(ck)} owners. Values are short summaries; size bands, gas carriers and exceptions are in the sources and on the <a href="table.html">requirements table</a>.</p>
{RR_STRIP}<h2 class="sm">Sources</h2>{srclist(ck)}{RR_DISCLAIMER}</div>{RR_JSON}""", scripts=RR_SCRIPTS)

# b. inspection frequency by age
FQ = {"t3": "≤ 3–4 months", "t6": "≈ 6 months", "t12": "7–15 months", "scr": "Screening, no fixed interval", "no": "Not accepted", "ns": "Not stated"}
rows_fq = ""
for f in CP["frequency"]:
    tds = "".join(f'<td class="fq {lv}"><span>{e(t) if t else "—"}</span></td>' for lv, t in f["cells"])
    rows_fq += f'<tr>{ocell(f["owner"], f"<div class=\"note fqn\">{e(f["note"])}</div>" if f.get("note") else "")}{tds}</tr>'
page("compare-frequency.html", "Inspection frequency by vessel age, owner by owner", section="table.html",
     desc="How fresh a SIRE or owner inspection must be at each vessel age band, for oil majors, vetting schemes and terminals, from public sources.",
     body=pagehead("Compare", "Inspection frequency by vessel age", "How recent the SIRE or owner inspection must be as a tanker gets older, and where each owner stops accepting it.") + subnav("compare-frequency.html") + f"""
<div class="wrap page widepage"><p class="intro">Each row is one requirement owner, each column an age band. Colours show how tight the inspection window is; dark cells mean the owner's published age limit excludes the vessel. Bands are approximate: owners draw the line at slightly different ages (e.g. 10.1 or 15.1 years), so check the exact wording at source.</p>
{verified_bar()}
<div class="lvlegend fqlegend" aria-label="Legend">{''.join(f'<span><i class="fq {k}"></i>{e(v)}</span>' for k, v in FQ.items())}</div>
<div class="tablewrap mxwrap"><table class="mx fqt"><thead><tr><th scope="col">Owner</th>{''.join(f'<th scope="col" class="band">{e(b)}</th>' for b in CP["bands"])}</tr></thead><tbody>{rows_fq}</tbody></table></div>
<p class="note">Oil and chemical tankers above 5,000 dwt unless noted. Gas carriers and small tankers often have higher age limits; see the sources.</p>
{RR_STRIP}<h2 class="sm">Sources</h2>{srclist([f["owner"] for f in CP["frequency"]])}{RR_DISCLAIMER}</div>{RR_JSON}""", scripts=RR_SCRIPTS)

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
{f'<span class="flag">⚠ {e(t["flag"])}</span>' if t["flag"] else ''}<div class="tfoot">{links}<span>·</span><span>Verified {fmt_date(CP['verified_on'])}</span><span>·</span><span>Verify at source</span></div>{rrbox(rid) if rid else ''}</article>"""
page("compare-terminals.html", "Terminal requirements: age limits, SIRE, pre-arrival and escort rules", section="table.html",
     desc="Public terminal and port rules for tankers: age limits, SIRE/vetting, pre-arrival documents and escort tugs (Saudi Aramco, Fujairah, Trans Mountain, SIOT Trieste, Ceyhan, Brofjorden, Ingleside and more).",
     body=pagehead("Compare", "Terminal requirements", "What terminals publish about vessel age, SIRE or terminal vetting, pre-arrival documents and escort tugs.") + subnav("compare-terminals.html") + f"""
<div class="wrap page"><p class="intro">Terminals screen on top of the charterer's clearance. These cards summarise what each terminal's own public handbook or port notice says. Blank fields mean that document does not cover the point; other port rules or the charterer may still apply.</p>
{verified_bar()}
<div class="controls"><input id="tq" type="search" placeholder="Search terminals: e.g. escort, 25 years, Q88, H2S…"></div>
<div class="tcards" id="tcards">{tcards}</div>
<p class="note" style="margin-top:16px">Missing a terminal? Only terminals with a public document we could read are listed.</p>{RR_STRIP}{RR_DISCLAIMER}</div>{RR_JSON}
<script>document.addEventListener('DOMContentLoaded',()=>{{const q=document.getElementById('tq');q.addEventListener('input',()=>{{const v=q.value.toLowerCase().trim();document.querySelectorAll('#tcards .tcard').forEach(c=>{{c.style.display=!v||c.innerText.toLowerCase().includes(v)?'':'none'}})}})}});</script>""", scripts=RR_SCRIPTS)

# d. crew matrix
def yrs(v): return f'<td class="yr">{e(v)}</td>' if v else '<td class="yr na" title="Not stated in source">—</td>'
def txt(v): return f'<td>{e(v)}</td>' if v else '<td><span class="blank">—</span></td>'
rows_cr = ""
for c in CP["crew"]:
    rows_cr += f'<tr>{ocell(c["owner"])}{"".join(map(yrs, c["m"]))}{"".join(map(yrs, c["e"]))}{txt(c["junior"])}{txt(c["english"])}{txt(c["nat"])}{txt(c["fresh"])}{txt(c["other"])}</tr>'
none = ", ".join(OWN[k]["name"] for k in CP["crew_none"])
SUB = '<th scope="col" class="yh">Operator</th><th scope="col" class="yh">Rank</th><th scope="col" class="yh">Type</th><th scope="col" class="yh">All tankers</th>'
page("compare-crew.html", "Crew-matrix requirements compared: officer experience, English, nationalities", section="table.html",
     desc="Officer experience minimums (years with operator, in rank, on type), English, nationality limits and crew-matrix freshness, owner by owner, from public sources.",
     body=pagehead("Compare", "Crew-matrix comparison", "Senior officer experience, English, nationality limits and how fresh the crew matrix must be, by owner.") + subnav("compare-crew.html") + f"""
<div class="wrap page widepage"><p class="intro">Most owners check the OCIMF officer / crew matrix against combined ("aggregate") experience for the Master + Chief Officer and the Chief Engineer + Second (or First) Engineer. Figures are minimum years: calendar time with the operator, then sea time in rank, on the same tanker type and on all tankers. A dash means the cited source does not set that value.</p>
{verified_bar()}
<div class="tablewrap mxwrap"><table class="mx crew"><thead>
<tr><th rowspan="2" scope="col">Owner</th><th colspan="4" scope="colgroup" class="grp">Master + Chief Officer (years)</th><th colspan="4" scope="colgroup" class="grp">Chief Eng. + 2nd / 1st Eng. (years)</th><th rowspan="2" scope="col">Junior officers</th><th rowspan="2" scope="col">English</th><th rowspan="2" scope="col">Nationalities</th><th rowspan="2" scope="col">Matrix freshness</th><th rowspan="2" scope="col">Other</th></tr>
<tr>{SUB}{SUB}</tr></thead><tbody>{rows_cr}</tbody></table></div>
<p class="note">No public crew-matrix rules found in the sources reviewed for: {e(none)}. ExxonMobil values come from a 2017 edition on a third-party host and are shown for reference only.</p>
{RR_STRIP}<h2 class="sm">Sources</h2>{srclist([c["owner"] for c in CP["crew"]])}{RR_DISCLAIMER}</div>{RR_JSON}""", scripts=RR_SCRIPTS)

# ---------- reader reports pages ----------
RR_CATS = [("crew", "Crew experience"), ("vessel_age", "Vessel age"), ("inspections", "Inspections / SIRE"), ("terminal", "Terminal"), ("other", "Other")]
RR_VT = [("crude", "Crude tanker"), ("product", "Product tanker"), ("chemical", "Chemical tanker"), ("lpg", "LPG carrier"), ("lng", "LNG carrier"), ("other", "Other")]
_oopts = "".join(f'<option value="{e(o["id"])}">{e(o["name"])}</option>' for o in RR_OWNERS)
_copts = "".join(f'<option value="{k}">{v}</option>' for k, v in RR_CATS)
RR_SOON = '<div class="rr-soon card" id="rr-soon"><span class="rr-badge">User report</span><p><b>Reader reports coming soon.</b> Members will be able to share requirements they met in practice, clearly separated from official criteria.</p></div>'
def rr_join(title, lede):
    return (f'<div class="card rr-card" id="rr-join" hidden><h2>{title}</h2><p class="note">{lede}</p>'
            '<form class="rr-joinf" novalidate><label class="rr-l" for="rr-email">Email</label><div class="rr-inline"><input id="rr-email" name="email" type="email" autocomplete="email" required placeholder="you@example.com">'
            f'<button class="btn" type="submit">{icon("mail")}Email me a sign-in link</button></div><p class="rr-msg" role="status" hidden></p></form>'
            '<p class="note rr-small">No password. We use your email only to sign you in; it is never shown with your reports.</p></div>')

page("reports.html", "Reader reports: requirements members met in practice", section="table.html",
     desc="Requirements tanker people say they met in practice, shared by members, reviewed before publishing, and kept separate from official vetting criteria.",
     body=pagehead("Compare", "Reader reports", "What members met in practice. Reviewed before publishing, never official.") + subnav("reports.html") + f"""
<div class="wrap page"><div class="rr-top"><p class="intro">Each report is one member's experience with an oil major or terminal, checked by a bot and the editor before it appears. Vote if it matches yours.</p>
<a class="btn" href="submit.html">{icon("chat")}Post a report</a></div>
<div class="controls rr-filters" id="rr-filters" hidden><select id="rr-fo" aria-label="Owner"><option value="">All owners</option>{_oopts}<option value="other">Other</option></select>
<select id="rr-fc" aria-label="Category"><option value="">All categories</option>{_copts}</select>
<label class="rr-chk"><input type="checkbox" id="rr-fs"> Hide stale</label><span class="note"><b id="rr-count">0</b> reports</span></div>
<div id="rr-list">{RR_SOON}</div>
<p class="note rr-legend"><span class="rr-staletag">Stale</span> no confirmation in 12 months · <a href="table.html">Official criteria</a></p>
{RR_DISCLAIMER}</div>{RR_JSON}""", scripts=RR_SCRIPTS)

page("submit.html", "Post a reader report", section="table.html",
     desc="Share a tanker vetting requirement you met in practice. Members only, reviewed before publishing.",
     body=pagehead("Compare", "Post a reader report", "Share one requirement you met in practice. Members only, reviewed before it goes public.") + subnav("reports.html") + f"""
<div class="wrap page rr-narrow" id="rr-submit">{RR_SOON}
{rr_join("Join to post a report", "Membership is free. Enter your email and we'll send a one-time sign-in link.")}
<div id="rr-post" hidden><div class="rr-who note"></div>
<form class="card rr-card rr-form" id="rr-form" novalidate>
<div class="rr-f"><label class="rr-l" for="rr-owner">Oil major or terminal</label><select id="rr-owner" name="owner" required><option value="">Select…</option>{_oopts}<option value="other">Other</option></select></div>
<div class="rr-f" id="rr-other" hidden><label class="rr-l" for="rr-oo">Which one?</label><input id="rr-oo" name="owner_other" maxlength="60" placeholder="Oil major or terminal name"></div>
<div class="rr-f"><label class="rr-l" for="rr-cat">Category</label><select id="rr-cat" name="category" required>{_copts}</select></div>
<div class="rr-f"><label class="rr-l" for="rr-req">Requirement you faced</label><textarea id="rr-req" name="requirement" maxlength="300" rows="4" required placeholder="e.g. Crew time onboard on the current contract no more than 10 months"></textarea><span class="note" id="rr-chars">0 / 300</span></div>
<div class="rr-row2"><div class="rr-f"><span class="rr-l" id="rr-when">When (month / year)</span><div class="rr-inline"><select name="month" aria-labelledby="rr-when">{''.join(f'<option value="{i}">{dt.date(2000, i, 1).strftime("%b")}</option>' for i in range(1, 13))}</select><select name="year" aria-label="Year"></select></div></div>
<div class="rr-f"><label class="rr-l" for="rr-vt">Vessel type <span class="note">(optional)</span></label><select id="rr-vt" name="vessel_type"><option value="">Not stated</option>{''.join(f'<option value="{k}">{v}</option>' for k, v in RR_VT)}</select></div></div>
<fieldset class="rr-rules"><legend>Posting rules</legend>
<label class="rr-chk"><input type="checkbox" name="rule_docs" required> No confidential documents or copied text (SIRE/CDI reports, charterer emails).</label>
<label class="rr-chk"><input type="checkbox" name="rule_names" required> No vessel, person or company names.</label></fieldset>
<button class="btn" type="submit">Submit for review</button><p class="rr-msg" id="rr-form-msg" role="status" hidden></p>
<p class="note rr-small">Reviewed by a bot check, then by the editor. Your name and email are never shown.</p></form>
<div class="card rr-card" id="rr-mine" hidden><h2 class="sm" style="margin-top:0">Your reports</h2><ul class="rr-mine"></ul></div></div>
{RR_DISCLAIMER}</div>{RR_JSON}""", scripts=RR_SCRIPTS)

page("admin.html", "Moderation", full_title="Moderation · Vetting Radar", head='<meta name="robots" content="noindex,nofollow">',
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
<div class="tablewrap"><table id="src"><thead><tr><th>Source</th><th>Owner</th><th>Category</th><th>Type</th><th>Status</th><th>Last checked (Athens)</th><th>URL verified</th></tr></thead><tbody>{rows}</tbody></table></div></div>
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
    open(P("newsletter", name + ".html"), "w").write(open(os.path.join(DIST, "newsletter", name + ".html")).read().replace('href="../', 'href="../dist/'))
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
<h2>How it works</h2><ol><li>A script fetches each source, extracts the text (PDFs via pdftotext), stores a snapshot and a SHA-256 hash.</li>
<li>On the next run it diffs against the last snapshot. Any change creates a change record with the diff excerpt.</li>
<li>A human reviews each change, writes a one-paragraph summary, and decides whether it goes into the feed and newsletter.</li></ol>
<h2>Disclaimer</h2>
<div class="notice"><p style="margin-top:0"><b>Independent.</b> Vetting Radar is not affiliated with, endorsed by or speaking for OCIMF, CDI, RightShip, INTERTANKO, any oil major, terminal, port authority, PSC regime, or the editor's employer.</p>
<p><b>Public information only.</b> Content is compiled solely from publicly available documents. No confidential SIRE/CDI reports, inspection data, charterer correspondence or employer information is used or accepted.</p>
<p><b>No advice, no guarantee.</b> Summaries can be incomplete or out of date; owners apply their criteria case by case and may change them without notice. Nothing here is legal, commercial or technical advice.</p>
<p><b>Logos.</b> Logos are trademarks of their respective owners, used only to identify the source. Vetting Radar is independent and not endorsed by them.</p>
<p style="margin-bottom:0"><b>Verify at source.</b> Every item links to its source and shows the date it was verified. Always check the source before acting.</p></div>
<h2>Corrections</h2><p>Spotted an error or a stale value? A corrections address will be published at launch; corrections are logged publicly.</p></div>""")

# ---------- static assets & data ----------
for f in ("style.css", "app.js", "reports.js"): shutil.copy(P("site", f), os.path.join(DIST, f))
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
for f in ("comparison.json", "comparison.csv", "compare_pages.json", "updates.json", "calendar.json"):
    if os.path.exists(P("data", f)): shutil.copy(P("data", f), os.path.join(DIST, "data", f))
shutil.copy(P("sources.json"), os.path.join(DIST, "data", "sources.json"))
print("built", sorted(os.listdir(DIST)))
