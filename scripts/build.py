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
NAV = [("index.html","Latest"),("table.html","Who requires what"),("calendar.html","Calendar"),("sources.html","Sources"),
       ("newsletter.html","Newsletter"),("sponsor.html","Sponsor"),("about.html","About")]

def fmt_date(s):
    if not s: return ""
    try:
        if len(s) == 7: return dt.datetime.strptime(s, "%Y-%m").strftime("%b %Y")
        return dt.date.fromisoformat(s[:10]).strftime("%d %b %Y")
    except Exception: return s

def page(fname, title, body, desc="Independent tracker of tanker vetting rulebook changes: SIRE 2.0, OCIMF, CDI, RightShip, oil-major and terminal criteria.", depth=0):
    pre = "../" * depth
    nav = "".join(f'<a href="{pre}{h}" class="{"on" if h==os.path.basename(fname) else ""}">{l}</a>' for h, l in NAV)
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · Vetting Radar</title><meta name="description" content="{e(desc)}"><link rel="stylesheet" href="{pre}style.css">
<link rel="alternate" type="application/json" href="{pre}data/changes.json"></head><body>
<header class="site"><div class="wrap"><a class="brand" href="{pre}index.html"><span class="dot"></span>Vetting Radar</a><nav class="main">{nav}</nav></div></header>
{body}
<footer class="site"><div class="wrap"><div>Vetting Radar is independent and not affiliated with OCIMF, CDI, RightShip, INTERTANKO, any oil major, terminal or employer. Public sources only — <b>always verify at source</b>.</div>
<div>Built {TODAY.isoformat()} · <a href="{pre}about.html">About & disclaimer</a></div></div></footer>
<script src="{pre}app.js"></script></body></html>"""
    path = os.path.join(DIST, fname); os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(doc)

signup = """<div class="card signup"><h3 style="margin-top:0">Get the weekly change log</h3>
<p class="note">One email a week: what changed in SIRE, CDI, TMSA, oil-major and terminal criteria, with the source links.</p>
<form onsubmit="alert('Newsletter signup is not live yet (placeholder).');return false;"><input type="email" placeholder="you@company.com" aria-label="Email">
<button class="btn" type="submit">Subscribe (coming soon)</button></form>
<p class="note">Placeholder: will be connected to a newsletter provider at launch. No data is collected yet.</p></div>"""
sponsor_box = """<div class="card"><span class="tag minor">Sponsor slot</span><h3 style="margin:6px 0">Reach tanker vetting & marine assurance teams</h3>
<p class="note">One sponsor per issue and one on the comparison table. <a href="sponsor.html">Details →</a></p></div>"""

# ---------- index ----------
ok_sources = sum(1 for s in sources if state.get(s["id"], {}).get("hash"))
last_run = runlog.get("run_at", "")
def _pub(c): return bool(c.get("reviewed") and c.get("publish"))
# Raw monitor feed: unreviewed changes only say "a change was detected" + source link; summaries appear only once reviewed & published.
auto = "".join(f"""<div class="card item"><div class="meta"><span class="tag auto">{'Reviewed' if _pub(c) else 'Auto-detected · unreviewed'}</span><span>{fmt_date(c['detected_at'])}</span><span>{e(c['owner'])}</span></div>
<h3>Change detected: {e(c['source_name'])}</h3><p>{e(c['summary']) if _pub(c) and c.get('summary') else 'The monitor detected a text change on this source. Not yet reviewed &mdash; check the source directly.'}</p>
<div class="src"><a href="{e(c['url'])}" rel="noopener">Source</a> · detected {e(c['detected_at'][:16].replace('T',' '))}</div></div>""" for c in changes[:10])
if not auto:
    auto = f"""<div class="card item"><div class="meta"><span class="tag auto">Monitor</span><span>{fmt_date(last_run)}</span></div>
