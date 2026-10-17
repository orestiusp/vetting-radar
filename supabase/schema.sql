-- Vetting Radar · Reader reports
-- Run once in the Supabase SQL editor (Dashboard > SQL Editor > New query > paste > Run).
-- Safe to re-run: objects are created with "if not exists" / "or replace" where possible.
--
-- Model
--   reports  : one requirement a member says they faced. Status flow:
--              pending -> bot_approved (agent check) -> published (admin) ; rejected at either step
--              (an admin can also take a published report down -> rejected).
--   votes    : one vote per (report_id, voter_id). voter_id is a random id kept in the browser.
--   admins   : e-mail allow-list for the moderation page.
-- Access
--   anon / authenticated can only READ published reports (RLS + column grants, no author id)
--   and the public view published_reports. All writes go through the RPCs below.
--   The agent script (scripts/reports_admin.py) uses the service-role key and bot_review().

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- tables
create table if not exists public.admins (
  email      text primary key check (email = lower(btrim(email)) and position('@' in email) > 1),
  added_at   timestamptz not null default now()
);

create table if not exists public.reports (
  id               uuid primary key default gen_random_uuid(),
  author_id        uuid references auth.users(id) on delete set null,
  owner_id         text not null check (owner_id ~ '^[a-z0-9-]{1,40}$'),          -- id from data/comparison.json, or 'other'
  owner_other      text check (owner_other is null or char_length(btrim(owner_other)) between 2 and 60),
  category         text not null check (category in ('crew','vessel_age','inspections','terminal','other')),
  requirement      text not null check (char_length(btrim(requirement)) between 10 and 300),
  faced_on         date not null check (faced_on >= date '2015-01-01' and extract(day from faced_on) = 1), -- month precision
  vessel_type      text check (vessel_type is null or vessel_type in ('crude','product','chemical','lpg','lng','other')),
  rules_accepted   boolean not null check (rules_accepted),
  status           text not null default 'pending' check (status in ('pending','bot_approved','published','rejected')),
  bot_reason       text check (bot_reason is null or char_length(bot_reason) <= 500),
  bot_reviewed_at  timestamptz,
  admin_reason     text check (admin_reason is null or char_length(admin_reason) <= 500),
  admin_reviewed_at timestamptz,
  reviewed_by      text,
  published_at     timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint other_needs_name check (owner_id <> 'other' or owner_other is not null)
);
create index if not exists reports_status_idx on public.reports (status, created_at desc);
create index if not exists reports_owner_idx  on public.reports (owner_id) where status = 'published';
create index if not exists reports_author_idx on public.reports (author_id, created_at desc);

create table if not exists public.votes (
  id         bigint generated always as identity primary key,
  report_id  uuid not null references public.reports(id) on delete cascade,
  voter_id   uuid not null,
  value      smallint not null check (value in (1, -1)),
  created_at timestamptz not null default now(),
  constraint one_vote_per_browser unique (report_id, voter_id)
);
create index if not exists votes_report_idx on public.votes (report_id, value, created_at desc);

-- ---------------------------------------------------------------- status guard
-- Enforces the two-step flow whatever path the write comes from (RPC, dashboard, service role).
create or replace function public.reports_guard() returns trigger
language plpgsql set search_path = public as $$
begin
  if tg_op = 'INSERT' then
    if new.status <> 'pending' then raise exception 'new reports must start as pending'; end if;
    return new;
  end if;
  if new.status is distinct from old.status then
    if not ((old.status = 'pending'      and new.status in ('bot_approved','rejected'))
         or (old.status = 'bot_approved' and new.status in ('published','rejected'))
         or (old.status = 'published'    and new.status = 'rejected')) then
      raise exception 'invalid status change % -> %', old.status, new.status;
    end if;
    if new.status = 'published' then new.published_at := now(); end if;
  end if;
  -- content is frozen once submitted (moderators approve or reject, they do not edit)
  if (new.owner_id, new.owner_other, new.category, new.requirement, new.faced_on, new.vessel_type, new.author_id)
     is distinct from (old.owner_id, old.owner_other, old.category, old.requirement, old.faced_on, old.vessel_type, old.author_id)
     and current_user not in ('postgres','supabase_admin') then
    raise exception 'report content cannot be edited';
  end if;
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists reports_guard on public.reports;
create trigger reports_guard before insert or update on public.reports
  for each row execute function public.reports_guard();

-- ---------------------------------------------------------------- helpers
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.admins a
    where a.email = lower(coalesce(auth.jwt() ->> 'email', ''))
  ) and coalesce(auth.jwt() ->> 'role', '') = 'authenticated';
$$;

