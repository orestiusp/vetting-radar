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

def page(fname, title, body, desc="Vetting Radar tracks public tanker vetting rules (SIRE 2.0/OCIMF, CDI, RightShip, oil-major and terminal criteria) daily and shows what changed, with the source.", depth=0, full_title=None):
    pre = "../" * depth
    doc_title = full_title or f"{title} · Vetting Radar"
    base = os.path.basename(fname)
    nav = "".join(f'<a href="{pre}{h}"{" class=\"on\" aria-current=\"page\"" if h==base else ""}>{l}</a>' for h, l in NAV)
    sub_href = f"{pre}index.html#subscribe"
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(doc_title)}</title><meta name="description" content="{e(desc)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="Vetting Radar"><meta property="og:title" content="{e(doc_title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{SITE_URL}/brand/og-image.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Vetting Radar: Know what changed before your next screening.">
<meta property="og:url" content="{SITE_URL}/{'' if fname=='index.html' else fname}">
<link rel="icon" href="{pre}brand/favicon.svg" type="image/svg+xml"><link rel="icon" href="{pre}brand/favicon-32.png" sizes="32x32" type="image/png"><link rel="icon" href="{pre}brand/favicon-16.png" sizes="16x16" type="image/png">
<link rel="apple-touch-icon" href="{pre}brand/apple-touch-icon.png">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{SITE_URL}/brand/og-image.png"><meta name="twitter:title" content="{e(doc_title)}"><meta name="twitter:description" content="{e(desc)}"><meta name="theme-color" content="#0b1a2c"><link rel="stylesheet" href="{pre}style.css">
<link rel="alternate" type="application/json" href="{pre}data/changes.json">
<script type="text/javascript" async src="https://subscribe-forms.beehiiv.com/attribution.js"></script></head><body>
<a class="skip" href="#content">Skip to content</a>
<header class="site"><div class="wrap"><a class="brand" href="{pre}index.html" aria-label="Vetting Radar home">{logo("h")}<span>Vetting <span class="r">Radar</span></span></a>
<nav class="main" aria-label="Main">{nav}</nav><a class="btn sm" href="{sub_href}">Subscribe</a></div></header>
<main id="content">{body}</main>
<footer class="site"><div class="wrap"><div class="cols">
<div><a class="brand" href="{pre}index.html" style="margin-bottom:10px">{logo("f")}<span>Vetting <span class="r">Radar</span></span></a><p style="margin:0;max-width:420px">Independent tracker of public tanker vetting rules. Not affiliated with OCIMF, CDI, RightShip, any oil major, terminal or employer. Summaries only. <b style="color:#fff">Always verify at source.</b></p><p class="tm">Logos are trademarks of their respective owners, used only to identify the source. Vetting Radar is independent and not endorsed by them.</p></div>
<div><h4>Product</h4><ul><li><a href="{pre}updates.html">Updates</a></li><li><a href="{pre}table.html">Compare requirements</a></li><li><a href="{pre}calendar.html">Calendar</a></li><li><a href="{pre}newsletter.html">Newsletter</a></li></ul></div>
<div><h4>About</h4><ul><li><a href="{pre}about.html">About &amp; disclaimer</a></li><li><a href="{pre}sources.html">Sources</a></li><li><a href="{pre}sponsor.html">Sponsor</a></li><li><a href="{pre}data/comparison.csv">Data (CSV)</a></li></ul></div>
</div><div class="fine"><span>© {TODAY.year} Vetting Radar · Public sources only</span><span>Last built {fmt_date(TODAY.isoformat())}</span></div></div></footer>
<script src="{pre}app.js"></script></body></html>"""
    path = os.path.join(DIST, fname); os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(doc)

# ---------- organisation logos (source identifiers only) ----------
ORG_LOGOS = load(P("assets", "logos", "manifest.json"), {})
ORG_RULES = [("ocimf","ocimf"),("cdi","cdi"),("rightship","rightship"),("paris","parismou"),("tokyo","tokyomou"),("intertanko","intertanko"),
 ("adnoc","adnoc"),("repsol","repsol"),("moeve","moeve"),("cepsa","moeve"),("braskem","braskem"),("exxon","exxonmobil"),("total","totalenergies"),
 ("trans mountain","transmountain"),("fujairah","fujairah"),("uscg","uscg"),("med mou","medmou"),("iomou","iomou"),("equasis","equasis"),
 ("aramco","aramco"),("sigtto","sigtto"),("amsa","amsa"),("emsa","emsa"),("imo","imo"),("bp","bp")]
def org_keys(owner):
    o = (owner or "").lower(); keys = []
    for needle, key in ORG_RULES:
        if (needle in o if len(needle) > 3 else re.search(rf"\b{needle}\b", o)) and key not in keys: keys.append(key)
    return keys[:2]
def initials(name):
    w = [x for x in re.split(r"[\s/–-]+", name) if x and x[0].isalnum()]
    return (w[0][:3] if len(w) == 1 or w[0].isupper() and len(w[0]) <= 4 else "".join(x[0] for x in w[:2])).upper()
def orglogo(owner, depth=0, size=""):
    out = ""
    for k in org_keys(owner) or [None]:
        m = ORG_LOGOS.get(k, {}) if k else {}
        name = m.get("name") or owner
        if m.get("file"):
            out += f'<span class="olg {size}{" dark" if m.get("dark_bg") else ""}" title="{e(name)}"><img src="{"../"*depth}assets/logos/{e(m["file"])}" alt="{e(name)} logo" loading="lazy"></span>'
        else:
            out += f'<span class="olg fb {size}" title="{e(name)}" aria-label="{e(name)}">{e(initials(name))}</span>'
    return f'<span class="olgs">{out}</span>'

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
rows_html = "".join(f"""<li><a class="row" href="updates.html#{e(u['id'])}">{orglogo(u['owner'])}
<span class="t">{e(u['headline'])}<small><span class="badge {e(u['impact'])}"><span class="dot"></span>{e(u['impact'].title())}</span> {e(u['owner'])}</small></span><time datetime="{e(u['date'])}">{fmt_date(u['date'])}</time></a></li>""" for u in UPD[:5])
mon = (f'{icon("pulse")}<span>{len(pending)} change{"s" if len(pending)!=1 else ""} detected by the monitor, awaiting review. <a href="updates.html#monitor">View</a></span>' if pending
       else f'{icon("check")}<span>Monitor checked {ok_sources} sources on {fmt_date(last_run)}. No unreviewed changes.</span>')
nxt = sorted([c for c in calendar if c["date"] and len(c["date"]) == 10 and (c.get("end") or c["date"]) >= TODAY.isoformat()], key=lambda c: c["date"])
def calic(d):
    x = dt.date.fromisoformat(d); return f'<span class="cal-ic" aria-hidden="true"><span class="m">{x.strftime("%b")}</span><span class="d">{x.day}</span></span>'
dates_html = "".join(f"""<li class="card date">{calic(c['date'])}<div><b>{e(c['title'])}</b><span class="src-id">{orglogo(c['owner'], 0, 'xs')}{fmt_date(c['date'])}{(' – ' + fmt_date(c['end'])) if c.get('end') else ''}</span></div></li>""" for c in nxt[:3])
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

# ---------- table ----------
def cell(v):
    return e(v) if v else '<span class="blank">not stated in source</span>'
types = sorted({r["owner_type"] for r in comp["rows"]})
trs = ""
for r in comp["rows"]:
    links = f'<a href="{e(r["source_url"])}" rel="noopener">Primary source</a>' + "".join(f'<br><a href="{e(u)}" rel="noopener">Source {i+2}</a>' for i, u in enumerate(r["extra_source_urls"]))
    flag = f'<span class="flag">⚠ {e(r["flags"])}</span>' if r["flags"] else ""
    trs += f"""<tr data-type="{e(r['owner_type'])}"><td class="owner"><div style="margin-bottom:6px">{orglogo(r['requirement_owner'])}</div><b>{e(r['requirement_owner'])}</b><br><span class="pill">{e(r['owner_type'])}</span>
<div class="note" style="margin-top:6px">{e(r['document'])}{(' · dated ' + e(r['document_date'])) if r['document_date'] else ''}</div>{flag}</td>
<td class="wide">{cell(r['age_limits'])}</td><td class="wide">{cell(r['sire_report_age'])}</td><td class="wide">{cell(r['cap_rules'])}</td><td class="wide">{cell(r['other_criteria'])}</td>
<td>{links}<div class="note">Verified {fmt_date(r['verified_on'])}</div><div class="note">Verify at source</div></td></tr>"""
gaps = "".join(f"<li><b>{e(g['owner'])}</b>: {e(g['note'])}</li>" for g in comp["not_found_publicly"])
page("table.html", "Who requires what — tanker vetting criteria compared", f"""
""" + pagehead("Compare", "Who requires what", "Tanker acceptance criteria side by side. Built only from cited public documents; blank means the source doesn't say.") + f"""<div class="wrap page">
<div class="notice">Summaries, not legal text. Owners apply criteria case by case and change them without notice. <b>Always verify at the linked source before relying on any value.</b></div>
<div class="controls"><input id="q" type="search" placeholder="Search: e.g. CAP 2, 20 years, crew matrix, LNG…"><select id="t"><option value="">All owner types</option>{''.join(f'<option>{e(t)}</option>' for t in types)}</select></div>
<p class="note">Showing <b id="cmp-count">{len(comp['rows'])}</b> of {len(comp['rows'])} · Download <a href="data/comparison.csv">CSV</a> · <a href="data/comparison.json">JSON</a></p>
<div class="tablewrap"><table id="cmp"><thead><tr><th>Requirement owner</th><th>Vessel age limits</th><th>Required SIRE / inspection age</th><th>CAP / condition assessment</th><th>Other notable criteria</th><th>Source &amp; date</th></tr></thead><tbody>{trs}</tbody></table></div>
<h2 class="sm">Not covered yet</h2><ul>{gaps}</ul></div>
<script>document.addEventListener('DOMContentLoaded',()=>vrFilter('cmp','q','t','type'));</script>""")

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
for f in ("style.css", "app.js"): shutil.copy(P("site", f), os.path.join(DIST, f))
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
for f in ("comparison.json", "comparison.csv", "updates.json", "calendar.json"):
    if os.path.exists(P("data", f)): shutil.copy(P("data", f), os.path.join(DIST, "data", f))
shutil.copy(P("sources.json"), os.path.join(DIST, "data", "sources.json"))
print("built", sorted(os.listdir(DIST)))
