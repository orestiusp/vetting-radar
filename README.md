# Vetting Radar (MVP, local only)

Independent tracker of public tanker-vetting rules (SIRE 2.0/OCIMF, CDI, RightShip, oil-major and terminal criteria, PSC campaigns).
Not affiliated with OCIMF, CDI, RightShip or any employer. Always verify at source.

## Layout
- sources.json: registry of 77 public pages/PDFs (verified 2026-10-17)
- scripts/monitor.py: fetch, extract (pdftotext for PDFs), snapshot, SHA-256 and diff -> changes/*.json + data/changes.json
  - `python3 scripts/monitor.py` (all) or `--only <id> ...`
  - Change entries have summary/significance = null and reviewed/publish = false; fill them in during review.
- scripts/comparison_data.py: writes data/comparison.json/csv ("who requires what"; only cited facts, blanks where the source is silent)
- data/updates.json, data/calendar.json: reviewed editorial updates and deadlines
- newsletter/issue-001.md: sample issue (build writes the .html copies)
- scripts/build.py: writes the static site to dist/
- screens/: local screenshots (not committed)

## Local preview
    python3 scripts/build.py && python3 -m http.server 8765 --directory dist

## Homepage
"Lessons first" (option C of three mockups, chosen 2026-10-19): the lesson of the week leads, with the signup beside it; on phones a
"Get the weekly brief" link under the intro jumps to the signup below the lesson card. Styles in `site/home.css` (index only).
Without published safety lessons the build falls back to the rule-changes homepage.

## Go-live (not done: no accounts created, nothing deployed)
1. Push the repo to GitHub and enable GitHub Pages (or Cloudflare Pages) on dist/.
2. Add a scheduled GitHub Action (e.g. daily) to run monitor.py, then build.py, then commit. Note: USCG returns 403 to some datacenter IPs.
3. Create a Buttondown or Beehiiv free account and swap the signup placeholder form action.
4. Optional: register vettingradar.com (unregistered per Verisign RDAP on 2026-10-17).

## Automation
`.github/workflows/monitor-and-deploy.yml` runs daily at 05:00 UTC (and on push / manual dispatch):
monitor -> build -> commit updated data/snapshots back (`[skip ci]`) -> deploy `dist/` to GitHub Pages.
Detected changes stay `reviewed=false, publish=false`; the site only shows "change detected" with a source link until a human
fills in `summary`/`significance` and sets both flags to true.

## Safety lessons (editorial, human-approved)
- `data/lessons.json`: lessons in our own words, linked to the official report. AI drafts, a person approves.
  The live build publishes only records with `reviewed: true` **and** `publish: true`. With none published, the nav link, homepage block and pages are not generated.
- `python scripts/build.py --preview` (or `VR_PREVIEW=1`): local review build. Also renders drafts with a "Draft – awaiting review" badge, editor notes, a preview banner and `noindex`. Never deploy a preview build.
- Lesson URLs (`lessons/<id>.html`): the slug ends in the year the incident **occurred** (`occurred`), not the year the report was published
  (e.g. `mooring-spring-parted-lock-entry-2018`: incident 2018, report 2020). Keep doing this for new lessons. Never rename a published slug:
  the URLs are live and may already be shared. (One launch lesson, `chemical-cargo-contaminated-by-tank-coating`, has no year because the
  source gives no occurrence date; leave it as is.)
- Each lesson gets `lessons/<id>.html` and a one-page toolbox talk `lessons/<id>-toolbox.html` (+ `.pdf` when headless Chrome is available).
  It also gets the hub `lessons.html`, the policy `lessons-policy.html` and `data/lessons.json`. A newsletter "Lesson of the week" snippet is written to `newsletter/snippets/`.
- The build prints `lessons check:` warnings (never a build failure): missing fields, unknown SIRE/PSC tags, possible vessel names in our text, "owner" wording, and more than 2 new lessons in one ISO week. The 14 launch lessons (approved together on 2026-10-19) carry `"launch_batch": true` and are exempt from the weekly cap; do not set it on later additions.
- Editor review notes are private: they live in `data/private/lessons_review_notes.json` (git-ignored, `{"<lesson id>": ["note", ...]}`), are read only by `--preview` builds (shown in the lesson sidebar), and never reach the repo, the live build or `dist/data/lessons.json`. Keep a backup outside the repo; GitHub Actions never sees them.
- `lesson_sources.json` + `scripts/lesson_candidates.py`: the daily monitor collects new report links from MAIB, TSIB, NSIA, OCIMF, the Swedish Club and UK P&I into `data/lesson_candidates.json`.
  These are a queue only and are never published automatically.
