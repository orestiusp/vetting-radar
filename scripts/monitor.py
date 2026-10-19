#!/usr/bin/env python3
"""Vetting Radar change monitor.

Fetches every source in sources.json, extracts text (pdftotext for PDFs,
BeautifulSoup for HTML), stores a snapshot + SHA-256 hash, diffs against the
previous snapshot and writes a change entry (JSON) when the text changed.

Usage:  python3 scripts/monitor.py [--only ID ...] [--workers 8]
Outputs:
  snapshots/<id>/latest.txt, snapshots/<id>/<timestamp>.txt
  data/state.json            per-source hash / last checked / last changed / errors
  changes/<timestamp>-<id>.json  one file per detected change
  data/changes.json          rolling feed (newest first) used by the site
  data/run_log.json          summary of the last run
"""
import argparse, concurrent.futures as cf, datetime as dt, difflib, hashlib, json, os, re, subprocess, sys, tempfile
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 VettingRadarMonitor/0.1 (+independent, non-commercial change monitor)"}
P = lambda *a: os.path.join(ROOT, *a)

# Lines that change on every load and would cause false positives
NOISE = [re.compile(p, re.I) for p in [
    r"^\s*(copyright|©)", r"cookie", r"^\s*\d+\s*(comments?|views?)\s*$",
    r"Public Site Detention Portlet\(", r"csrf|nonce|__VIEWSTATE",
    # timestamps / relative times / pagination that change on every load
    r"printed date \d", r"^\w{3} \w{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2}",
    r"^\s*\d+\s*(minute|hour|day|week)\(?s?\)?\s+ago\s*$", r"^\s*(Connections|Users connected)\s*:", r"^\s*(read more|more)\s*[….]*\s*$",
]]

def now():
    return dt.datetime.now().astimezone()

def load(path, default):
    try:
        with open(path) as f: return json.load(f)
    except FileNotFoundError: return default

def html_text(raw):
    soup = BeautifulSoup(raw, "lxml")
    for t in soup(["script", "style", "noscript", "svg", "iframe", "form", "header", "footer", "nav"]):
        t.decompose()
    main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.find("article") or soup.body or soup
    text = main.get_text("\n")
    if len(text.strip()) < 300:          # empty <main> shells (JS sites): fall back to the whole body
        soup2 = BeautifulSoup(raw, "lxml")
        for t in soup2(["script", "style", "noscript", "svg"]): t.decompose()
        text = (soup2.body or soup2).get_text("\n")
    return text

def pdf_text(raw):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(raw); f.flush()
        r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", f.name, "-"], capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "replace")

def normalise(text):
    lines = []
    for ln in text.splitlines():
        ln = re.sub(r"[ \t\u00a0]+", " ", ln).strip()
        if not ln or any(n.search(ln) for n in NOISE): continue
        lines.append(ln)
    return "\n".join(lines) + "\n"

CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
def fingerprint(text, kind="html"):
    """Order- and layout-insensitive fingerprint: the multiset of words.
    Ignores pdftotext version/layout differences (dot leaders, control chars, column order)
    and pages that merely reshuffle the same items; any added/removed/edited word still changes it."""
    t = CTRL.sub("", normalise(text))
    t = re.sub(r"(?:\.\s?){2,}", " ", t)          # table-of-contents dot leaders
    if kind == "pdf":
        # pdftotext versions split/move glyphs around control characters; compare the multiset of characters instead
        return hashlib.sha256("".join(sorted(re.sub(r"[\W_]", "", t.lower()))).encode()).hexdigest()
    toks = re.findall(r"\w+(?:[.,:%/'’-]\w+)*%?", t.lower())
    return hashlib.sha256(" ".join(sorted(toks)).encode()).hexdigest()

def fetch(src, attempts=2):
    last = None
    for i in range(attempts):
        try:
            r = requests.get(src["url"], headers=UA, timeout=(20, 180), allow_redirects=True)
            r.raise_for_status(); break
        except requests.RequestException as e:
            last = e
    else:
        raise last
    is_pdf = r.content[:4] == b"%PDF" or src.get("type") == "pdf"
    text = pdf_text(r.content) if is_pdf else html_text(r.content)
    return normalise(text), ("pdf" if is_pdf else "html")

def diff_excerpt(old, new, max_lines=60):
    d = list(difflib.unified_diff(old.splitlines(), new.splitlines(), "previous", "current", n=1, lineterm=""))
    added = [l[1:] for l in d if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:] for l in d if l.startswith("-") and not l.startswith("---")]
    return {"unified_diff": "\n".join(d[:max_lines]) + ("\n…(truncated)" if len(d) > max_lines else ""),
            "lines_added": len(added), "lines_removed": len(removed),
            "added_sample": added[:15], "removed_sample": removed[:15]}