-- ---------------------------------------------------------------- row level security
alter table public.admins  enable row level security;
alter table public.reports enable row level security;
alter table public.votes   enable row level security;

-- reports: the public sees published rows only
drop policy if exists "published reports are public" on public.reports;
create policy "published reports are public" on public.reports
  for select to anon, authenticated using (status = 'published');
-- admins can read every row (moderation queue)
drop policy if exists "admins read all reports" on public.reports;
create policy "admins read all reports" on public.reports
  for select to authenticated using (public.is_admin());
-- no insert/update/delete policies: writes only through the security-definer RPCs below

-- votes: no direct access at all (counts come from the view / cast_vote)
-- admins: an admin may see the allow-list, nobody can change it from the client
drop policy if exists "admins read admins" on public.admins;
create policy "admins read admins" on public.admins
  for select to authenticated using (public.is_admin());

-- column privileges: never expose author_id or moderation notes to the client roles
revoke all on public.reports, public.votes, public.admins from anon, authenticated;
grant select (id, owner_id, owner_other, category, requirement, faced_on, vessel_type, status, published_at)
  on public.reports to anon, authenticated;
grant select on public.admins to authenticated;

-- ---------------------------------------------------------------- public view
-- Published reports with vote counts and "last confirmed" (latest of the month it was faced and the latest thumbs-up).
-- Runs with the view owner's rights so it can count votes; it filters to status = 'published' itself
-- and exposes no author or moderation columns.
create or replace view public.published_reports as
select r.id, r.owner_id, r.owner_other, r.category, r.requirement, r.faced_on, r.vessel_type, r.published_at,
       coalesce(v.up, 0)   as up,
       coalesce(v.down, 0) as down,
       greatest(r.faced_on, v.last_up) as last_confirmed,
       greatest(r.faced_on, v.last_up) < (current_date - interval '12 months') as stale
from public.reports r
left join lateral (
  select count(*) filter (where value = 1)::int  as up,
         count(*) filter (where value = -1)::int as down,
         max(created_at) filter (where value = 1)::date as last_up
  from public.votes where report_id = r.id
) v on true
where r.status = 'published';
revoke all on public.published_reports from anon, authenticated;
grant select on public.published_reports to anon, authenticated;

-- ---------------------------------------------------------------- RPC: voting (anyone, no sign-in)
-- One vote per (report, browser). Returns current counts; inserted=false if this browser had already voted.
create or replace function public.cast_vote(p_report uuid, p_voter uuid, p_value int)
returns table (up int, down int, last_confirmed date, stale boolean, my_vote int, inserted boolean)
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if p_value not in (1, -1) then raise exception 'value must be 1 or -1'; end if;
  if p_voter is null then raise exception 'voter id required'; end if;
  if not exists (select 1 from reports where id = p_report and status = 'published') then
    raise exception 'report not found';
  end if;
  insert into votes (report_id, voter_id, value) values (p_report, p_voter, p_value)
  on conflict on constraint one_vote_per_browser do nothing;
  get diagnostics n = row_count;
  return query
    select pr.up, pr.down, pr.last_confirmed, pr.stale,
           (select value::int from votes where report_id = p_report and voter_id = p_voter),
           n > 0
    from published_reports pr where pr.id = p_report;
end $$;

-- ---------------------------------------------------------------- RPC: posting (signed-in members)
create or replace function public.submit_report(
  p_owner_id text, p_owner_other text, p_category text, p_requirement text,
  p_faced_on date, p_vessel_type text, p_rules_accepted boolean)
returns uuid
language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); new_id uuid;
begin
  if uid is null then raise exception 'sign in to post a report'; end if;
  if not coalesce(p_rules_accepted, false) then raise exception 'please accept the posting rules'; end if;
  if p_faced_on > current_date or p_faced_on < current_date - interval '10 years' then
    raise exception 'month faced must be within the last 10 years';
  end if;
  if (select count(*) from reports where author_id = uid and created_at > now() - interval '24 hours') >= 5 then
    raise exception 'daily limit reached (5 reports per 24 hours)';
  end if;
  insert into reports (author_id, owner_id, owner_other, category, requirement, faced_on, vessel_type, rules_accepted)
  values (uid, lower(btrim(p_owner_id)),
          case when lower(btrim(p_owner_id)) = 'other' then nullif(btrim(p_owner_other), '') end,
          p_category, btrim(p_requirement), date_trunc('month', p_faced_on)::date,
          nullif(btrim(coalesce(p_vessel_type, '')), ''), true)
  returning id into new_id;
  return new_id;
end $$;

