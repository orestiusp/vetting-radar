-- Migration 2026-10-17: multi-item reports (items jsonb) + stale threshold 12 -> 24 months.
-- Already folded into schema.sql; this file is the delta for an existing database. Safe to re-run.
begin;
alter table public.reports add column if not exists items jsonb;
alter table public.reports drop constraint if exists reports_items_shape;
alter table public.reports add constraint reports_items_shape check (items is null or (jsonb_typeof(items) = 'array'
  and jsonb_array_length(items) between 1 and 60 and char_length(items::text) <= 8000));

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
  if (new.owner_id, new.owner_other, new.category, new.requirement, new.faced_on, new.vessel_type, new.author_id, new.items)
     is distinct from (old.owner_id, old.owner_other, old.category, old.requirement, old.faced_on, old.vessel_type, old.author_id, old.items)
     and current_user not in ('postgres','supabase_admin') then
    raise exception 'report content cannot be edited';
  end if;
  new.updated_at := now();
  return new;
end $$;

grant select (items) on public.reports to anon, authenticated;

create or replace view public.published_reports as
select r.id, r.owner_id, r.owner_other, r.category, r.requirement, r.faced_on, r.vessel_type, r.published_at,
       coalesce(v.up, 0)   as up,
       coalesce(v.down, 0) as down,
       greatest(r.faced_on, v.last_up) as last_confirmed,
       greatest(r.faced_on, v.last_up) < (current_date - interval '24 months') as stale,
       r.items
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
commit;