def process(src, state):
    sid = src["id"]; ts = now(); stamp = ts.strftime("%Y%m%dT%H%M%S")
    st = state.get(sid, {})
    st["last_checked"] = ts.isoformat(timespec="seconds")
    try:
        text, kind = fetch(src)
    except Exception as e:
        st["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"; st["error_count"] = st.get("error_count", 0) + 1
        return sid, st, None, "error"
    st.pop("last_error", None); st["error_count"] = 0
    if len(text) < 200:
        st["warning"] = "very little text extracted (JS-rendered page or bot challenge?)"
    else:
        st.pop("warning", None)
    h = hashlib.sha256(text.encode()).hexdigest()
    d = P("snapshots", sid); os.makedirs(d, exist_ok=True)
    latest = os.path.join(d, "latest.txt")
    if st.get("hash") == h:
        return sid, st, None, "unchanged"
    old = open(latest).read() if os.path.exists(latest) else None
    fp = fingerprint(text, kind)
    old_fp = st.get("fp") if (st.get("fp_v") == 2 and st.get("fp")) else (fingerprint(old, kind) if old is not None else None)
    st["fp_v"] = 2
    if old is not None and old_fp == fp:
        # same words, only layout/order/noise differs: not a content change; keep the stored snapshot to avoid churn
        st["fp"] = fp
        return sid, st, None, "unchanged"
    if old is not None and normalise(old) == text:
        # only noise-filter rules changed: refresh the stored snapshot/hash silently
        with open(latest, "w") as f: f.write(text)
        st.update(hash=h, chars=len(text), kind=kind)
        return sid, st, None, "unchanged"
    prev_hash = st.get("hash")
    with open(os.path.join(d, f"{stamp}.txt"), "w") as f: f.write(text)
    with open(latest, "w") as f: f.write(text)
    first = st.get("hash") is None
    st.update(hash=h, fp=fp, chars=len(text), kind=kind, last_changed=ts.isoformat(timespec="seconds"))
    if first or old is None:
        st["baseline_at"] = ts.isoformat(timespec="seconds")
        return sid, st, None, "baseline"
    change = {
        "id": f"{stamp}-{sid}", "source_id": sid, "source_name": src["name"], "owner": src["owner"],
        "category": src["category"], "url": src["url"], "detected_at": ts.isoformat(timespec="seconds"),
        "previous_hash": prev_hash, "new_hash": h,
        "diff": diff_excerpt(old, text),
        "summary": None,            # placeholder: to be written by a human/AI reviewer
        "significance": None,       # placeholder: "minor" | "notable" | "major"
        "reviewed": False, "publish": False,
    }
    return sid, st, change, "changed"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only", nargs="*"); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    sources = load(P("sources.json"), {})["sources"]
    if a.only: sources = [s for s in sources if s["id"] in a.only]
    state = load(P("data", "state.json"), {})
    feed = load(P("data", "changes.json"), [])
    os.makedirs(P("changes"), exist_ok=True)
    results = {"baseline": [], "unchanged": [], "changed": [], "error": []}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for sid, st, change, status in ex.map(lambda s: process(s, state), sources):
            state[sid] = st; results[status].append(sid)
            if change:
                with open(P("changes", change["id"] + ".json"), "w") as f: json.dump(change, f, indent=2, ensure_ascii=False)
                feed.insert(0, change)
    feed.sort(key=lambda c: c["detected_at"], reverse=True)
    json.dump(state, open(P("data", "state.json"), "w"), indent=2)
    json.dump(feed[:500], open(P("data", "changes.json"), "w"), indent=2, ensure_ascii=False)
    log = {"run_at": now().isoformat(timespec="seconds"), "scope": "partial" if a.only else "full",
           "sources_checked": len(sources), **{k: len(v) for k, v in results.items()},
           "errors": {s: state[s].get("last_error") for s in results["error"]}, "changed_ids": results["changed"]}
    if not a.only:  # new safety-lesson candidates (queue only, never published automatically)
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import lesson_candidates
            log["lesson_candidates"] = lesson_candidates.run()
        except Exception as e:
            log["lesson_candidates"] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    json.dump(log, open(P("data", "run_log.json"), "w"), indent=2)
    hist = load(P("data", "run_history.json"), [])
    hist.insert(0, log)
    json.dump(hist[:200], open(P("data", "run_history.json"), "w"), indent=2)
    print(json.dumps(log, indent=2))

if __name__ == "__main__":
    main()
