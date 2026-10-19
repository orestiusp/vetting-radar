"""SIRE 2.0 lessons: one anonymised SIRE 2.0 observation a week, explained with the public OCIMF SIRE 2.0 Question Library
guidance and the publications it references. Same look as the incident safety lessons, in the indigo "sire" accent.
Records with "illustrative": true are examples built from typical SIRE 2.0 findings (not a real inspection) and say so on every page.

Data: data/sire_lessons.json. Published only with reviewed=true AND publish=true; `build.py --preview` also renders drafts
(with the "Draft - awaiting review" badge). Records with "placeholder": true are layout stand-ins and are never published.
Anonymised: never a vessel name, IMO, operator, inspector, inspecting company, port or date; never the observation verbatim.
"""
import json, os, re, subprocess
import lessons as LS

REQUIRED = ["id", "title", "topic", "ship_type_label", "summary3", "why_it_matters", "inspector_looks_for", "root_causes", "key_lessons", "check_on_board",
            "sire_questions", "source_line", "guidance", "guidance_url", "checked_on"]

def is_pub(l): return bool(l.get("reviewed") and l.get("publish") and not l.get("placeholder"))

def load(path, preview):
    data = json.load(open(path)) if os.path.exists(path) else {"lessons": []}
    allx = data.get("lessons", [])
    return allx, [l for l in allx if preview or is_pub(l)]

def check(lessons, pmou_codes=None):
    w = []
    for l in lessons:
        lid = l.get("id", "?")
        if l.get("placeholder"): w.append(f"{lid}: placeholder content (preview only, never published)")
        for f in REQUIRED:
            if not l.get(f): w.append(f"{lid}: missing {f}")
        for q in l.get("sire_questions", []):
            if not l.get("placeholder") and not re.fullmatch(r"\d+\.\d+\.\d+", q.get("q", "")): w.append(f"{lid}: check SIRE 2.0 question number {q.get('q')}")
        for c in l.get("psc_codes", []):
            if not re.fullmatch(r"\d{5}", c) or (pmou_codes and c not in pmou_codes): w.append(f"{lid}: check PSC code {c}")
        if not 4 <= len(l.get("check_on_board", [])) <= 6: w.append(f"{lid}: 'What to check on board' should have 4 to 6 items")
        ours = " ".join([l.get("title", ""), l.get("summary3", "")] + l.get("why_it_matters", []) + l.get("key_lessons", []) + l.get("check_on_board", []))
        if re.search(r"\bowners?\b", ours, re.I): w.append(f"{lid}: says 'owner' - use charterer, oil major, terminal or ship operator")
        if re.search(r"\bIMO\s?\d{7}\b|\b(?:19|20)\d{2}-\d{2}-\d{2}\b", ours): w.append(f"{lid}: possible IMO number or date in our text")
    return w

def of_week(vis, today):
    c = [l for l in vis if l.get("sire_lesson_of_week") and l["sire_lesson_of_week"] <= today.isoformat()]
    return max(c, key=lambda l: l["sire_lesson_of_week"]) if c else None

def qtags(l, e, n=None): return "".join(f'<span class="stag">SIRE {e(q["q"])}</span>' for q in l["sire_questions"][:n])
def rtags(l, e, n=None): return "".join(f'<span class="rtag">{e(r["label"])}</span>' for r in [r for r in l.get("refs", []) if r.get("chip", True)][:n])
def ptags(l, e, n=None): return "".join(f'<span class="ptag">PMoU {e(c)}</span>' for c in l.get("psc_codes", [])[:n])
def draft(l): return '' if is_pub(l) else ('<span class="draftb">Placeholder content</span>' if l.get("placeholder") else '<span class="draftb">Draft – awaiting review</span>')

