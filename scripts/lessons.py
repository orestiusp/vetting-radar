"""Safety lessons: data model, checks and page rendering for scripts/build.py.

Only lessons with reviewed=true AND publish=true are published. `build.py --preview` (or VR_PREVIEW=1)
also renders drafts, each with a visible 'Draft - awaiting review' badge, for local review only.
"""
import datetime as dt, json, os, re, shutil, subprocess

# SIRE 2.0 Question Library v1.0 (OCIMF, Jan 2022) chapters and sections, titles as printed in the QL contents.
SIRE_CHAPTERS = {"1": "Vessel, Operator and Inspection Particulars", "2": "Certification and Documentation", "3": "Crew Management",
    "4": "Navigation and Communications", "5": "Safety Management", "6": "Pollution Prevention", "7": "Maritime Security",
    "8": "Cargo and Ballast Systems", "9": "Mooring and Anchoring", "10": "Machinery Spaces", "11": "General Appearance and Condition",
    "12": "Ice Operations"}
SIRE_SECTIONS = {"2.1": "Certification", "2.2": "Management Oversight", "2.3": "Structural Assessment", "2.4": "Defect Management",
    "2.5": "Management of Change", "2.6": "Statutory Management Plans", "2.7": "Safety Management System", "2.8": "General Information",
    "3.1": "Crew Qualification", "3.2": "Crew Evaluation", "3.3": "Crew Training", "3.4": "Crew Compliance", "3.5": "Crew Familiarisation",
    "4.1": "Navigation Equipment", "4.2": "Navigational Procedures", "4.3": "Bridge and Machinery Space Team Management",
    "4.4": "Communications Equipment and Procedures", "4.5": "DP & Shuttle Tanker Specialist Procedures and Equipment",
    "5.1": "Emergency Response Plans and Drills", "5.2": "Fixed Fire Protection Systems", "5.3": "Portable fire fighting appliances",
    "5.4": "Life saving appliances", "5.5": "Permits to work", "5.6": "Fixed and portable gas detecting systems", "5.7": "Safety Management",
    "5.8": "Area Safety Inspections", "5.9": "Lifting and Rigging", "5.10": "Safe Access", "5.11": "Sample Management", "5.12": "Safety Equipment",
    "6.1": "Pollution Prevention - Record Books", "6.2": "Cargo and Bunker Operations", "6.3": "Ballast Operations",
    "6.4": "Deck Area Pollution Prevention", "6.5": "Machinery Space Pollution Prevention", "6.6": "Oil Discharge Monitors",
    "7.1": "Ship Routing", "7.2": "Ship Hardening and access control", "7.3": "Communications and Monitoring", "7.4": "Ship Security Officer",
    "7.5": "Cyber Security", "8.1": "Oil", "8.2": "Chemicals", "8.3": "Oil and Chemical", "8.4": "LPG", "8.5": "LNG",
    "8.6": "Gas (common to all vessels under IGC Code)", "8.7": "Shuttle Tanker Cargo Operations", "8.8": "OBO / Combination Carriers",
    "8.99": "All types", "9.1": "Mooring Equipment Management", "9.2": "Emergency Towing Arrangement", "9.3": "Mooring and Anchoring Procedures",
    "9.4": "Mooring and Anchoring Team Management", "9.5": "STS Operation Management", "9.6": "Single Point Mooring",
    "9.7": "Shuttle Tanker Mooring Systems", "10.1": "Engineering Procedures", "10.2": "Machinery Status", "10.3": "Safety Management",
    "10.4": "Planned Maintenance Systems", "10.5": "Conventional Bunkering Management", "10.6": "LNG Bunkering Management",
    "10.7": "Fire Protection Measures"}
