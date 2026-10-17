#!/usr/bin/env python3
"""Reader reports, step 1 of moderation (the agent check).

Uses the Supabase service-role key, so run it only on a trusted machine. Never commit the key.

    export SUPABASE_URL=https://<project>.supabase.co
    export SUPABASE_SERVICE_ROLE_KEY=...            # Dashboard > Project Settings > API > service_role

    python3 scripts/reports_admin.py list                         # pending reports (oldest first)
    python3 scripts/reports_admin.py list --status bot_approved   # waiting for the admin (admin.html)
    python3 scripts/reports_admin.py approve <id> [--reason "..."]  # pending -> bot_approved
    python3 scripts/reports_admin.py reject  <id> --reason "names a vessel"
    python3 scripts/reports_admin.py list --json                  # machine-readable, for the agent

Only the admin can publish (admin.html). This script cannot set 'published'.
Checks the agent should apply before approving: no vessel, person or company names (other than the owner the
report is about), no copied/confidential text (SIRE/CDI report extracts, charterer e-mails), a plausible,
specific requirement, not abusive, not an advert, not a duplicate of an existing published report.
"""
import argparse, json, os, sys, urllib.request, urllib.error

COLS = "id,owner_id,owner_other,category,requirement,faced_on,vessel_type,status,bot_reason,created_at"


def env():
    url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")
    return url, key


def call(method, path, body=None):
    url, key = env()
    req = urllib.request.Request(url + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        try: detail = json.loads(detail).get("message", detail)
        except Exception: pass
        sys.exit(f"Supabase error {e.code}: {detail}")


def cmd_list(a):
    rows = call("GET", f"/rest/v1/reports?select={COLS}&status=eq.{a.status}&order=created_at.asc&limit={a.limit}")
    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False)); return
    if not rows:
        print(f"No {a.status} reports."); return
    for r in rows:
        owner = r["owner_other"] if r["owner_id"] == "other" else r["owner_id"]
        print(f"{r['id']}  [{r['status']}]  {owner} · {r['category']} · faced {r['faced_on'][:7]}"
              f"{(' · ' + r['vessel_type']) if r['vessel_type'] else ''} · submitted {r['created_at'][:16].replace('T', ' ')} UTC")
        print(f"    {r['requirement']}")
        if r.get("bot_reason"): print(f"    check: {r['bot_reason']}")
    print(f"\n{len(rows)} report(s).")


def review(a, decision):
    if decision == "rejected" and not (a.reason or "").strip():
        sys.exit("--reason is required to reject.")
    res = call("POST", "/rest/v1/rpc/bot_review", {"p_id": a.id, "p_decision": decision, "p_reason": a.reason or "passed agent check"})
    print(f"{a.id} -> {res}")


p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = p.add_subparsers(dest="cmd", required=True)
l = sub.add_parser("list", help="list reports by status (default: pending)")
l.add_argument("--status", default="pending", choices=["pending", "bot_approved", "published", "rejected"])
l.add_argument("--limit", type=int, default=100)
l.add_argument("--json", action="store_true")
for name, decision in (("approve", "bot_approved"), ("reject", "rejected")):
    s = sub.add_parser(name, help=f"mark a pending report {decision}")
    s.add_argument("id"); s.add_argument("--reason", default="")
    s.set_defaults(decision=decision)
a = p.parse_args()
if a.cmd == "list": cmd_list(a)
else: review(a, a.decision)
