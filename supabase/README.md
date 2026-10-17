# Reader reports · Supabase setup

Project: `kfxroqikspadmpjqiwkl` (eu-central-1). Everything below is one-time.
The frontend only ever uses the **public anon key** (`site/config.js`). The service-role key and DB password stay
off the repo (env vars / secret files only).

## A. SQL (SQL Editor, or psql)

1. **Dashboard → SQL Editor → New query**, paste all of [`schema.sql`](schema.sql), **Run**.
   It creates `reports`, `votes`, `admins` (RLS enabled on all three), the `published_reports` view,
   the status-guard trigger and the RPCs `cast_vote`, `submit_report`, `my_reports`, `admin_list_reports`,
   `moderate_report`, `bot_review`. Re-running it is safe.
   psql alternative (session pooler; port 5432 must be reachable from your network):
   `psql "host=aws-0-eu-central-1.pooler.supabase.com port=5432 user=postgres.kfxroqikspadmpjqiwkl dbname=postgres sslmode=require" -f supabase/schema.sql`
2. **Add the admins** (same SQL editor; lower-case e-mails):
   ```sql
   insert into public.admins (email) values ('admin@example.com'), ('you@example.com') on conflict do nothing;
   ```
3. Check: `select tablename, rowsecurity from pg_tables where schemaname = 'public';` → all `true`.
3b. Then run the files in [`migrations/`](migrations/) in name order (security hardening: no auto-grants on new
    objects, RLS on by default, per-network vote throttle, admin only via e-mail-link sessions).
    Offline test: [`tests/pglite_security_test.mjs`](tests/pglite_security_test.mjs).

## B. Dashboard (cannot be done from SQL)

4. **Authentication → URL Configuration**
   - Site URL: `https://vettingradar.com`
   - Redirect URLs: `https://vettingradar.com/submit.html`, `https://vettingradar.com/admin.html` only.
     For local testing add `http://localhost:8765/**` temporarily and remove it again afterwards
     (a localhost entry lets a sign-in link be redirected to whatever runs on the user's port 8765).
5. **Authentication → Sign In / Providers → Email**: enabled, magic link / OTP on.
   Turn **"Allow new users to sign up"** on (members join by magic link). Password sign-in is not used by the site.
6. **Authentication → Emails → SMTP**: the built-in mailer is for testing only (very low hourly limit, Supabase branding).
   Before launch add custom SMTP (e.g. Resend / Postmark / SES, sender like `no-reply@vettingradar.com`) and then raise
   **Authentication → Rate Limits → emails per hour**. Optionally edit the "Magic Link" e-mail template text.
7. **Optional bot check (Cloudflare Turnstile)**, when you have a key:
   - Cloudflare → Turnstile → add site `vettingradar.com`, widget mode *Invisible*. Copy site key + secret.
   - Authentication → Attack Protection → enable CAPTCHA, provider Turnstile, paste the **secret** (protects magic-link sign-ups).
   - Votes: `supabase functions deploy vote --no-verify-jwt` and `supabase secrets set TURNSTILE_SECRET_KEY=...`,
     then in SQL: `revoke execute on function public.cast_vote(uuid, uuid, int) from anon, authenticated;`
   - `site/config.js`: set `TURNSTILE_SITE_KEY` and `VOTE_FUNCTION: true`.
8. **Project Settings → API**: the anon key goes in `site/config.js` (already set). Keep the service-role key secret.

## Moderation

- Step 1 (agent/bot): `SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/reports_admin.py list`
  then `approve <id>` or `reject <id> --reason "..."`. It can never publish.
- Step 2 (admin): sign in on `https://vettingradar.com/admin.html` (hidden, noindex) with an e-mail from `admins`.
  "Approve" on a bot-approved report publishes it; "Reject" needs a reason. Published reports can be taken down with
  `select public.moderate_report('<id>', 'reject', 'reason');` while signed in, or from the SQL editor:
  `update public.reports set status = 'rejected', admin_reason = '...' where id = '<id>';`

## Notes

- Only `published` rows are readable by anon/authenticated (RLS policy + column grants; `author_id` is never exposed).
- One vote per browser per report: `unique (report_id, voter_id)`; `cast_vote` ignores repeats and returns counts.
- "Stale": no thumbs-up and no new "faced" month for 12 months (`published_reports.stale`).
- Demo data exists only in the browser (`?demo=1` on localhost). Nothing sample is ever written to the database.