TOOLBOX_LABEL = "Toolbox talk (PDF)"  # one button label everywhere (hub, lesson pages, homepage, the sheet itself)
TOOLBOX_LABEL_HTML = "Toolbox talk (print)"  # only when no PDF could be made (no headless Chrome): the link then opens the printable page
TOPICS = ["Enclosed spaces", "Mooring", "Cargo & vapour", "STS", "Fire", "Bridge & navigation", "Personal safety", "Pollution", "Machinery"]
VESSELS = [("crude", "Crude oil"), ("product", "Product"), ("chemical", "Chemical"), ("LPG", "LPG"), ("LNG", "LNG"), ("other", "Transferable (other ship types)")]
SOURCE_TYPES = [("investigation body", "Investigation bodies"), ("P&I club", "P&I clubs"), ("industry body", "Industry bodies"), ("class", "Class societies")]
REQUIRED = ["id", "title", "summary3", "what_went_wrong", "root_cause", "key_lessons", "check_on_board", "sire2_tags", "vessel_types",
            "operation", "topic", "source_body", "source_type", "source_title", "source_url", "source_published", "checked_on"]
# Editorial cap: at most 2 new lessons per ISO week (a warning, never a build failure).
# Exception: the 14 lessons approved together at launch on 2026-10-19 carry "launch_batch": true and are not counted.
# Do not set launch_batch on later additions.
MAX_PER_WEEK = 2
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
_TITLE_STOP = set("""Final Report Investigation Accident Marine Brief Collision Between Sinking Fatal Fatality Allision Explosion Fire Cargo Tank Tanker
 Chemical Crude Oil Part One Two The And With From Outside On Of In At Lessons Learned Mooring Line Parting Outcome Following Board Safety Bulletin
 Incident Ship Transfer Completion Stern Trawler Frigate Terminal County Territorial Waters Singapore South China Sea Strait TSS Dutch Flagged Port
 Subsequent Waterway Dolphins Barge Towed Tug Crew Onboard Bulk Carrier Loss Lives Casebook Tankers Hazardous Contaminated Coating Club Swedish
 Hordaland Norway January February March April May June July August September October November December Report OCIMF NTSB MAIB TSIB HNoMS
 Mooring Dolphins Cargo""".split())

def is_pub(l): return bool(l.get("reviewed") and l.get("publish"))

# Editor review notes are private: data/private/ is git-ignored and never read by the live build.
# Format: {"<lesson id>": ["note", ...]}. Preview builds merge them in and show them on each lesson page.
NOTES_PATH = os.path.join("data", "private", "lessons_review_notes.json")

def load(path, preview):
    data = json.load(open(path)) if os.path.exists(path) else {"lessons": []}
    allx = data.get("lessons", [])
    for l in allx: l.pop("review_notes", None)  # never trust notes left in the public file
    if preview:
        np = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), NOTES_PATH)
        notes = json.load(open(np)) if os.path.exists(np) else {}
        for l in allx:
            if notes.get(l["id"]): l["review_notes"] = notes[l["id"]]
    vis = [l for l in allx if preview or is_pub(l)]
    return allx, sorted(vis, key=lambda l: (l.get("vr_published") or "", l.get("source_published") or ""), reverse=True)

def check(lessons, pmou_codes=None):
    """Editorial checks; returns warnings (printed by build.py). Never blocks a preview build."""
    w = []
    weeks = {}
    for l in lessons:
        lid = l.get("id", "?")
        for f in REQUIRED:
            if not l.get(f): w.append(f"{lid}: missing {f}")
        for t in l.get("sire2_tags", []):
            if t not in SIRE_SECTIONS and t not in SIRE_CHAPTERS: w.append(f"{lid}: unknown SIRE 2.0 tag {t}")
        for c in l.get("psc_codes", []):
            if not re.fullmatch(r"\d{5}", c) or (pmou_codes and c not in pmou_codes): w.append(f"{lid}: check PSC code {c}")
        if l.get("topic") not in TOPICS: w.append(f"{lid}: topic {l.get('topic')} not in list")
        if len(l.get("title", "")) > 90: w.append(f"{lid}: title over 90 chars")
        ours = " ".join([l.get("title", ""), l.get("summary3", ""), l.get("root_cause", "")] + l.get("what_went_wrong", []) + l.get("key_lessons", [])
                        + l.get("check_on_board", []) + l.get("discussion_questions", []) + [l.get("ship_type_label", ""), l.get("operation_label", "")])
        names = {t for t in re.findall(r"\b[A-Z][A-Za-z]{2,}\b", l.get("source_title", "")) if t not in _TITLE_STOP}
        for n in sorted(names):
            if re.search(rf"\b{re.escape(n)}\b", ours): w.append(f"{lid}: possible vessel/company name in our text: {n}")
        if re.search(r"\bowners?\b", ours, re.I): w.append(f"{lid}: says 'owner' - use charterer, oil major or terminal (or ship operator)")
        if is_pub(l) and l.get("vr_published") and not l.get("launch_batch"):
            y, wk, _ = dt.date.fromisoformat(l["vr_published"]).isocalendar(); weeks.setdefault((y, wk), []).append(lid)
    for k, ids in weeks.items():
        if len(ids) > MAX_PER_WEEK: w.append(f"week {k[0]}-W{k[1]:02d}: {len(ids)} lessons published (cap {MAX_PER_WEEK}): {', '.join(ids)}")
    return w