<h3>Baseline captured for {ok_sources} sources</h3><p>The change monitor has stored a first snapshot and hash for every reachable source. From the next run onward, any text change will appear here automatically with a diff excerpt.</p></div>"""
ed = "".join(f"""<div class="card item"><div class="meta"><span class="tag {e(u['significance'])}">{e(u['significance'])}</span><span>{fmt_date(u['date'])}</span><span>{e(u['owner'])}</span></div>
<h3>{e(u['title'])}</h3><p>{e(u['summary'])}</p><div class="src"><a href="{e(u['source_url'])}" rel="noopener">Source</a> · verified {fmt_date(u['verified_on'])}</div></div>""" for u in sorted(updates, key=lambda u: u["date"], reverse=True))
nxt = [c for c in calendar if c["date"] and len(c["date"]) == 10 and (c.get("end") or c["date"]) >= TODAY.isoformat()]
nxt_html = "".join(f'<li><b>{fmt_date(c["date"])}</b> — {e(c["title"])}</li>' for c in sorted(nxt, key=lambda c: c["date"])[:5])
page("index.html", "Latest vetting rule changes", f"""
<section class="hero"><div class="wrap"><h1>Every tanker vetting rulebook, watched for changes.</h1>
<p>SIRE 2.0 &amp; OCIMF, CDI, TMSA, RightShip, oil-major clearance criteria, terminal notices and PSC campaigns — tracked, diffed and summarised with a source link and date on every item.</p>
<div class="stats"><div class="stat"><b>{len(sources)}</b><span>public sources watched</span></div><div class="stat"><b>{len(comp['rows'])}</b><span>owners in the comparison table</span></div>
<div class="stat"><b>{len(changes)}</b><span>auto-detected changes since baseline</span></div><div class="stat"><b>{fmt_date(last_run) or '—'}</b><span>last monitor run</span></div></div></div></section>
<main><div class="wrap grid"><div><h2>Change monitor</h2><div class="feed">{auto}</div>
<h2>Recent rule changes (reviewed)</h2><div class="feed">{ed}</div></div>
<aside class="side"><h2>Next dates</h2><div class="card"><ul style="margin:0;padding-left:18px">{nxt_html}</ul><p class="note"><a href="calendar.html">Full calendar →</a></p></div>
{signup}{sponsor_box}</aside></div></main>""")

# ---------- table ----------
def cell(v):
    return e(v) if v else '<span class="blank">not stated in source</span>'
types = sorted({r["owner_type"] for r in comp["rows"]})
trs = ""
for r in comp["rows"]:
    links = f'<a href="{e(r["source_url"])}" rel="noopener">Primary source</a>' + "".join(f'<br><a href="{e(u)}" rel="noopener">Source {i+2}</a>' for i, u in enumerate(r["extra_source_urls"]))
    flag = f'<span class="flag">⚠ {e(r["flags"])}</span>' if r["flags"] else ""
    trs += f"""<tr data-type="{e(r['owner_type'])}"><td class="owner"><b>{e(r['requirement_owner'])}</b><br><span class="pill">{e(r['owner_type'])}</span>
<div class="note" style="margin-top:6px">{e(r['document'])}{(' · dated ' + e(r['document_date'])) if r['document_date'] else ''}</div>{flag}</td>
<td class="wide">{cell(r['age_limits'])}</td><td class="wide">{cell(r['sire_report_age'])}</td><td class="wide">{cell(r['cap_rules'])}</td><td class="wide">{cell(r['other_criteria'])}</td>
<td>{links}<div class="note">Verified {fmt_date(r['verified_on'])}</div><div class="note">Verify at source</div></td></tr>"""
gaps = "".join(f"<li><b>{e(g['owner'])}</b>: {e(g['note'])}</li>" for g in comp["not_found_publicly"])
page("table.html", "Who requires what — tanker vetting criteria compared", f"""
<main><div class="wrap"><h1 style="margin-top:0">Who requires what</h1>
<p>Public tanker acceptance criteria from oil majors, terminals, port authorities and vetting schemes, side by side. Built <b>only</b> from the cited public documents; a field is left blank when the source does not state it.</p>
<div class="notice">Summaries, not legal text. Owners apply criteria case by case and change them without notice. <b>Always verify at the linked source before relying on any value.</b></div>
<div class="controls"><input id="q" type="search" placeholder="Search: e.g. CAP 2, 20 years, crew matrix, LNG…"><select id="t"><option value="">All owner types</option>{''.join(f'<option>{e(t)}</option>' for t in types)}</select></div>
<p class="note">Showing <b id="cmp-count">{len(comp['rows'])}</b> of {len(comp['rows'])} · Download <a href="data/comparison.csv">CSV</a> · <a href="data/comparison.json">JSON</a></p>
<div class="tablewrap"><table id="cmp"><thead><tr><th>Requirement owner</th><th>Vessel age limits</th><th>Required SIRE / inspection age</th><th>CAP / condition assessment</th><th>Other notable criteria</th><th>Source &amp; date</th></tr></thead><tbody>{trs}</tbody></table></div>
<h2>Not covered yet</h2><ul>{gaps}</ul></div></main>
<script>document.addEventListener('DOMContentLoaded',()=>vrFilter('cmp','q','t','type'));</script>""")

# ---------- calendar ----------
def evrow(c):
    d = fmt_date(c["date"]) + (f" – {fmt_date(c['end'])}" if c.get("end") else "")
    past = c["date"] and (c.get("end") or c["date"]) < TODAY.isoformat()[:len(c["date"])]
    return f"""<div class="card ev {'past' if past else ''}"><div class="d">{d or 'TBA'}</div><div><b>{e(c['title'])}</b> <span class="pill">{e(c['kind'])}</span>
