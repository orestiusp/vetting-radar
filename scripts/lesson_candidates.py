"""Safety-lesson candidate finder (no auto-publish).

Reads the feeds in lesson_sources.json and appends NEW items to data/lesson_candidates.json with
status "new", reviewed=false and publish=false. A person then opens the report, writes the lesson in
our own words in data/lessons.json and approves it. Nothing here touches the public site.

The first run of a feed marks its current items as baseline (seen, not new) so the queue starts clean.
"""
import datetime as dt, hashlib, json, os, re, sys
import xml.etree.ElementTree as ET
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 VettingRadarMonitor/0.1 (+independent, non-commercial change monitor)"}
KEEP = 1000

TANKER = re.compile(r"\b(tanker|tankers|chemical|oil|lng|lpg|gas carrier|sts|ship[- ]to[- ]ship|bunker\w*|cargo tank|crude|product|terminal|vetting|sire|ocimf|inert|vapou?r|h2s|benzene|mooring)\b", re.I)
TRANSFER = re.compile(r"\b(collision|allision|grounding|fire|explosion|enclosed space|confined space|fatal\w*|fatigue|man overboard|blackout|steering|pilot\w*|lifeboat|bridge|navigation|watch\w*|crane|lifting|mooring|ladder|fall|injur\w*|towage|tug|safety)\b", re.I)
SKIP = re.compile(r"\b(fishing vessel|yacht|canoe|kayak|rib|recreational|ferry timetable|annual report|webinar|podcast|newsletter|appointment|joins|welcomes|award|premium|renewal|results|aviation|rail|road|aircraft|helicopter)\b", re.I)

def now(): return dt.datetime.now(dt.timezone.utc)
def load(p, d):
    try: return json.load(open(p))
    except Exception: return d
def strip(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()

def parse(xml):
    root = ET.fromstring(xml)
    out = []
    atom = "{http://www.w3.org/2005/Atom}"
    for it in root.iter(atom + "entry"):
        link = it.find(atom + "link")
        out.append({"title": strip(it.findtext(atom + "title")), "link": (link.get("href") if link is not None else "") or "",
                    "published": it.findtext(atom + "updated") or it.findtext(atom + "published") or "",
                    "summary": strip(it.findtext(atom + "summary"))[:400]})
    for it in root.iter("item"):
        out.append({"title": strip(it.findtext("title")), "link": (it.findtext("link") or "").strip(),
                    "published": it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "",
                    "summary": strip(it.findtext("description"))[:400]})
    return [x for x in out if x["title"] and x["link"]]

def relevance(item):
    t = item["title"] + " " + item["summary"]
    if TANKER.search(t): return "tanker-relevant"
    if SKIP.search(t): return "skip"
    if TRANSFER.search(t): return "transferable"
    return "unsorted"

def run(only=None):
    cfg = load(P("lesson_sources.json"), {"feeds": []})
    data = load(P("data", "lesson_candidates.json"), {"_about": "", "feeds": {}, "candidates": []})
    data["_about"] = ("New safety-lesson candidates found by scripts/lesson_candidates.py. Never published automatically. "
                      "To use one: read the full report, write a lesson in our own words in data/lessons.json (reviewed=false), "
                      "get it approved, then set status here to 'drafted' or 'rejected'.")
    seen = {c["key"] for c in data["candidates"]}
    summary = {"new": 0, "baseline": 0, "errors": {}}
    for f in cfg["feeds"]:
        if only and f["id"] not in only: continue
        fs = data["feeds"].setdefault(f["id"], {})
        try:
            r = requests.get(f["url"], headers=UA, timeout=(20, 60)); r.raise_for_status()
            items = parse(r.content)
            if f.get("link_contains"): items = [i for i in items if f["link_contains"] in i["link"]]
        except Exception as ex:
            fs.update({"last_error": f"{type(ex).__name__}: {str(ex)[:200]}", "last_checked": now().isoformat(timespec="seconds")})
            summary["errors"][f["id"]] = fs["last_error"]; continue
        first = not fs.get("initialised")
        for i in items:
            key = hashlib.sha1((f["id"] + "|" + i["link"]).encode()).hexdigest()[:16]
            if key in seen: continue
            seen.add(key)
            data["candidates"].append({"key": key, "feed": f["id"], "source_body": f["body"], "source_type": f["source_type"],
                "title": i["title"], "url": i["link"], "published": i["published"], "summary_from_feed": i["summary"],
                "relevance": relevance(i), "found_at": now().isoformat(timespec="seconds"),
                "status": "baseline" if first else "new", "reviewed": False, "publish": False, "lesson_id": None})
            summary["baseline" if first else "new"] += 1
        fs.update({"initialised": True, "last_checked": now().isoformat(timespec="seconds"), "last_ok": now().isoformat(timespec="seconds"),
                   "last_error": None, "items_in_feed": len(items)})
    data["candidates"].sort(key=lambda c: c["found_at"], reverse=True)
    data["candidates"] = data["candidates"][:KEEP]
    data["open_new"] = sum(1 for c in data["candidates"] if c["status"] == "new" and c["relevance"] != "skip")
    json.dump(data, open(P("data", "lesson_candidates.json"), "w"), indent=2, ensure_ascii=False)
    summary["open_new"] = data["open_new"]
    return summary

if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1:] or None), indent=2))