def lesson_of_week(vis, today):
    c = [l for l in vis if l.get("lesson_of_week") and l["lesson_of_week"] <= today.isoformat()]
    return max(c, key=lambda l: l["lesson_of_week"]) if c else None

def chapters(l): return sorted({t.split(".")[0] for t in l.get("sire2_tags", [])}, key=int)

def build(ctx, vis, preview, lotw):
    """Render lessons.html, lessons/<id>.html, lessons/<id>-toolbox.html (+ .pdf) and lessons-policy.html."""
    page, e, fmt_date, icon, DIST = ctx["page"], ctx["e"], ctx["fmt_date"], ctx["icon"], ctx["DIST"]
    signup_card, SITE_URL = ctx["signup_card"], ctx["SITE_URL"]
    head = ctx["head"]
    VLAB = dict(VESSELS + [("all tankers", "All tankers")])
    def draft(l): return '' if is_pub(l) else '<span class="draftb" title="Not published: awaiting editor review">Draft – awaiting review</span>'
    def stags(l, short=False):
        return "".join(f'<span class="stag">SIRE {e(t)}{"" if short else " " + e(SIRE_SECTIONS.get(t, SIRE_CHAPTERS.get(t, "")))}</span>' for t in l["sire2_tags"])
    def tagrow(l, short=False):
        return (stags(l, short) + "".join(f'<span class="ptag">PMoU {e(c)}</span>' for c in l.get("psc_codes", []))
                + "".join(f'<span class="ctag">CDI: {e(c)}</span>' for c in l.get("cdi_tags", [])))
    def toolbox_href(l, pre):
        pdf = os.path.join(DIST, "lessons", l["id"] + "-toolbox.pdf")
        return (f'{pre}lessons/{l["id"]}-toolbox.pdf', TOOLBOX_LABEL) if os.path.exists(pdf) else (f'{pre}lessons/{l["id"]}-toolbox.html', TOOLBOX_LABEL_HTML)
    def srcline(l):
        return f'{e(l["source_short"])}{" · published " + fmt_date(l["source_published"]) if l.get("source_published") else ""}'

    # ---- toolbox-talk sheets first (the PDF links depend on them) ----
    tb_files = []
    for l in vis:
        meta = " · ".join(x for x in [f'Topic: {e(l["topic"])}', e(l.get("ship_type_label", "")), e(l.get("operation_label", "")),
                                      "SIRE 2.0: " + ", ".join(e(t) for t in l["sire2_tags"]),
                                      ("PSC (Paris MoU): " + ", ".join(e(c) for c in l["psc_codes"])) if l.get("psc_codes") else ""] if x)
        qs = "".join(f"<li>{e(q)}</li>" for q in l.get("discussion_questions", [])[:4])
        rows = "".join("<tr><td></td><td></td><td></td></tr>" for _ in range(8))
        body = f"""<div class="tbt-bg"><div class="tbt-bar noprint wrap"><a href="{e(l['id'])}.html">← Back to the lesson</a>
<span><button class="btn sm" type="button" data-print data-goatcounter-click="print-toolbox-{e(l['id'])}" data-goatcounter-title="Print toolbox talk">Print / Save as PDF</button>
{f'<a class="btn sm light" href="{e(l["id"])}-toolbox.pdf" data-goatcounter-click="dl-toolbox-{e(l["id"])}" data-goatcounter-title="Toolbox talk PDF">{TOOLBOX_LABEL}</a>' if ctx.get("pdf_ok") else ''}</span></div>
<div class="sheet"><div class="sh"><span class="b">{ctx["logo"]("t")}Vetting Radar</span><span class="t">Toolbox talk · onboard safety meeting · 10 min</span></div>
<h1>{e(l['title'])}</h1><p class="sub">{meta} {draft(l)}</p>
<h2>What happened</h2><div class="three">{e(l['summary3'])}</div>
<div class="cols2"><div><h2>What went wrong</h2><ul>{''.join(f"<li>{e(x)}</li>" for x in l['what_went_wrong'][:5])}</ul></div>
<div><h2>Key lessons</h2><ul>{''.join(f"<li>{e(x)}</li>" for x in l['key_lessons'][:5])}</ul></div></div>
{f'<h2>Discuss with your team</h2><ol class="q">{qs}</ol>' if qs else ''}
<h2>Check on board this week</h2><div class="box"><ul class="checklist">{''.join(f"<li>{e(x)}</li>" for x in l['check_on_board'][:6])}</ul></div>
<h2>Attendance</h2><table class="att"><tr><th style="width:42%">Name</th><th style="width:24%">Rank</th><th>Signature</th></tr>{rows}</table>
<div class="sign"><div>Led by:</div><div>Date / place:</div><div>Master's signature:</div></div>
<div class="foot"><b>Source:</b> {e(l['source_body'])}, "{e(l['source_title'])}"{', published ' + fmt_date(l['source_published']) if l.get('source_published') else ''}. {e(l['source_url'])}<br>
This sheet is Vetting Radar's own short summary to support discussion. It is not the official report, not legal advice and not a substitute for your company's SMS. Read the full report at the source. {SITE_URL.replace('https://', '')}/lessons/{e(l['id'])}.html · free to print and share on board · checked {fmt_date(l['checked_on'])}{' · DRAFT, NOT PUBLISHED' if not is_pub(l) else ''}</div>
</div></div>"""
        f = f"lessons/{l['id']}-toolbox.html"
        page(f, "Toolbox talk: " + l["title"], body, depth=1, section="lessons.html", head=head(1),
             desc=f"One-page toolbox talk for an onboard safety meeting: {l['title']}", scripts='<script src="../lessons.js"></script>')
        tb_files.append((l, os.path.join(DIST, f)))

    # ---- PDFs by headless Chrome (optional; falls back to the print page) ----
    pdf_n = 0
    if ctx.get("pdf_ok"):
        for l, fpath in tb_files:
            out = os.path.join(DIST, "lessons", l["id"] + "-toolbox.pdf")
            try:
                subprocess.run([ctx["chrome"], "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                                "--virtual-time-budget=3000", "--blink-settings=imagesEnabled=true", f"--print-to-pdf={out}", "file://" + fpath],
                               check=True, capture_output=True, timeout=90)
                with open(out, "rb") as fh: head_ok = fh.read(5) == b"%PDF-"
                if not head_ok or os.path.getsize(out) < 5000: raise ValueError("output is not a usable PDF")
                pdf_n += 1
            except Exception as ex:
                print("toolbox PDF failed for", l["id"], type(ex).__name__, "- falling back to the print page")
                if os.path.exists(out): os.remove(out)
    # Fallback: a missing PDF must never break the deploy or leave a dead link. Drop the Download button;
    # the sheet keeps its Print / Save as PDF button, and lesson pages and the hub link the HTML sheet instead.
    for l, fpath in tb_files:
        if not os.path.exists(os.path.join(DIST, "lessons", l["id"] + "-toolbox.pdf")):
            with open(fpath) as fh: t = fh.read()
            t = re.sub(r'<a class="btn sm light" href="[^"]*-toolbox\.pdf"[^>]*>' + re.escape(TOOLBOX_LABEL) + '</a>', "", t)
            with open(fpath, "w") as fh: fh.write(t)

    # ---- lesson pages ----
    for l in vis:
        pre = "../"
        rel = [x for x in vis if x is not l and x["topic"] == l["topic"]][:3] or [x for x in vis if x is not l and set(chapters(x)) & set(chapters(l))][:3]
        maprows = "".join(f'<tr><td>SIRE 2.0</td><td><span class="stag">{e(t)} {e(SIRE_SECTIONS.get(t, SIRE_CHAPTERS.get(t, "")))}</span></td><td>Chapter {e(t.split(".")[0])}: {e(SIRE_CHAPTERS.get(t.split(".")[0], ""))}</td></tr>' for t in l["sire2_tags"])
        maprows += "".join(f'<tr><td>CDI</td><td><span class="ctag">SIR: {e(c)}</span></td><td>Chapter named, number to confirm</td></tr>' for c in l.get("cdi_tags", []))
        maprows += "".join(f'<tr><td>PSC</td><td><span class="ptag">Paris MoU {e(c)}</span></td><td>{e(ctx["pmou"].get(c, ""))} (indicative)</td></tr>' for c in l.get("psc_codes", []))
        tbh, tbl = toolbox_href(l, pre)
        notes = "".join(f"<li>{e(n)}</li>" for n in l.get("review_notes", []))
        review = (f'<div class="card sbox revbox"><h3>Editor review notes</h3><p class="note">Shown only in the preview build.</p><ul>{notes}</ul></div>' if preview and notes else "")
        ld = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": l["title"], "description": l["summary3"],
                         "datePublished": l.get("vr_published") or l.get("checked_on"), "dateModified": l.get("checked_on"),
                         "publisher": {"@type": "Organization", "name": "Vetting Radar", "url": SITE_URL},
                         "isBasedOn": l["source_url"], "url": f'{SITE_URL}/lessons/{l["id"]}.html'}, ensure_ascii=False).replace("</", "<\\/")
        body = f"""<section class="pagehead safe-head"><div class="wrap"><p class="kicker"><a href="../lessons.html">Safety lessons</a> › {e(l['topic'])}</p>
<h1>{e(l['title'])}</h1><div class="metaline"><span class="badge who">{e(l.get('ship_type_label', ''))}</span><span class="badge who">{e(l.get('operation_label', ''))}</span><span class="badge who">{e(l['source_type'].capitalize())}</span>{draft(l)}</div></div></section>
<div class="wrap page"><div class="lesson-grid"><div><article class="card lbody">
<h2>In three lines</h2><div class="three">{e(l['summary3'])}</div>
<h2>What went wrong</h2><ul>{''.join(f"<li>{e(x)}</li>" for x in l['what_went_wrong'])}</ul>
<h2>Root cause (as found by the investigators)</h2><p>{e(l['root_cause'])}</p>
<h2>Key lessons</h2><ul>{''.join(f"<li>{e(x)}</li>" for x in l['key_lessons'])}</ul>
<h2>What to check on board</h2><ul class="checklist">{''.join(f"<li>{e(x)}</li>" for x in l['check_on_board'])}</ul>
<h2>Mapping to vetting and PSC</h2><div class="mapwrap"><table class="maptable"><tr><th>Scheme</th><th>Area</th><th>Chapter / meaning</th></tr>{maprows}</table></div>
<p class="disc">Tags are Vetting Radar's editorial view, not OCIMF's, CDI's, a PSC regime's or the investigators'. SIRE 2.0 section numbers per the OCIMF Question Library v1.0; PSC codes from the Paris MoU deficiency code list.</p>
<h2>Source</h2><div class="srcbox"><b>{e(l['source_body'])}</b>: "{e(l['source_title'])}".{(' Occurred ' + fmt_date(l['occurred']) + ' ·') if l.get('occurred') else ''} Published {fmt_date(l['source_published'])} · <a href="{e(l['source_url'])}" rel="noopener">Read the full report at the source</a><br>
<span class="srcnote">Our summary, in our own words; vessel names appear only in the official report title. Checked {fmt_date(l['checked_on'])}. Not legal advice. <a href="../lessons-policy.html">How we write safety lessons</a> · Spotted an error? <a href="mailto:customer@vettingradar.com?subject=Safety%20lesson%20correction:%20{e(l['id'])}">customer@vettingradar.com</a></span></div>
<div class="btnrow"><a class="btn" href="{e(tbh)}" data-goatcounter-click="dl-toolbox-{e(l['id'])}" data-goatcounter-title="Toolbox talk">{icon("todo")}{e(tbl)}</a><a class="btn light" href="https://www.linkedin.com/sharing/share-offsite/?url={e(SITE_URL)}/lessons/{e(l['id'])}.html" rel="noopener" data-goatcounter-click="share-linkedin-{e(l['id'])}">Share on LinkedIn</a><button class="btn light" type="button" data-copy>Copy link</button></div>
</article></div>
<aside class="side">{review}
<div class="card sbox"><h3>Use this in a meeting</h3><p>Print the one-page toolbox talk: summary, discussion questions, checklist and an attendance list. Free, no sign-up.</p><a class="btn sm" href="{e(tbh)}" data-goatcounter-click="dl-toolbox-{e(l['id'])}" data-goatcounter-title="Toolbox talk">{e(tbl)}</a></div>
{f'<div class="card sbox"><h3>Related lessons</h3>' + ''.join(f'<p><a href="{e(x["id"])}.html">{e(x["title"])}</a></p>' for x in rel) + '</div>' if rel else ''}
<div class="card sbox"><h3>How we write lessons</h3><p>Our own words, linked to the official source, no vessel or company names. Every lesson is checked by a person before it is published.</p><a href="../lessons-policy.html">Read the policy</a></div>
</aside></div></div>
<script type="application/ld+json">{ld}</script>"""
        page(f"lessons/{l['id']}.html", l["title"], body, depth=1, section="lessons.html", head=head(1), desc=l["summary3"][:300],
             full_title=f"{l['title']} · Safety lessons · Vetting Radar", scripts='<script src="../lessons.js"></script>')

    # ---- hub ----
    def card(l):
        tbh, tbl = toolbox_href(l, "")
        return (f'<article class="card lcard" data-topic="{e(slug(l["topic"]))}" data-vt="{e(" ".join(slug(v) for v in l["vessel_types"]))}" '
                f'data-sire="{e(" ".join(chapters(l)))}" data-src="{e(slug(l["source_type"]))}" data-k="{e(" ".join(l["what_went_wrong"] + l["key_lessons"] + l["check_on_board"] + [l.get("operation_label", "")]).lower())}">'
                f'<div class="top"><span class="cat">{e(l["topic"])}</span><span class="badge who">{e(l.get("ship_type_label", ""))}</span>{draft(l)}</div>'
                f'<h3><a href="lessons/{e(l["id"])}.html">{e(l["title"])}</a></h3><p class="sum">{e(l["summary3"])}</p>'
                f'<div class="tags">{tagrow(l, short=True)}</div>'
                f'<div class="lfoot"><a href="{e(l["source_url"])}" rel="noopener">Source: {e(l["source_short"])}</a><span class="lf-i"><span class="sep" aria-hidden="true">·</span>Published {fmt_date(l["source_published"])}</span>'
                f'<span class="lf-i"><span class="sep" aria-hidden="true">·</span><a href="{e(tbh)}" data-goatcounter-click="dl-toolbox-{e(l["id"])}" data-goatcounter-title="Toolbox talk">{e(tbl)}</a></span></div></article>')
    used_topics = [t for t in TOPICS if any(l["topic"] == t for l in vis)]
    xcards = ctx.get("extra_cards", [])  # SIRE 2.0 lessons (sire_lessons.py), listed first, indigo
    used_ch = sorted({c for l in vis for c in chapters(l)} | set(ctx.get("extra_chapters", [])), key=int)
    used_vt = [(k, v) for k, v in VESSELS if any(k in l["vessel_types"] for l in vis)]
    used_src = [(k, v) for k, v in SOURCE_TYPES if any(l["source_type"] == k for l in vis)] + ([("sire observation", "SIRE 2.0 observations")] if xcards else [])
    pills = '<a href="lessons.html" class="on" data-topic="">All topics</a>' + "".join(f'<a href="lessons.html?topic={slug(t)}" data-topic="{slug(t)}">{e(t)}</a>' for t in used_topics)
    n_draft = sum(1 for l in vis if not is_pub(l))
    body = f"""<section class="pagehead safe-head"><div class="wrap"><p class="kicker">Safety lessons</p><h1>Learn from public incident reports, mapped to SIRE 2.0</h1>
<p>Short summaries in our own words of public accident reports and safety alerts, tagged to the SIRE 2.0 question areas, CDI chapters and PSC deficiency codes they touch. Use them for pre-vetting briefings and onboard safety meetings. Always read the linked source.</p></div></section>
<div class="wrap page">{f'<div class="notice draftnote"><b>Preview build.</b> {n_draft} draft lesson{"s" if n_draft != 1 else ""} awaiting review are shown with a "Draft – awaiting review" badge. They are not published.</div>' if n_draft else ''}
<nav class="topicbar" aria-label="Topics">{pills}</nav>
<div class="grid"><div>
<form class="card filters" id="lf" role="search"><div class="row">
<label>Search<input id="lf-q" type="search" placeholder="e.g. snap-back, gas-freeing, AIS, pilot"></label>
<label>Vessel type<select id="lf-vt"><option value="">All tankers</option>{''.join(f'<option value="{slug(k)}">{e(v)}</option>' for k, v in used_vt)}</select></label>
<input type="hidden" id="lf-topic" value="">
<label>SIRE 2.0 chapter<select id="lf-sire"><option value="">All chapters</option>{''.join(f'<option value="{c}">{c} {e(SIRE_CHAPTERS[c])}</option>' for c in used_ch)}</select></label>
<label>Source type<select id="lf-src"><option value="">All sources</option>{''.join(f'<option value="{slug(k)}">{e(v)}</option>' for k, v in used_src)}</select></label>
</div></form>
<div class="rescount"><span><b id="lf-count">{len(vis) + len(xcards)}</b> of {len(vis) + len(xcards)} lessons shown</span><button class="linkbtn" type="button" id="lf-reset" hidden>Clear filters</button></div>
<p class="note" id="lf-empty" hidden>No lessons match these filters yet. <a href="lessons.html">Show all</a>.</p>
<div class="lcards" id="lcards">{''.join(xcards)}{''.join(card(l) for l in vis)}</div></div>
<aside class="side">
<div class="card sbox"><h3>Toolbox talks, free</h3><p>Every lesson has a one-page sheet for the onboard safety meeting: what happened, discussion questions, a checklist and an attendance list. Print it or save it as a PDF. No sign-up.</p></div>
<div class="card sbox"><h3>How we tag lessons</h3><p>Each lesson is tagged to SIRE 2.0 Question Library sections (OCIMF, v1.0), CDI SIR chapters and Paris MoU deficiency codes. Tags are our editorial view, not OCIMF's, CDI's or the investigators'.</p><a href="lessons-policy.html">How we write safety lessons</a></div>
<h2 class="sm">Lesson of the week, by email</h2>{signup_card}
</aside></div></div>"""
    page("lessons.html", "Safety lessons: public incident reports for tankers, mapped to SIRE 2.0", body, head=head(0), section="lessons.html",
         desc="Short, sourced lessons from public tanker accident reports and safety alerts, tagged to SIRE 2.0 sections, CDI chapters and PSC codes, with free toolbox talks.",
         scripts='<script src="lessons.js"></script>')

    # ---- policy note ----
    page("lessons-policy.html", "How we write safety lessons", ctx["pagehead"]("Safety lessons", "How we write safety lessons", "The rules every lesson follows before it is published.", "safe-head") + f"""
<div class="wrap page prose"><ul class="policy">
<li><b>Our own words.</b> Each lesson is a short summary we write ourselves. We do not copy text, images or PDFs from the report; at most one short quote.</li>
<li><b>Always linked.</b> Every lesson links to the official report or alert at its publisher and shows the publication date and the date we last checked the link.</li>
<li><b>No names.</b> Our text does not name vessels, companies or people. Names appear only inside the official report title and link.</li>
<li><b>No blame.</b> Causes are stated as the investigators found them. Investigation reports are written to prevent accidents, not to decide blame or liability, and neither are our summaries.</li>
<li><b>Reviewed by a person.</b> A first draft may be prepared with AI assistance. Nothing is published until the editor has checked it against the source and approved it.</li>
<li><b>Tags are our view.</b> SIRE 2.0, CDI and PSC tags are our editorial mapping, not the view of OCIMF, CDI, any PSC regime or the investigators.</li>
<li><b>Not advice.</b> Lessons and toolbox talks support discussion. They are not legal or technical advice and do not replace your company's SMS or the official report.</li>
<li><b>Free to use on board.</b> Toolbox talks are free to print and share, with no sign-up.</li>
<li><b>At most two new lessons a week</b>, and one "Lesson of the week" in the newsletter.</li></ul>
<h2>Report an error</h2><p>Spotted a mistake, a broken link or a name that should not be there? Email <a href="mailto:customer@vettingradar.com?subject=Safety%20lesson%20correction">customer@vettingradar.com</a> and we will fix it.</p></div>""",
         head=head(0), section="lessons.html", desc="How Vetting Radar writes safety lessons: our own words, source links, no names, human review, not legal advice.")

    # ---- public data (published fields only; review notes only in preview) ----
    keep = [k for k in ["id", "title", "summary3", "what_went_wrong", "root_cause", "key_lessons", "check_on_board", "discussion_questions", "sire2_tags",
            "cdi_tags", "psc_codes", "vessel_types", "operation", "topic", "severity", "source_body", "source_type", "source_title", "source_url",
            "source_published", "occurred", "checked_on", "vr_published", "lesson_of_week"]]
    pub = [{**{k: l.get(k) for k in keep}, **({"reviewed": l.get("reviewed"), "review_notes": l.get("review_notes")} if preview else {})} for l in vis]
    os.makedirs(os.path.join(DIST, "data"), exist_ok=True)
    json.dump(pub, open(os.path.join(DIST, "data", "lessons.json"), "w"), indent=1, ensure_ascii=False)

    # ---- newsletter snippet: "Lesson of the week" (Markdown for the Beehiiv issue) ----
    if lotw:
        tbh, _ = toolbox_href(lotw, "")
        md = (f"## Lesson of the week\n\n**[{lotw['title']}]({SITE_URL}/lessons/{lotw['id']}.html?utm_source=newsletter&utm_medium=email&utm_campaign=lesson-of-the-week)**\n\n"
              f"{lotw['summary3']}\n\n**Check on board:**\n\n" + "".join(f"- {x}\n" for x in lotw["check_on_board"][:3])
              + f"\n[Read the lesson]({SITE_URL}/lessons/{lotw['id']}.html) · [This week's toolbox talk]({SITE_URL}/{tbh}) · Source: {lotw['source_short']}, published {fmt_date(lotw['source_published'])}\n")
        out = os.path.join(DIST, "_preview", "lesson-of-the-week.md") if preview else ctx["P"]("newsletter", "snippets", "lesson-of-the-week.md")
        os.makedirs(os.path.dirname(out), exist_ok=True); open(out, "w").write(md)
    return {"pages": len(vis), "pdfs": pdf_n}

