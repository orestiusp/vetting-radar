-- Migration 2026-10-18 (b, optional but recommended): admin rights only for e-mail-link sessions.
-- NOT APPLIED. Run after 20261018_security_hardening.sql. Safe to re-run.
--
-- Why: is_admin() trusts the e-mail claim in the JWT. Email+password sign-up is also enabled on the
-- project (the site never uses passwords). Neither admin address has an auth user yet, so anyone can
-- pre-register an admin address with a password; when the real admin later clicks a magic link the
-- address is confirmed and the attacker's password then logs into the same, now-admin, account.
-- Requiring the session to come from an e-mail link/OTP (amr claim) closes that path even before the
-- admin users are created. Optional second factor: uncomment the aal2 line once each admin has
-- enrolled TOTP (supabase.auth.mfa), so a stolen mailbox alone is not enough.
--
-- Lock-out recovery: if moderation on admin.html says "not on the admin list" after this, re-run the
-- previous definition from schema.sql in the SQL editor.
begin;
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(auth.jwt() ->> 'role', '') = 'authenticated'
     and exists (select 1 from public.admins a where a.email = lower(coalesce(auth.jwt() ->> 'email', '')))
     and exists (select 1 from jsonb_array_elements(coalesce(auth.jwt() -> 'amr', '[]'::jsonb)) m
                 where m ->> 'method' in ('otp', 'magiclink'))
     -- and coalesce(auth.jwt() ->> 'aal', '') = 'aal2'
$$;
revoke all on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;
commit;
