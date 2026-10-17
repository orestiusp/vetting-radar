// Optional: Turnstile-checked voting. Deploy only if you set a Turnstile key (see supabase/README.md, step 7).
//   supabase functions deploy vote --no-verify-jwt
//   supabase secrets set TURNSTILE_SECRET_KEY=...
// The browser sends { report_id, voter_id, value, token }; we verify the token with Cloudflare,
// then call cast_vote() with the service role (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are provided by Supabase).
const ORIGINS = ["https://vettingradar.com", "https://www.vettingradar.com"];

Deno.serve(async (req) => {
  const origin = req.headers.get("origin") ?? "";
  const cors = {
    "Access-Control-Allow-Origin": ORIGINS.includes(origin) ? origin : ORIGINS[0],
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405);

  let b: { report_id?: string; voter_id?: string; value?: number; token?: string };
  try { b = await req.json(); } catch { return json({ error: "bad request" }, 400); }
  if (!b.report_id || !b.voter_id || ![1, -1].includes(Number(b.value)) || !b.token) return json({ error: "bad request" }, 400);

  const form = new FormData();
  form.append("secret", Deno.env.get("TURNSTILE_SECRET_KEY") ?? "");
  form.append("response", b.token);
  const ip = req.headers.get("cf-connecting-ip") ?? req.headers.get("x-forwarded-for")?.split(",")[0];
  if (ip) form.append("remoteip", ip);
  const ts = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form })
    .then((r) => r.json()).catch(() => ({ success: false }));
  if (!ts.success) return json({ error: "bot check failed" }, 403);

  const url = Deno.env.get("SUPABASE_URL")!, key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const r = await fetch(`${url}/rest/v1/rpc/cast_vote`, {
    method: "POST",
    headers: { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ p_report: b.report_id, p_voter: b.voter_id, p_value: Number(b.value) }),
  });
  const data = await r.json().catch(() => null);
  return r.ok ? json(Array.isArray(data) ? data[0] : data) : json({ error: data?.message ?? "vote failed" }, 400);
});
