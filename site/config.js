// Vetting Radar · reader reports configuration (public values only; never put the service-role key here).
// Empty URL/key: the site shows "Reader reports coming soon". Fill in after creating the Supabase project
// (Dashboard > Project Settings > API). The build can also write this file from env vars
// VR_SUPABASE_URL, VR_SUPABASE_ANON_KEY, VR_TURNSTILE_SITE_KEY, VR_VOTE_FUNCTION.
window.VR_CONFIG = {
  SUPABASE_URL: "https://kfxroqikspadmpjqiwkl.supabase.co",
  SUPABASE_ANON_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtmeHJvcWlrc3BhZG1wanFpd2tsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIyNTg2MzUsImV4cCI6MjEwNzgzNDYzNX0.xgLc849X45W_DJ_0HYtEQlfZEoONa_mWNZCseUozVRg", // public anon key (safe to publish)
  TURNSTILE_SITE_KEY: "",  // optional Cloudflare Turnstile site key (invisible bot check)
  VOTE_FUNCTION: false     // true once the "vote" Edge Function is deployed (Turnstile-checked votes)
};