-- a member's own submissions and their status (no moderation notes beyond the outcome)
create or replace function public.my_reports()
returns table (id uuid, owner_id text, owner_other text, category text, requirement text, faced_on date, status text, created_at timestamptz)
language sql stable security definer set search_path = public as $$
  select id, owner_id, owner_other, category, requirement, faced_on,
         case when status = 'bot_approved' then 'pending' else status end, created_at
  from reports where author_id = auth.uid() order by created_at desc limit 50;
$$;

-- ---------------------------------------------------------------- RPC: moderation (admins, step 2)
create or replace function public.admin_list_reports()
returns table (id uuid, owner_id text, owner_other text, category text, requirement text, faced_on date, vessel_type text,
               status text, bot_reason text, bot_reviewed_at timestamptz, created_at timestamptz)
language plpgsql stable security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'not authorised'; end if;
  return query
    select r.id, r.owner_id, r.owner_other, r.category, r.requirement, r.faced_on, r.vessel_type,
           r.status, r.bot_reason, r.bot_reviewed_at, r.created_at
    from reports r where r.status in ('pending','bot_approved')
    order by (r.status = 'bot_approved') desc, r.created_at;
end $$;

-- p_action: 'approve' (pending -> bot_approved as a manual check, bot_approved -> published),
--           'reject' (pending/bot_approved/published -> rejected)
create or replace function public.moderate_report(p_id uuid, p_action text, p_reason text default null)
returns text
language plpgsql security definer set search_path = public as $$
declare cur text; nxt text; who text := lower(auth.jwt() ->> 'email');
begin
  if not public.is_admin() then raise exception 'not authorised'; end if;
  select status into cur from reports where id = p_id for update;
  if cur is null then raise exception 'report not found'; end if;
  nxt := case
    when p_action = 'approve' and cur = 'pending'      then 'bot_approved'
    when p_action = 'approve' and cur = 'bot_approved' then 'published'
    when p_action = 'reject'  and cur in ('pending','bot_approved','published') then 'rejected'
  end;
  if nxt is null then raise exception 'cannot % a % report', p_action, cur; end if;
  if cur = 'pending' then
    update reports set status = nxt, bot_reason = coalesce(left(p_reason, 500), 'manual check by admin'),
           bot_reviewed_at = now(), reviewed_by = who where id = p_id;
  else
    update reports set status = nxt, admin_reason = left(p_reason, 500), admin_reviewed_at = now(), reviewed_by = who where id = p_id;
  end if;
  return nxt;
end $$;

-- ---------------------------------------------------------------- RPC: agent check (service role only, step 1)
create or replace function public.bot_review(p_id uuid, p_decision text, p_reason text)
returns text
language plpgsql security definer set search_path = public as $$
declare cur text;
begin
  if p_decision not in ('bot_approved','rejected') then raise exception 'decision must be bot_approved or rejected'; end if;
  if p_decision = 'rejected' and coalesce(btrim(p_reason), '') = '' then raise exception 'a reason is required to reject'; end if;
  select status into cur from reports where id = p_id for update;
  if cur is distinct from 'pending' then raise exception 'report is %, not pending', coalesce(cur, 'missing'); end if;
  update reports set status = p_decision, bot_reason = left(p_reason, 500), bot_reviewed_at = now(), reviewed_by = 'agent'
  where id = p_id;
  return p_decision;
end $$;

-- ---------------------------------------------------------------- function privileges
-- Supabase grants EXECUTE on new functions to anon/authenticated by default, so revoke explicitly, then grant.
revoke all on function public.cast_vote(uuid, uuid, int)            from public, anon, authenticated;
revoke all on function public.submit_report(text, text, text, text, date, text, boolean) from public, anon, authenticated;
revoke all on function public.my_reports()                          from public, anon, authenticated;
revoke all on function public.admin_list_reports()                  from public, anon, authenticated;
revoke all on function public.moderate_report(uuid, text, text)     from public, anon, authenticated;
revoke all on function public.bot_review(uuid, text, text)          from public, anon, authenticated;
revoke all on function public.is_admin()                            from public, anon, authenticated;
revoke all on function public.reports_guard()                       from public, anon, authenticated;

grant execute on function public.cast_vote(uuid, uuid, int)         to anon, authenticated, service_role;
grant execute on function public.submit_report(text, text, text, text, date, text, boolean) to authenticated;
grant execute on function public.my_reports()                       to authenticated;
grant execute on function public.admin_list_reports()               to authenticated;
grant execute on function public.moderate_report(uuid, text, text)  to authenticated;
grant execute on function public.is_admin()                         to anon, authenticated;
grant execute on function public.bot_review(uuid, text, text)       to service_role;

-- ---------------------------------------------------------------- admins (edit, then run)
-- insert into public.admins (email) values ('you@example.com') on conflict do nothing;
