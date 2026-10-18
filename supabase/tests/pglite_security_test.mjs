// Offline security test for schema.sql + migrations (PGlite = Postgres 17 in WASM, nothing touches the live project).
//   cd supabase/tests && npm i @electric-sql/pglite && node pglite_security_test.mjs   -> every line PASS
process.on('unhandledRejection', e => { console.log('UNCAUGHT', e.code||'', e.message, (e.query||'').slice(0,200)); process.exit(1); });
import { PGlite } from '@electric-sql/pglite';
import { pgcrypto } from '@electric-sql/pglite/contrib/pgcrypto';
import fs from 'fs';
const R = new URL('../', import.meta.url).pathname;
const db = new PGlite({ extensions: { pgcrypto } });
const ok = (m) => console.log('PASS', m), bad = (m) => { console.log('FAIL', m); process.exitCode = 1; };
async function expectErr(sql, re, label) { try { await db.exec(sql); bad(label + ' (no error)'); } catch (e) { (re.test(e.message) || re.test(e.code||'')) ? ok(label + ' -> ' + (e.code||'') + ' ' + e.message.slice(0,80)) : bad(label + ' -> ' + e.message); } }
const one = async (sql) => { const p = sql.split(';').map(x => x.trim()).filter(Boolean); for (const q of p.slice(0, -1)) await db.exec(q); return (await db.query(p.at(-1))).rows[0]; };
await db.exec(`
create role anon nologin; create role authenticated nologin; create role service_role nologin bypassrls;
create schema extensions; create extension pgcrypto schema extensions;
grant usage on schema extensions to anon, authenticated, service_role;
create schema auth; grant usage on schema auth to anon, authenticated, service_role;
create table auth.users (id uuid primary key, email text);
create function auth.jwt() returns jsonb language sql stable as $$ select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $$;
create function auth.uid() returns uuid language sql stable as $$ select nullif(auth.jwt() ->> 'sub', '')::uuid $$;
grant execute on all functions in schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
-- emulate the live project's auto-expose default privileges
alter default privileges for role postgres in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges for role postgres in schema public grant all on sequences to anon, authenticated, service_role;
alter default privileges for role postgres in schema public grant execute on functions to anon, authenticated, service_role;
set search_path = public, extensions;
`);
await db.exec(fs.readFileSync(R + 'schema.sql', 'utf8'));
await db.exec(fs.readFileSync(R + 'migrations/20261017_report_items_stale24.sql', 'utf8'));
// seed one published report the legitimate way
await db.exec(`insert into reports (id, owner_id, owner_other, category, requirement, faced_on, rules_accepted) values
  ('11111111-1111-1111-1111-111111111111','other','Example','crew','Example requirement text long enough','2026-01-01',true),
  ('22222222-2222-2222-2222-222222222222','other','Example','crew','Second example requirement text','2026-01-01',true);`);
