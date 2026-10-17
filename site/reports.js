// Vetting Radar · reader reports (user-submitted, moderated, never official data)
// Needs window.VR_CONFIG (config.js). Without SUPABASE_URL/ANON_KEY everything stays on "coming soon".
// Local demo: add ?demo=1 on localhost to render clearly fake "Example" reports (never shown on the live site).
(function () {
  'use strict';
  var CFG = window.VR_CONFIG || {};
  var LOCAL = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || location.protocol === 'file:';
  var QS = new URLSearchParams(location.search);
  var DEMO = LOCAL && QS.has('demo') ? (QS.get('demo') || '1') : '';
  var LIVE = !DEMO && !!(CFG.SUPABASE_URL && CFG.SUPABASE_ANON_KEY);
  var SB_SRC = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.118.0/dist/umd/supabase.js';
  var SB_SRI = 'sha384-TcHRA3zBbn+Lexh5n+Oil4guNPOS3rjNDpGRAN46u/s/mB2IZ50ceC6TYDU2yvgK';
  var TS_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
  var CATS = { crew: 'Crew experience', vessel_age: 'Vessel age', inspections: 'Inspections / SIRE', terminal: 'Terminal', other: 'Other' };
  var VT = { crude: 'Crude tanker', product: 'Product tanker', chemical: 'Chemical tanker', lpg: 'LPG carrier', lng: 'LNG carrier', other: 'Other type' };
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var OWNERS = []; try { OWNERS = JSON.parse(($('#vr-owners') || {}).textContent || '[]'); } catch (e) { OWNERS = []; }
  var OWN = {}; OWNERS.forEach(function (o) { OWN[o.id] = o; });

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function my(d) { if (!d) return ''; var p = String(d).split('-'); return MON[(+p[1] || 1) - 1] + ' ' + p[0]; }
  function staleDate(d) { if (!d) return false; var p = String(d).split('-'), t = new Date(), c = new Date(t.getFullYear() - 1, t.getMonth(), t.getDate()); return new Date(+p[0], (+p[1] || 1) - 1, +p[2] || 1) < c; }
  function ownerName(r) { return r.owner_id === 'other' ? (r.owner_other || 'Other') : (OWN[r.owner_id] ? OWN[r.owner_id].name : r.owner_id); }
  function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || 'null'); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }
  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var b = new Uint8Array(16); (window.crypto || {}).getRandomValues ? crypto.getRandomValues(b) : b.forEach(function (_, i) { b[i] = Math.random() * 256; });
    b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
    var h = Array.prototype.map.call(b, function (x) { return (x + 256).toString(16).slice(1); }).join('');
    return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
  }
  function voterId() { var v = store('vr_voter'); if (!v) { v = uuid(); store('vr_voter', v); } return v; }
  function myVotes() { return store('vr_votes') || {}; }

  // ---------- demo data: clearly fake, local only ----------
  function demoReports() {
    var first = OWNERS[0] ? OWNERS[0].id : 'other';
    var term = (OWNERS.filter(function (o) { return /^terminal$/i.test(o.type); })[0] || OWNERS[1] || { id: first }).id;
    return [
      { id: 'demo-1', example: true, owner_id: first, category: 'crew', requirement: 'Example (not a real report): crew time onboard on the current contract no more than 10 months.', faced_on: '2026-08-01', vessel_type: 'product', up: 7, down: 1, last_confirmed: '2026-09-14' },
      { id: 'demo-2', example: true, owner_id: first, category: 'inspections', requirement: 'Example (not a real report): placeholder text showing how an inspection-related report is displayed.', faced_on: '2026-05-01', vessel_type: 'crude', up: 3, down: 2, last_confirmed: '2026-06-02' },
      { id: 'demo-3', example: true, owner_id: term, category: 'terminal', requirement: 'Example (not a real report): sample text showing a stale report with no confirmation in the last 12 months.', faced_on: '2025-03-01', vessel_type: null, up: 1, down: 0, last_confirmed: '2025-04-20' }
    ];
  }

  // ---------- loaders ----------
  function loadScript(src, sri) {
    return new Promise(function (ok, fail) {
      var s = document.createElement('script'); s.src = src; s.async = true;
      if (sri) { s.integrity = sri; s.crossOrigin = 'anonymous'; }
      s.onload = ok; s.onerror = function () { fail(new Error('could not load ' + src)); }; document.head.appendChild(s);
    });
  }
  var _sb = null;
  function client(auth) {
    if (_sb) return Promise.resolve(_sb);
    return loadScript(SB_SRC, SB_SRI).then(function () {
      _sb = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON_KEY, {
        auth: auth ? { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
                   : { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false }
      });
      return _sb;
    });
  }
  var _ts = null, _tsEl = null;
  function botToken() { // invisible Cloudflare Turnstile; resolves '' when not configured
    if (!CFG.TURNSTILE_SITE_KEY || !LIVE) return Promise.resolve('');
    _ts = _ts || loadScript(TS_SRC);
    return _ts.then(function () {
      return new Promise(function (ok) {
        if (!_tsEl) { _tsEl = document.createElement('div'); _tsEl.className = 'rr-ts'; document.body.appendChild(_tsEl); }
        else { try { window.turnstile.remove(_tsEl); } catch (e) { /* first use */ } }
        window.turnstile.render(_tsEl, { sitekey: CFG.TURNSTILE_SITE_KEY, appearance: 'interaction-only', callback: ok, 'error-callback': function () { ok(''); } });
      });
    }).catch(function () { return ''; });
  }
  function fetchPublished() {
    if (DEMO) return Promise.resolve(demoReports());
    return client(false).then(function (sb) {
      return sb.from('published_reports').select('*').order('last_confirmed', { ascending: false }).limit(1000);
    }).then(function (res) { if (res.error) throw res.error; return res.data || []; });
  }

  // ---------- rendering ----------
  function item(r, withOwner) {
    var stale = r.stale != null ? r.stale : staleDate(r.last_confirmed);
    var mv = myVotes()[r.id];
    var meta = ['Faced ' + my(r.faced_on)]; if (r.vessel_type) meta.push(VT[r.vessel_type] || r.vessel_type);
    return '<article class="rr-item' + (stale ? ' stale' : '') + '" data-id="' + esc(r.id) + '">' +
      '<div class="rr-meta"><span class="rr-badge">User report</span>' + (r.example ? '<span class="rr-ex">Example</span>' : '') +
      (withOwner ? '<span class="rr-own">' + esc(ownerName(r)) + '</span>' : '') +
      '<span class="pill">' + esc(CATS[r.category] || r.category) + '</span>' +
      (stale ? '<span class="rr-staletag" title="No confirmation in the last 12 months">Stale</span>' : '') + '</div>' +
      '<p class="rr-text">' + esc(r.requirement) + '</p>' +
      '<div class="rr-foot"><span>' + esc(meta.join(' · ')) + '</span><span class="rr-conf">Last confirmed ' + esc(my(r.last_confirmed)) + '</span>' +
      '<span class="rr-vote" role="group" aria-label="Does this match your experience?">' +
      vbtn(r, 1, mv) + vbtn(r, -1, mv) + '</span></div></article>';
  }
  function vbtn(r, v, mv) {
    var on = mv === v, lbl = v === 1 ? 'Matches my experience' : 'Not my experience';
    return '<button type="button" class="rr-vb' + (on ? ' on' : '') + '" data-v="' + v + '"' + (mv ? ' disabled' : '') + ' aria-pressed="' + on + '" title="' + lbl + '">' +
      '<span aria-hidden="true">' + (v === 1 ? '👍' : '👎') + '</span><span class="lbl">' + lbl + '</span><b>' + (v === 1 ? r.up : r.down) + '</b></button>';
  }
  var BY_ID = {};
  function bindVotes(root) {
    root.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('.rr-vb'); if (!b || b.disabled) return;
      var art = b.closest('.rr-item'), id = art.getAttribute('data-id'), v = +b.getAttribute('data-v'), r = BY_ID[id]; if (!r) return;
      $$('.rr-item[data-id="' + id + '"] .rr-vb').forEach(function (x) { x.disabled = true; });
      vote(r, v).then(function (res) {
        if (res) { r.up = res.up; r.down = res.down; r.last_confirmed = res.last_confirmed || r.last_confirmed; if (res.stale != null) r.stale = res.stale; }
        var m = myVotes(); m[id] = (res && res.my_vote) || v; store('vr_votes', m);
        $$('.rr-item[data-id="' + id + '"]').forEach(function (x) { x.outerHTML = item(r, x.querySelector('.rr-own') != null); });
      }).catch(function (e) {
        $$('.rr-item[data-id="' + id + '"] .rr-vb').forEach(function (x) { x.disabled = false; });
        toast(art, 'Vote not saved: ' + (e && e.message ? e.message : 'please try again'));
      });
    });
  }
  function vote(r, v) {
    if (DEMO) { if (v === 1) { r.up++; r.last_confirmed = new Date().toISOString().slice(0, 10); r.stale = false; } else r.down++; return Promise.resolve(null); }
    var voter = voterId();
    if (CFG.VOTE_FUNCTION && CFG.TURNSTILE_SITE_KEY) {
      return botToken().then(function (token) {
        return fetch(CFG.SUPABASE_URL.replace(/\/$/, '') + '/functions/v1/vote', {
          method: 'POST', headers: { 'Content-Type': 'application/json', apikey: CFG.SUPABASE_ANON_KEY, Authorization: 'Bearer ' + CFG.SUPABASE_ANON_KEY },
          body: JSON.stringify({ report_id: r.id, voter_id: voter, value: v, token: token })
        });
      }).then(function (x) { return x.json().then(function (d) { if (!x.ok) throw new Error(d.error || 'vote failed'); return d; }); });
    }
    return client(false).then(function (sb) { return sb.rpc('cast_vote', { p_report: r.id, p_voter: voter, p_value: v }); })
      .then(function (res) { if (res.error) throw res.error; return (res.data || [])[0]; });
  }
  function toast(el, msg) { var p = document.createElement('p'); p.className = 'rr-msg err'; p.textContent = msg; el.appendChild(p); setTimeout(function () { p.remove(); }, 6000); }

  // owner boxes on comparison pages
  function fillBoxes(list) {
    $$('details.rr').forEach(function (d) {
      var mine = list.filter(function (r) { return r.owner_id === d.getAttribute('data-owner'); });
      var n = $('.rr-n', d), body = $('.rr-body', d), post = 'submit.html?owner=' + encodeURIComponent(d.getAttribute('data-owner'));
      n.textContent = '(' + mine.length + ')';
      d.classList.toggle('has', mine.length > 0);
      body.innerHTML = (DEMO ? '<p class="rr-demo">Demo mode · sample data, not real reports</p>' : '') +
        (mine.length ? mine.map(function (r) { return item(r, false); }).join('') : '<p class="rr-empty">No reader reports yet.</p>') +
        '<p class="rr-actions"><a href="' + post + (DEMO ? '&demo=1' : '') + '">Post a report</a><span>·</span><a href="reports.html' + (DEMO ? '?demo=1' : '') + '">All reader reports</a></p>';
    });
    var h = location.hash.slice(1), target = h && document.getElementById(h);
    if (target && target.tagName === 'DETAILS') target.open = true;
  }
  function fillStrip(list) {
    var s = $('#rr-strip'); if (!s) return;
    var owners = {}; list.forEach(function (r) { owners[r.owner_id] = 1; });
    $('.rr-strip-n', s).textContent = list.length ? list.length + ' published report' + (list.length === 1 ? '' : 's') + ' across ' + Object.keys(owners).length + ' owner' + (Object.keys(owners).length === 1 ? '' : 's') + '.' : 'No reports yet.';
  }
  // reports.html
  function fillList(list) {
    var box = $('#rr-list'); if (!box) return;
    var fo = $('#rr-fo'), fc = $('#rr-fc'), fs = $('#rr-fs');
    $('#rr-filters').hidden = false;
    var pre = QS.get('owner'); if (pre && fo) fo.value = pre;
    function draw() {
      var o = fo.value, c = fc.value, hideStale = fs && fs.checked;
      var rows = list.filter(function (r) { return (!o || r.owner_id === o) && (!c || r.category === c) && !(hideStale && (r.stale != null ? r.stale : staleDate(r.last_confirmed))); });
      var groups = {}, order = [];
      rows.forEach(function (r) { var k = r.owner_id === 'other' ? 'other:' + (r.owner_other || '').toLowerCase() : r.owner_id; if (!groups[k]) { groups[k] = []; order.push(k); } groups[k].push(r); });
      var idx = function (k) { var i = OWNERS.findIndex(function (x) { return x.id === k; }); return i < 0 ? 999 : i; };
      order.sort(function (a, b) { return idx(a) - idx(b) || a.localeCompare(b); });
      $('#rr-count').textContent = rows.length;
      box.innerHTML = (DEMO ? '<p class="rr-demo">Demo mode · sample data, not real reports</p>' : '') + (order.length ? order.map(function (k) {
        var g = groups[k], o = OWN[g[0].owner_id], other = g[0].owner_id === 'other';
        return '<section class="rr-group"><header><span class="lc-logo">' + (o && !other ? o.logo : '<span class="olgs fix"><span class="olg fb">?</span></span>') + '</span>' +
          '<div><h2>' + esc(ownerName(g[0])) + '</h2><span class="note">' + esc(o && !other ? o.type : 'Other owner') + ' · ' + g.length + ' report' + (g.length === 1 ? '' : 's') + '</span></div>' +
          (o && !other ? '<a class="rr-off" href="' + esc(o.href) + '">Official criteria →</a>' : '') + '</header>' +
          '<div class="rr-items">' + g.map(function (r) { return item(r, false); }).join('') + '</div></section>';
      }).join('') : '<div class="rr-none"><p><b>No published reader reports' + (o || c ? ' for this filter' : ' yet') + '.</b></p><p class="note">Reports appear here after a two-step review.</p></div>');
    }
    [fo, fc, fs].forEach(function (x) { if (x) x.addEventListener('change', draw); });
    draw();
  }

  // ---------- auth (submit + admin) ----------
  function show(id, on) { var el = document.getElementById(id); if (el) el.hidden = !on; }
  function msg(el, text, bad) { if (!el) return; el.textContent = text; el.className = 'rr-msg' + (bad ? ' err' : ' ok'); el.hidden = !text; }
  function bindJoin(form, sb) {
    if (!form || form._bound) return; form._bound = true;
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var email = form.email.value.trim(), out = $('.rr-msg', form), btn = $('button', form);
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return msg(out, 'Enter a valid email address.', true);
      if (DEMO) return msg(out, 'Demo: no email sent.');
      btn.disabled = true;
      botToken().then(function (token) {
        var opts = { emailRedirectTo: location.origin + location.pathname, shouldCreateUser: true };
        if (token) opts.captchaToken = token;
        return sb.auth.signInWithOtp({ email: email, options: opts });
      }).then(function (res) {
        btn.disabled = false;
        if (res.error) return msg(out, res.error.message, true);
        msg(out, 'Check your inbox for a sign-in link. You can close this tab.');
      }).catch(function (e) { btn.disabled = false; msg(out, e.message || 'Something went wrong.', true); });
    });
  }
  function signOutLink(sb, who) {
    $$('.rr-who').forEach(function (w) {
      w.innerHTML = 'Signed in as <b>' + esc(who) + '</b> · <a href="#" class="rr-out">Sign out</a>';
      $('.rr-out', w).addEventListener('click', function (ev) { ev.preventDefault(); if (DEMO) return; sb.auth.signOut().then(function () { location.reload(); }); });
    });
  }
  function withSession(cb) {
    if (DEMO) return cb(null, DEMO === 'join' ? null : { user: { email: $('#rr-admin') ? 'admin@example.com' : 'member@example.com' } });
    client(true).then(function (sb) {
      sb.auth.getSession().then(function (r) { cb(sb, r.data && r.data.session); });
      sb.auth.onAuthStateChange(function (evt, s) { if (evt === 'SIGNED_IN' || evt === 'SIGNED_OUT') cb(sb, s); });
    }).catch(function () { var s = $('#rr-soon'); if (s) { s.hidden = false; s.textContent = 'Reader reports are unavailable right now. Please try again later.'; } });
  }

  // submit.html
  function initSubmit() {
    var root = $('#rr-submit'); if (!root) return;
    if (!LIVE && !DEMO) return; // "coming soon" stays
    show('rr-soon', false);
    var f = $('#rr-form');
    var pre = QS.get('owner'); if (pre && f.owner) { f.owner.value = OWN[pre] || pre === 'other' ? pre : ''; }
    var yr = f.year, now = new Date();
    for (var y = now.getFullYear(); y >= now.getFullYear() - 9; y--) yr.insertAdjacentHTML('beforeend', '<option>' + y + '</option>');
    f.month.value = String(now.getMonth() + 1);
    var other = function () { var on = f.owner.value === 'other'; $('#rr-other').hidden = !on; f.owner_other.required = on; };
    f.owner.addEventListener('change', other); other();
    var cnt = $('#rr-chars'); f.requirement.addEventListener('input', function () { cnt.textContent = f.requirement.value.length + ' / 300'; });
    var sbRef = null;
    withSession(function (sb, session) {
      sbRef = sb;
      var inn = !!(session && session.user);
      show('rr-join', !inn); show('rr-post', inn);
      bindJoin($('#rr-join form'), sb);
      if (inn) { signOutLink(sb, session.user.email); loadMine(sb); }
    });
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var out = $('#rr-form-msg'), btn = $('button[type=submit]', f);
      var m = +f.month.value, y = +f.year.value, faced = y + '-' + (m < 10 ? '0' : '') + m + '-01';
      if (new Date(y, m - 1, 1) > now) return msg(out, 'The month faced cannot be in the future.', true);
      if (f.requirement.value.trim().length < 10) return msg(out, 'Describe the requirement in at least 10 characters.', true);
      if (!f.rule_docs.checked || !f.rule_names.checked) return msg(out, 'Please tick both posting rules.', true);
      if (DEMO) return msg(out, 'Demo: nothing was sent.');
      btn.disabled = true;
      sbRef.rpc('submit_report', {
        p_owner_id: f.owner.value, p_owner_other: f.owner.value === 'other' ? f.owner_other.value.trim() : null, p_category: f.category.value,
        p_requirement: f.requirement.value.trim(), p_faced_on: faced, p_vessel_type: f.vessel_type.value || null, p_rules_accepted: true
      }).then(function (res) {
        btn.disabled = false;
        if (res.error) return msg(out, res.error.message, true);
        f.reset(); f.month.value = String(now.getMonth() + 1); other(); cnt.textContent = '0 / 300';
        msg(out, 'Thanks. Your report is in review. It appears publicly only after a bot check and the editor\'s approval.');
        loadMine(sbRef);
      }, function (e) { btn.disabled = false; msg(out, e.message || 'Something went wrong.', true); });
    });
  }
  var STAT = { pending: 'In review', published: 'Published', rejected: 'Not published' };
  function loadMine(sb) {
    var box = $('#rr-mine'); if (!box) return;
    var draw = function (rows) {
      box.hidden = !rows.length;
      $('ul', box).innerHTML = rows.map(function (r) { return '<li><span class="rr-st ' + esc(r.status) + '">' + esc(STAT[r.status] || r.status) + '</span><span>' + esc(ownerName(r)) + ' · ' + esc(r.requirement) + '</span></li>'; }).join('');
    };
    if (DEMO) return draw([{ owner_id: OWNERS[0] ? OWNERS[0].id : 'other', requirement: 'Example (not a real report): your earlier submission waiting for review.', status: 'pending' }]);
    sb.rpc('my_reports').then(function (res) { if (!res.error) draw(res.data || []); });
  }

  // admin.html
  function initAdmin() {
    var root = $('#rr-admin'); if (!root) return;
    if (!LIVE && !DEMO) return;
    show('rr-soon', false);
    withSession(function (sb, session) {
      var inn = !!(session && session.user);
      show('rr-join', !inn); bindJoin($('#rr-join form'), sb);
      if (!inn) { show('rr-queue', false); show('rr-denied', false); return; }
      signOutLink(sb, session.user.email);
      var load = function () {
        if (DEMO) return Promise.resolve({ data: [
          { id: 'demo-a', owner_id: OWNERS[0] ? OWNERS[0].id : 'other', category: 'crew', requirement: 'Example (not a real report): crew time onboard on the current contract no more than 10 months.', faced_on: '2026-08-01', vessel_type: 'product', status: 'bot_approved', bot_reason: 'No names, no copied text, specific.', created_at: '2026-10-15T09:12:00Z' },
          { id: 'demo-b', owner_id: 'other', owner_other: 'Example Terminal', category: 'terminal', requirement: 'Example (not a real report): placeholder text for a report still waiting for the bot check.', faced_on: '2026-09-01', vessel_type: null, status: 'pending', bot_reason: null, created_at: '2026-10-16T18:40:00Z' }
        ] });
        return sb.rpc('admin_list_reports');
      };
      var draw = function () {
        load().then(function (res) {
          if (res.error) { show('rr-queue', false); show('rr-denied', true); return; }
          show('rr-denied', false); show('rr-queue', true);
          var rows = res.data || [];
          [['bot_approved', '#rr-q2'], ['pending', '#rr-q1']].forEach(function (p) {
            var list = rows.filter(function (r) { return r.status === p[0]; }), el = $(p[1]);
            $('.rr-qn', el.parentNode).textContent = '(' + list.length + ')';
            el.innerHTML = list.length ? list.map(function (r) {
              return '<article class="rr-item rr-mod" data-id="' + esc(r.id) + '"><div class="rr-meta"><span class="rr-badge">User report</span>' + (DEMO ? '<span class="rr-ex">Example</span>' : '') +
                '<span class="rr-own">' + esc(ownerName(r)) + '</span><span class="pill">' + esc(CATS[r.category] || r.category) + '</span></div>' +
                '<p class="rr-text">' + esc(r.requirement) + '</p><div class="rr-foot"><span>Faced ' + esc(my(r.faced_on)) + (r.vessel_type ? ' · ' + esc(VT[r.vessel_type] || r.vessel_type) : '') + '</span><span>Submitted ' + esc(String(r.created_at).slice(0, 10)) + '</span>' +
                (r.bot_reason ? '<span>Check: ' + esc(r.bot_reason) + '</span>' : '') + '</div>' +
                '<div class="rr-modbar"><input type="text" maxlength="500" placeholder="Reason (optional, required to reject)" aria-label="Reason">' +
                '<button type="button" class="btn sm" data-a="approve">Approve</button><button type="button" class="btn sm light" data-a="reject">Reject</button></div></article>';
            }).join('') : '<p class="note">Nothing here.</p>';
          });
        });
      };
      if (!root._bound) {
        root._bound = true;
        root.addEventListener('click', function (ev) {
          var b = ev.target.closest && ev.target.closest('.rr-modbar button'); if (!b) return;
          var art = b.closest('.rr-item'), reason = $('input', art).value.trim(), act = b.getAttribute('data-a');
          if (act === 'reject' && !reason) { $('input', art).focus(); return toast(art, 'Add a reason to reject.'); }
          if (DEMO) return toast(art, 'Demo: no change made.');
          $$('button', art).forEach(function (x) { x.disabled = true; });
          sb.rpc('moderate_report', { p_id: art.getAttribute('data-id'), p_action: act, p_reason: reason || null }).then(function (res) {
            if (res.error) { $$('button', art).forEach(function (x) { x.disabled = false; }); return toast(art, res.error.message); }
            draw();
          });
        });
      }
      draw();
    });
  }

  // ---------- boot ----------
  function boot() {
    var reads = $$('details.rr').length || $('#rr-strip') || $('#rr-list');
    if (reads && (LIVE || DEMO)) {
      fetchPublished().then(function (list) {
        list.forEach(function (r) { BY_ID[r.id] = r; });
        fillBoxes(list); fillStrip(list); fillList(list);
        $$('details.rr, #rr-list').forEach(bindVotes);
      }).catch(function () {
        $$('details.rr .rr-body').forEach(function (b) { b.innerHTML = '<p class="rr-empty">Reader reports are unavailable right now.</p>'; });
        var l = $('#rr-list'); if (l) l.innerHTML = '<div class="rr-none"><p>Reader reports are unavailable right now. Please try again later.</p></div>';
      });
    }
    initSubmit(); initAdmin();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