def hub_card(l, e, tb):
    """Card for the Safety lessons hub (lessons.html): same .lcard as incident lessons, indigo via .sire; works with the hub filters."""
    h, lab = tb
    k = " ".join(l["why_it_matters"] + l["key_lessons"] + l["check_on_board"] + ["sire 2.0 observation", "vetting"]).lower()
    return (f'<article class="card lcard sire" data-topic="{e(LS.slug(l["topic"]))}" data-vt="all-tankers" data-sire="{e(" ".join(sorted({q["q"].split(".")[0] for q in l["sire_questions"]}, key=int)))}" '
            f'data-src="sire-observation" data-k="{e(k)}"><div class="top"><span class="cat">SIRE 2.0 · {e(l["topic"])}</span><span class="badge who">{e(l["ship_type_label"])}</span>{draft(l)}</div>'
            f'<h3><a href="lessons/{e(l["id"])}.html">{e(l["title"])}</a></h3><p class="sum">{e(l["summary3"])}</p>'
            f'<div class="tags">{qtags(l, e)}{rtags(l, e, 3)}{ptags(l, e, 1)}</div>'
            f'<div class="lfoot"><span>{e(l["source_line"])}</span><span class="lf-i"><span class="sep" aria-hidden="true">·</span>'
            f'<a href="{e(h)}" data-goatcounter-click="dl-toolbox-{e(l["id"])}" data-goatcounter-title="Toolbox talk">{e(lab)}</a></span></div></article>')