<div class="note">{e(c['owner'])}{(' · ' + e(c['note'])) if c.get('note') else ''}</div><div class="src"><a href="{e(c['source_url'])}" rel="noopener">Source</a> · verified {fmt_date(c['verified_on'])}</div></div></div>"""
dated = sorted([c for c in calendar if c["date"]], key=lambda c: c["date"])
up = [c for c in dated if (c.get("end") or c["date"]) >= TODAY.isoformat()[:len(c["date"])]]
past = [c for c in dated if c not in up]
tba = [c for c in calendar if not c["date"]]
page("calendar.html", "Vetting deadlines & campaigns calendar", f"""<main><div class="wrap"><h1 style="margin-top:0">Calendar</h1>
<p>Effective dates, launches, consultation deadlines and inspection campaigns. Each entry links to the source that states the date.</p>
<h2>Upcoming &amp; ongoing</h2><div class="cal">{''.join(map(evrow, up))}</div>
<h2>Announced, no date yet</h2><div class="cal">{''.join(map(evrow, tba))}</div>
<h2>Recent past</h2><div class="cal">{''.join(map(evrow, reversed(past)))}</div></div></main>""")

# ---------- sources ----------
rows = ""
for s in sorted(sources, key=lambda s: (s["category"], s["owner"], s["name"])):
    st = state.get(s["id"], {})
    status = '<span class="pill err">fetch error</span>' if st.get("last_error") else ('<span class="pill ok">watching</span>' if st.get("hash") else '<span class="pill">pending</span>')
    rows += f"""<tr data-cat="{e(s['category'])}"><td><a href="{e(s['url'])}" rel="noopener">{e(s['name'])}</a>{('<div class="note">' + e(s['note']) + '</div>') if s.get('note') else ''}</td>
<td>{e(s['owner'])}</td><td>{e(CAT.get(s['category'], s['category']))}</td><td>{e(s['type'])}</td><td>{status}</td>
<td class="note">{e(st.get('last_checked','')[:16].replace('T',' '))}</td><td class="note">verified {e(s['verified_at'])}</td></tr>"""
cats = sorted({s["category"] for s in sources})
page("sources.html", "Sources watched", f"""<main><div class="wrap"><h1 style="margin-top:0">Sources watched</h1>
<p>{len(sources)} public pages and PDFs. Each is fetched on a schedule; the text is extracted (PDFs via pdftotext), hashed and diffed against the previous snapshot. Suggest a source by email once the newsletter is live.</p>
<div class="controls"><input id="sq" type="search" placeholder="Search sources…"><select id="sc"><option value="">All categories</option>{''.join(f'<option value="{c}">{e(CAT.get(c,c))}</option>' for c in cats)}</select></div>
<p class="note">Showing <b id="src-count">{len(sources)}</b> · Machine-readable: <a href="data/sources.json">sources.json</a></p>
<div class="tablewrap"><table id="src"><thead><tr><th>Source</th><th>Owner</th><th>Category</th><th>Type</th><th>Status</th><th>Last checked (Athens)</th><th>URL verified</th></tr></thead><tbody>{rows}</tbody></table></div></div></main>
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
    body = markdown.markdown(raw, extensions=["tables"])
    name = os.path.basename(md)[:-3]
    issues.append((name, fm))
    page(f"newsletter/{name}.html", fm.get("title", name), f'<main><div class="wrap prose">{body}</div></main>', depth=1)
    open(P("newsletter", name + ".html"), "w").write(open(os.path.join(DIST, "newsletter", name + ".html")).read().replace('href="../', 'href="../dist/'))