await db.exec(`update reports set status='bot_approved'; update reports set status='published';`);
// before: new tables auto-exposed, RLS off
await db.exec(`create table public.before_t (x int);`);
let r = await one(`select relrowsecurity rls, has_table_privilege('anon','public.before_t','INSERT') anon_ins from pg_class where oid='public.before_t'::regclass`);
console.log('BEFORE migration: new table rls=', r.rls, 'anon insert=', r.anon_ins);
// apply the new migrations
await db.exec(fs.readFileSync(R + 'migrations/20261018_security_hardening.sql', 'utf8')); ok('20261018_security_hardening.sql applied');
await db.exec(fs.readFileSync(R + 'migrations/20261018_security_hardening.sql', 'utf8')); ok('re-run is safe');
await db.exec(fs.readFileSync(R + 'migrations/20261018b_admin_session_hardening.sql', 'utf8')); ok('20261018b applied');
await db.exec(`create table public.after_t (x int); create function public.after_f() returns int language sql as 'select 1';`);
r = await one(`select relrowsecurity rls, has_table_privilege('anon','public.after_t','SELECT') anon_sel, has_function_privilege('anon','public.after_f()','EXECUTE') anon_exec from pg_class where oid='public.after_t'::regclass`);
(r.rls && !r.anon_sel && !r.anon_exec) ? ok('new table: RLS auto-on, no anon grant; new function not anon-executable') : bad('new objects ' + JSON.stringify(r));
r = await one(`select has_function_privilege('anon','public.is_admin()','EXECUTE') a, has_function_privilege('anon','public.cast_vote(uuid,uuid,int)','EXECUTE') v, has_sequence_privilege('anon','public.votes_id_seq','USAGE') s`);
(!r.a && r.v && !r.s) ? ok('anon: no is_admin, keeps cast_vote, no sequence') : bad(JSON.stringify(r));
// --- voting as anon
const vote = (ip, voter, rep='11111111-1111-1111-1111-111111111111') => `reset role; select set_config('request.headers', '${ip ? JSON.stringify({'cf-connecting-ip': ip}) : '{}'}', false); set role anon; select * from public.cast_vote('${rep}', '${voter}', 1);`;
const uid = (i) => '00000000-0000-4000-8000-' + String(i).padStart(12, '0');
for (let i = 1; i <= 3; i++) await db.exec(vote('203.0.113.7', uid(i)));
ok('3 votes from one IP on one report accepted');
await expectErr(vote('203.0.113.7', uid(4)), /PT429|too many/, '4th vote same IP same report (rotated voter id)');
await db.exec(vote('203.0.113.7', uid(1))); ok('repeat vote by an existing voter is not throttled (returns inserted=false)');
await db.exec(vote('198.51.100.9', uid(5))); ok('other IP still votes');
await db.exec(vote(null, uid(6))); ok('no cf-connecting-ip header -> throttle skipped (fails open)');
await expectErr(`set role anon; select * from private.vote_throttle`, /permission denied/, 'anon reading private.vote_throttle');
await expectErr(`set role anon; select * from private.app_secrets`, /permission denied/, 'anon reading private.app_secrets');
await expectErr(`set role anon; insert into public.votes (report_id, voter_id, value) values ('11111111-1111-1111-1111-111111111111','${uid(9)}',1)`, /permission denied/, 'anon direct insert into votes');
await expectErr(`set role anon; select * from public.cast_vote('11111111-1111-1111-1111-111111111111','${uid(10)}', 7)`, /value must be/, 'anon bad vote value');
// hourly cap: 30 per IP across reports (insert 29 throttle rows for report 2, then 1 vote ok, 31st fails)
await db.exec(`reset role; insert into private.vote_throttle (ip_hash, report_id) select private.client_ip_hash(), '22222222-2222-2222-2222-222222222222' from generate_series(1,27)`).catch(()=>{});
await db.exec(`reset role; select set_config('request.headers', '{"cf-connecting-ip":"192.0.2.50"}', false); insert into private.vote_throttle (ip_hash, report_id) select private.client_ip_hash(), gen_random_uuid() from generate_series(1,30);`);
await expectErr(vote('192.0.2.50', uid(20), '22222222-2222-2222-2222-222222222222'), /PT429|too many/, '31st vote in an hour from one IP');
r = await one(`reset role; select count(*)::int n, count(distinct ip_hash)::int k, bool_and(octet_length(ip_hash)=32) h from private.vote_throttle`);
console.log('throttle rows', r, '(only 32-byte hashes, no IPs stored)');
r = await one(`select up from published_reports where id='11111111-1111-1111-1111-111111111111'`); console.log('report 1 up votes =', r.up, '(expected 5)');
// --- admin checks
await db.exec(`reset role; insert into admins (email) values ('admin@vettingradar.com')`);
const asAdmin = async (method) => { await db.exec(`reset role; select set_config('request.jwt.claims', '${JSON.stringify({role:'authenticated', sub: uid(99), email:'admin@vettingradar.com', amr:[{method, timestamp:1}]})}', false); set role authenticated;`); return (await one(`select public.is_admin() a`)).a; };
(await asAdmin('otp')) ? ok('admin via magic-link/OTP session -> is_admin true') : bad('otp admin');
(!(await asAdmin('password'))) ? ok('admin e-mail via PASSWORD session -> is_admin false (pre-hijack closed)') : bad('password admin');
await expectErr(`select * from public.admin_list_reports()`, /not authorised/, 'password-session admin_list_reports');
await asAdmin('magiclink'); r = await one(`select count(*)::int n from public.admin_list_reports()`); ok('magiclink admin can list queue (' + r.n + ' rows)');
// member cannot publish
await db.exec(`reset role; insert into auth.users (id, email) values ('${uid(77)}', 'member@example.com')`);
await db.exec(`reset role; select set_config('request.jwt.claims', '${JSON.stringify({role:'authenticated', sub: uid(77), email:'member@example.com', amr:[{method:'otp'}]})}', false); set role authenticated;`);
const id = (await one(`select public.submit_report('other','Somewhere','crew','Member requirement text here','2026-02-01',null,true) id`)).id;
await expectErr(`select public.moderate_report('${id}','approve')`, /not authorised/, 'member approving own report');
await expectErr(`update public.reports set status='published' where id='${id}'`, /permission denied/, 'member updating status directly');
r = await one(`select count(*)::int n from public.reports where id='${id}'`).catch(e => ({err: e.message}));
console.log('member reading own pending row via table:', JSON.stringify(r));
// service role (edge function path) is not throttled by the shared server IP
await db.exec(`reset role; select set_config('request.jwt.claims', '{"role":"service_role"}', false); select set_config('request.headers', '{"cf-connecting-ip":"203.0.113.7"}', false); set role service_role;`);
await db.exec(`select * from public.cast_vote('11111111-1111-1111-1111-111111111111', '${uid(50)}', 1)`); ok('service_role vote not throttled (edge function path)');
await db.exec(`reset role; select set_config('request.jwt.claims', '', false); set role anon;`);
await expectErr(`select * from public.cast_vote('11111111-1111-1111-1111-111111111111', '${uid(51)}', 1)`, /PT429/, 'anon from same IP still throttled');