def build(ctx, vis, preview):
    """Render lessons/<id>.html and lessons/<id>-toolbox.html (+ .pdf) for each visible SIRE 2.0 lesson."""
    page, e, fmt_date, icon, DIST, SITE_URL, head = ctx["page"], ctx["e"], ctx["fmt_date"], ctx["icon"], ctx["DIST"], ctx["SITE_URL"], ctx["head"]
    os.makedirs(os.path.join(DIST, "lessons"), exist_ok=True)
    pdf_n, cards = 0, []
    for l in vis:
        lid = l["id"]
        qline = ", ".join(f'{q["q"]} {q["title"]}' for q in l["sire_questions"])
        meta = " · ".join(x for x in [f'Topic: {e(l["topic"])}', e(l["ship_type_label"]), "SIRE 2.0: " + e(qline),
                                      ("Refs: " + ", ".join(e(r["label"]) for r in l.get("refs", []))) if l.get("refs") else "",
                                      ("PSC (Paris MoU): " + ", ".join(e(c) for c in l["psc_codes"])) if l.get("psc_codes") else ""] if x)
        li = lambda xs, n=5: "".join(f"<li>{e(x)}</li>" for x in xs[:n])
        qs = "".join(f"<li>{e(q)}</li>" for q in l.get("discussion_questions", [])[:4])
        rows = "".join("<tr><td></td><td></td><td></td></tr>" for _ in range(8))
        refs_full = "; ".join(r.get("full") or r["label"] for r in l.get("refs", []))
        src_note = l.get("source_note") or "The vessel, operator, inspector, inspecting company, port and date are withheld, and the observation is paraphrased, not quoted."
        # ---- one-page toolbox talk ----
        sheet = f"""<div class="tbt-bg sire"><div class="tbt-bar noprint wrap"><a href="{e(lid)}.html">← Back to the lesson</a>
<span><button class="btn sm" type="button" data-print data-goatcounter-click="print-toolbox-{e(lid)}" data-goatcounter-title="Print toolbox talk">Print / Save as PDF</button>
{f'<a class="btn sm light" href="{e(lid)}-toolbox.pdf" data-goatcounter-click="dl-toolbox-{e(lid)}" data-goatcounter-title="Toolbox talk PDF">{LS.TOOLBOX_LABEL}</a>' if ctx.get("pdf_ok") else ''}</span></div>
<div class="sheet"><div class="sh"><span class="b">{ctx["logo"]("t")}Vetting Radar</span><span class="t">Toolbox talk · SIRE 2.0 observation · 10 min</span></div>
<h1>{e(l['title'])}</h1><p class="sub">{meta} {draft(l)}</p>
<h2>What the inspector observed</h2><div class="three">{e(l['summary3'])}</div>
<div class="cols2"><div><h2>Why it matters</h2><ul>{li(l['why_it_matters'], 3)}</ul></div>
<div><h2>Why it happens</h2><ul>{li(l['root_causes'], 4)}</ul></div></div>
{f'<h2>Discuss with your team</h2><ol class="q">{qs}</ol>' if qs else ''}
<h2>Check on board this week</h2><div class="box"><ul class="checklist">{li(l['check_on_board'], 6)}</ul></div>
<h2>Attendance</h2><table class="att"><tr><th style="width:42%">Name</th><th style="width:24%">Rank</th><th>Signature</th></tr>{rows}</table>
<div class="sign"><div>Led by:</div><div>Date / place:</div><div>Master's signature:</div></div>
<div class="foot"><b>Source:</b> {e(l['source_line'])}. {e(src_note)} <b>Guidance:</b> {e(l['guidance'])}, question {e(qline)}; see also {e(", ".join(r["label"] for r in l.get("refs", [])))}. {e(l['guidance_url'])}<br>
This sheet is Vetting Radar's own summary to support discussion. It is not OCIMF guidance, not legal advice and not a substitute for your company's SMS. {SITE_URL.replace('https://', '')}/lessons/{e(lid)}.html · free to print and share on board · checked {fmt_date(l['checked_on'])}{' · DRAFT, NOT PUBLISHED' if not is_pub(l) else ''}</div>
</div></div>"""
        tbf = f"lessons/{lid}-toolbox.html"
        page(tbf, "Toolbox talk: " + l["title"], sheet, depth=1, section="lessons.html", head=head(1),
             desc=f"One-page toolbox talk for an onboard safety meeting: {l['title']}", scripts='<script src="../lessons.js"></script>')
        pdf = os.path.join(DIST, "lessons", lid + "-toolbox.pdf")
        if ctx.get("pdf_ok"):
            try:
                subprocess.run([ctx["chrome"], "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                                "--virtual-time-budget=3000", f"--print-to-pdf={pdf}", "file://" + os.path.join(DIST, tbf)], check=True, capture_output=True, timeout=90)
                with open(pdf, "rb") as fh: ok = fh.read(5) == b"%PDF-"
                if not ok or os.path.getsize(pdf) < 5000: raise ValueError("output is not a usable PDF")
                pdf_n += 1
            except Exception as ex:
                print("SIRE toolbox PDF failed for", lid, type(ex).__name__, "- falling back to the print page")
                if os.path.exists(pdf): os.remove(pdf)
        has_pdf = os.path.exists(pdf)
        if not has_pdf:  # no dead Download link on the sheet
            t = open(os.path.join(DIST, tbf)).read()
            open(os.path.join(DIST, tbf), "w").write(re.sub(r'<a class="btn sm light" href="[^"]*-toolbox\.pdf"[^>]*>' + re.escape(LS.TOOLBOX_LABEL) + '</a>', "", t))
        tbh, tbl = (f"{lid}-toolbox.pdf", LS.TOOLBOX_LABEL) if has_pdf else (f"{lid}-toolbox.html", LS.TOOLBOX_LABEL_HTML)
        # ---- lesson page ----
        maprows = "".join(f'<tr><td>SIRE 2.0</td><td><span class="stag">{e(q["q"])}</span></td><td>{e(q["title"])}</td></tr>' for q in l["sire_questions"])
        maprows += "".join(f'<tr><td>Publication</td><td><span class="rtag">{e(r["label"])}</span></td><td>{e(r.get("full", ""))}</td></tr>' for r in l.get("refs", []))
        maprows += "".join(f'<tr><td>PSC</td><td><span class="ptag">Paris MoU {e(c)}</span></td><td>{e(ctx["pmou"].get(c, ""))} (indicative)</td></tr>' for c in l.get("psc_codes", []))
        body = f"""<section class="pagehead safe-head sire"><div class="wrap"><p class="kicker"><a href="../lessons.html">Safety lessons</a> › SIRE 2.0 observation › {e(l['topic'])}</p>
<h1>{e(l['title'])}</h1><div class="metaline"><span class="badge who">{e(l['ship_type_label'])}</span><span class="badge who">{"Illustrative" if l.get("illustrative") else "Anonymised"} SIRE 2.0 observation</span>{draft(l)}</div></div></section>
<div class="wrap page sire"><div class="lesson-grid"><div><article class="card lbody">
<h2>What the inspector observed</h2><div class="three">{e(l['summary3'])}</div>
<h2>Why it matters</h2><ul>{li(l['why_it_matters'], 8)}</ul>
<h2>Why it happens (typical root causes)</h2><ul>{li(l['root_causes'], 8)}</ul>
<h2>What the inspector will look for</h2><p class="note">Our paraphrase of the SIRE 2.0 Question Library guidance for {e(", ".join(q["q"] for q in l["sire_questions"]))}. Read the full text in the Question Library.</p><ul>{li(l['inspector_looks_for'], 8)}</ul>
<h2>Key lessons</h2><ul>{li(l['key_lessons'], 8)}</ul>
<h2>What to check on board</h2><ul class="checklist">{li(l['check_on_board'], 6)}</ul>
<h2>Mapping to SIRE 2.0, publications and PSC</h2><div class="mapwrap"><table class="maptable"><tr><th>Scheme</th><th>Reference</th><th>Meaning</th></tr>{maprows}</table></div>
<p class="disc">Question number per the OCIMF SIRE 2.0 Question Library v1.0 (Part 1). Publications are those the Question Library cites for this question, updated where IMO has since revised them. The guidance above is our paraphrase, not OCIMF text; mapping and wording are Vetting Radar's.</p>
<h2>Source</h2><div class="srcbox"><b>{e(l['source_line'])}</b>. {e(src_note)}<br>
<a href="{e(l['guidance_url'])}" rel="noopener">{e(l['guidance'])}</a>, question {e(qline)}. Publications: {e(refs_full)}.<br>
<span class="srcnote">Our summary, in our own words. Checked {fmt_date(l['checked_on'])}. Not legal advice and not OCIMF guidance. <a href="../lessons-policy.html">How we write safety lessons</a> · Spotted an error? <a href="mailto:customer@vettingradar.com?subject=SIRE%202.0%20lesson%20correction:%20{e(lid)}">customer@vettingradar.com</a></span></div>
<div class="btnrow"><a class="btn" href="{e(tbh)}" data-goatcounter-click="dl-toolbox-{e(lid)}" data-goatcounter-title="Toolbox talk">{icon("todo")}{e(tbl)}</a><button class="btn light" type="button" data-copy>Copy link</button></div>
</article></div>
<aside class="side"><div class="card sbox"><h3>Use this in a meeting</h3><p>Print the one-page toolbox talk: the observation, why it matters, discussion questions, a checklist and an attendance list. Free, no sign-up.</p><a class="btn sm" href="{e(tbh)}" data-goatcounter-click="dl-toolbox-{e(lid)}" data-goatcounter-title="Toolbox talk">{e(tbl)}</a></div>
<div class="card sbox"><h3>About SIRE 2.0 lessons</h3><p>One SIRE 2.0 observation a week, in our own words, explained with the public Question Library guidance. Examples are illustrative or fully anonymised: no vessel, company, inspector or port is named.</p><a href="../lessons-policy.html">How we write lessons</a></div>
</aside></div></div>"""
        page(f"lessons/{lid}.html", l["title"], body, depth=1, section="lessons.html", head=head(1), desc=l["summary3"][:300],
             full_title=f"{l['title']} · SIRE 2.0 lessons · Vetting Radar", scripts='<script src="../lessons.js"></script>')
        cards.append(hub_card(l, e, (f"lessons/{tbh}", tbl)))
    return {"pages": len(vis), "pdfs": pdf_n, "cards": cards}
