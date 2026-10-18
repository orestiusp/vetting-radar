-- Migration 2026-10-18: security hardening (from the security audit, see security-audit.md).
-- NOT APPLIED. Review, then run once in Dashboard > SQL Editor (runs as postgres). Safe to re-run.
--   1. Stop new tables/functions/sequences in `public` from being auto-granted to anon/authenticated.
--   2. Event trigger: every new table in `public` gets row level security switched on automatically.
--   3. Tidy grants the client roles do not need (is_admin for anon, the votes id sequence).
--   4. Per-network vote throttle inside cast_vote (no new account or service needed).
-- After running, do the checks at the bottom.
begin;

-- ---------------------------------------------------------------- 1. no auto-expose for new objects
-- Today a table created by postgres in public is granted ALL to anon + authenticated at birth
-- (pg_default_acl), so one forgotten "enable row level security" = world-writable table.
-- From now on new objects need an explicit GRANT, like the existing ones already have.
alter default privileges for role postgres in schema public revoke all     on tables    from anon, authenticated;
alter default privileges for role postgres in schema public revoke all     on sequences from anon, authenticated;
alter default privileges for role postgres in schema public revoke execute on functions from anon, authenticated;
-- functions are also executable via PUBLIC by default; that default is global (not per schema)
alter default privileges for role postgres revoke execute on functions from public;
-- Objects created as supabase_admin (some dashboard paths) keep their own defaults; turn off
-- "Automatically expose new tables" in Dashboard > Project Settings > Data API as well (see audit).

-- ---------------------------------------------------------------- private schema (never exposed by the API)
-- The Data API serves only public + graphql_public, so nothing here is reachable with the anon key.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

-- ---------------------------------------------------------------- 2. RLS on by default for new public tables
create or replace function private.rls_auto_enable() returns event_trigger
language plpgsql security definer set search_path = pg_catalog as $$
declare r record;
begin
  for r in select * from pg_event_trigger_ddl_commands()
           where command_tag in ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO') and object_type = 'table'
  loop
    if r.schema_name = 'public' then
      execute format('alter table %s enable row level security', r.object_identity);
    end if;
  end loop;
end $$;
revoke all on function private.rls_auto_enable() from public, anon, authenticated;
drop event trigger if exists rls_auto_enable;
create event trigger rls_auto_enable on ddl_command_end
  when tag in ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
  execute function private.rls_auto_enable();

-- ---------------------------------------------------------------- 3. grants the clients do not need
revoke execute on function public.is_admin() from anon;              -- only authenticated policies call it
revoke all on sequence public.votes_id_seq from anon, authenticated; -- votes are inserted by cast_vote (definer)

-- ---------------------------------------------------------------- 4. vote throttle
-- cast_vote stays callable without sign-in, but each network (client IP as seen by Supabase's Cloudflare edge,
-- header cf-connecting-ip, which clients cannot set) gets at most
--   * 3 counted votes per report per 24 h   (a few crew sharing one ship / office connection), and
--   * 30 counted votes per hour in total.
-- Only a salted SHA-256 of the IP is stored, and rows older than 2 days are purged.
-- If the header is missing (see check C below) the throttle is skipped (fails open) rather than
-- blocking every vote; then use the Turnstile edge function (supabase/functions/vote) instead.
create table if not exists private.app_secrets (name text primary key, value bytea not null);
alter table private.app_secrets enable row level security;
insert into private.app_secrets (name, value) values ('vote_ip_salt', extensions.gen_random_bytes(32))
  on conflict (name) do nothing;

create table if not exists private.vote_throttle (
  id         bigint generated always as identity primary key,
  ip_hash    bytea not null,
  report_id  uuid not null,
  created_at timestamptz not null default now()
);
alter table private.vote_throttle enable row level security;
create index if not exists vote_throttle_ip_idx on private.vote_throttle (ip_hash, created_at desc);
create index if not exists vote_throttle_ip_report_idx on private.vote_throttle (ip_hash, report_id, created_at desc);
revoke all on all tables in schema private from public, anon, authenticated;

create or replace function private.client_ip_hash() returns bytea
language plpgsql stable set search_path = pg_catalog as $$
declare h jsonb; ip text;
begin
  begin h := nullif(current_setting('request.headers', true), '')::jsonb; exception when others then h := null; end;
  ip := nullif(btrim(h ->> 'cf-connecting-ip'), '');
  if ip is null then return null; end if;
  return extensions.digest(convert_to(ip, 'UTF8') || (select value from private.app_secrets where name = 'vote_ip_salt'), 'sha256');
end $$;
revoke all on function private.client_ip_hash() from public, anon, authenticated;

create or replace function public.cast_vote(p_report uuid, p_voter uuid, p_value int)
returns table (up int, down int, last_confirmed date, stale boolean, my_vote int, inserted boolean)
language plpgsql security definer set search_path = public as $$
declare n int; k bytea;
begin
  -- the Turnstile edge function calls with the service role from Supabase's servers (one shared IP): not throttled here
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then k := private.client_ip_hash(); end if;
  if p_value is null or p_value not in (1, -1) then raise exception 'value must be 1 or -1'; end if;
  if p_voter is null then raise exception 'voter id required'; end if;
  if not exists (select 1 from reports where id = p_report and status = 'published') then
    raise exception 'report not found';
  end if;
  if k is not null and not exists (select 1 from votes where report_id = p_report and voter_id = p_voter) then
    if (select count(*) from private.vote_throttle t where t.ip_hash = k and t.created_at > now() - interval '1 hour') >= 30
       or (select count(*) from private.vote_throttle t where t.ip_hash = k and t.report_id = p_report
           and t.created_at > now() - interval '24 hours') >= 3 then
      raise exception 'too many votes from your network, please try again later' using errcode = 'PT429'; -- HTTP 429
    end if;
  end if;
  insert into votes (report_id, voter_id, value) values (p_report, p_voter, p_value)
  on conflict on constraint one_vote_per_browser do nothing;
  get diagnostics n = row_count;
  if n > 0 and k is not null then
    insert into private.vote_throttle (ip_hash, report_id) values (k, p_report);
    if random() < 0.02 then delete from private.vote_throttle where created_at < now() - interval '2 days'; end if;
  end if;
  return query
    select pr.up, pr.down, pr.last_confirmed, pr.stale,
           (select value::int from votes where report_id = p_report and voter_id = p_voter),
           n > 0
    from published_reports pr where pr.id = p_report;
end $$;
revoke all on function public.cast_vote(uuid, uuid, int) from public, anon, authenticated;
grant execute on function public.cast_vote(uuid, uuid, int) to anon, authenticated, service_role;

commit;

-- ---------------------------------------------------------------- checks after running (read-only)
-- A. no client grants on future objects:
--    select pg_get_userbyid(defaclrole), defaclnamespace::regnamespace, defaclobjtype, defaclacl from pg_default_acl;
--    -> the postgres/public rows no longer list anon= or authenticated=
-- B. RLS everywhere in public:
--    select relname, relrowsecurity from pg_class where relnamespace = 'public'::regnamespace and relkind = 'r';
-- C. throttle sees the client IP: cast ONE real vote on the live site, then
--    select count(*) from private.vote_throttle;   -> 1 (0 means cf-connecting-ip is not forwarded: throttle is off)
-- D. anon still cannot reach anything new:  curl .../rest/v1/vote_throttle  -> 404 (schema not exposed)