arch = "".join(f'<li><a href="newsletter/{n}.html">{e(fm.get("title", n))}</a> <span class="note">{e(fm.get("date",""))}</span></li>' for n, fm in reversed(issues))
page("newsletter.html", "Newsletter", f"""<main><div class="wrap grid"><div><h1 style="margin-top:0">The Vetting Radar newsletter</h1>
<p>A short weekly email: what changed in vetting rulebooks, why it matters on board and in the office, and the dates coming up. Every item links to its source.</p>
<h2>Archive</h2><ul>{arch}</ul></div><aside class="side">{signup}</aside></div></main>""")

# ---------- sponsor ----------
page("sponsor.html", "Sponsor Vetting Radar", """<main><div class="wrap prose"><h1 style="margin-top:0">Sponsor Vetting Radar</h1>
<div class="notice">Placeholder page. Packages and prices are not live yet; no bookings are being taken.</div>
<p>Vetting Radar is read by people who prepare tankers for SIRE 2.0, CDI and oil-major vetting: vetting managers, marine &amp; technical superintendents, DPAs, QHSE teams and masters.</p>
<h2>Planned placements</h2><ul><li><b>Newsletter sponsor</b>: one clearly labelled slot per weekly issue.</li><li><b>Comparison table sponsor</b>: "Sponsored by" line above the who-requires-what table, monthly.</li><li><b>Calendar sponsor</b>: logo on the calendar page, monthly.</li></ul>
<h2>Editorial independence</h2><p>Sponsors never influence which changes are reported or how criteria are summarised. Sponsored content is always labelled. We do not accept sponsorship from organisations whose rules we track (e.g. OCIMF members' vetting departments, terminals) for placements next to their own criteria.</p>
<p>Interested? Contact details will be published at launch.</p></div></main>""")

# ---------- about ----------
page("about.html", "About & disclaimer", f"""<main><div class="wrap prose"><h1 style="margin-top:0">About Vetting Radar</h1>
<p>Vetting Radar is an independent, free tracker of public tanker-vetting rulebooks. It watches {len(sources)} public pages and documents (OCIMF, CDI, RightShip, oil-major clearance pages, terminal and port notices, PSC MoUs, INTERTANKO public news, IMO) and reports what changed, with a link and date on every data point.</p>
<h2>How it works</h2><ol><li>A script fetches each source, extracts the text (PDFs via pdftotext), stores a snapshot and a SHA-256 hash.</li>
<li>On the next run it diffs against the last snapshot. Any change creates a change record with the diff excerpt.</li>
<li>A human reviews each change, writes a one-paragraph summary, and decides whether it goes into the feed and newsletter.</li></ol>
<h2>Disclaimer</h2>
<div class="notice"><p style="margin-top:0"><b>Independent.</b> Vetting Radar is not affiliated with, endorsed by or speaking for OCIMF, CDI, RightShip, INTERTANKO, any oil major, terminal, port authority, PSC regime, or the editor's employer.</p>
<p><b>Public information only.</b> Content is compiled solely from publicly available documents. No confidential SIRE/CDI reports, inspection data, charterer correspondence or employer information is used or accepted.</p>
<p><b>No advice, no guarantee.</b> Summaries can be incomplete or out of date; owners apply their criteria case by case and may change them without notice. Nothing here is legal, commercial or technical advice.</p>
<p style="margin-bottom:0"><b>Verify at source.</b> Every item links to its source and shows the date it was verified. Always check the source before acting.</p></div>
<h2>Corrections</h2><p>Spotted an error or a stale value? A corrections address will be published at launch; corrections are logged publicly.</p></div></main>""")

# ---------- static assets & data ----------
for f in ("style.css", "app.js"): shutil.copy(P("site", f), os.path.join(DIST, f))
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