def lotw_block(l, e, fmt_date, icon, pdf_href):
    if not l: return ""
    draft = '' if is_pub(l) else '<span class="draftb">Draft – awaiting review</span>'
    tags = "".join(f'<span class="stag">SIRE {e(t)}</span>' for t in l["sire2_tags"][:3]) + "".join(f'<span class="ptag">PMoU {e(c)}</span>' for c in l.get("psc_codes", [])[:1])
    return f"""<section class="block tight lotw-sec"><div class="wrap"><div class="sechead"><div><h2>Lesson of the week</h2><p class="note">One public incident report, in plain words, mapped to SIRE 2.0. Ready for your next safety meeting.</p></div><a href="lessons.html">All safety lessons →</a></div>
<div class="card lotw"><div class="l"><div class="top"><span class="cat">{e(l['topic'])}</span><span class="badge who">{e(l.get('ship_type_label', ''))}</span>{draft}</div>
<h3><a href="lessons/{e(l['id'])}.html">{e(l['title'])}</a></h3><p class="sum">{e(l['summary3'])}</p><div class="tags">{tags}</div>
<div class="btnrow"><a class="btn sm" href="lessons/{e(l['id'])}.html">Read the lesson</a><a class="btn sm light" href="{e(pdf_href)}" data-goatcounter-click="dl-toolbox-{e(l['id'])}" data-goatcounter-title="Toolbox talk (home)">{TOOLBOX_LABEL if pdf_href.endswith(".pdf") else TOOLBOX_LABEL_HTML}</a><span class="note">Source: <a href="{e(l['source_url'])}" rel="noopener">{e(l['source_short'])}</a>, published {fmt_date(l['source_published'])}</span></div></div>
<div class="r"><h4>What to check on board</h4><ol>{''.join(f"<li>{e(x)}</li>" for x in l['check_on_board'][:4])}</ol></div></div></div></section>"""
