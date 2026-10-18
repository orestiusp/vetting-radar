// Vetting Radar · vessel-profile lookup on table.html (no dependencies, no network).
// Rules come from data/lookup.json, a machine-readable restatement of the table's own values.
// Statuses: pass · fail · unclear (the source cannot decide) · need (an extra condition we cannot check) · info.
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var RULES = {}, SRC = {};
  try { RULES = JSON.parse($('#vr-lookup').textContent); SRC = JSON.parse($('#vr-src').textContent); } catch (e) { return; }
  var FIELD = { age_limits: 'Vessel age', sire_report_age: 'SIRE / inspection', cap_rules: 'CAP', other_criteria: 'Other criteria', flags: 'Source note' };
  var TYPE = { oil: 'oil tankers', chemical: 'chemical tankers', lpg: 'LPG carriers', lng: 'LNG carriers' };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var num = function (v) { v = String(v == null ? '' : v).replace(',', '.').trim(); return v === '' || isNaN(+v) ? null : +v; };

  // does a rule apply to this profile? true / false / 'dwt' (depends on a DWT we don't have)
  function applies(r, p) {
    if (r.types && r.types.indexOf(p.type) < 0) return false;
    var a = p.age;
    if (r.age_gt != null && !(a > r.age_gt)) return false;
    if (r.age_ge != null && !(a >= r.age_ge)) return false;
    if (r.age_lt != null && !(a < r.age_lt)) return false;
    if (r.age_le != null && !(a <= r.age_le)) return false;
    if (r.dwt_gt != null || r.dwt_lt != null || r.dwt_ge != null) {
      if (p.dwt == null) return 'dwt';
      if (r.dwt_gt != null && !(p.dwt > r.dwt_gt)) return false;
      if (r.dwt_lt != null && !(p.dwt < r.dwt_lt)) return false;
      if (r.dwt_ge != null && !(p.dwt >= r.dwt_ge)) return false;
    }
    return true;
  }
  function judge(r, p) {
    switch (r.k) {
      case 'age_max': return p.age > r.max ? ['fail', 'Over the ' + r.max + '-year limit'] : ['pass', 'Within the ' + r.max + '-year limit'];
      case 'age_band': return ['unclear', 'Depends on wording or charter type'];
      case 'need': return ['need', 'Extra condition'];
      case 'info': return ['info', ''];
      case 'cap':
        var res;
        if (p.cap == null) res = ['need', 'CAP ' + r.min + ' or better required'];
        else if (p.cap <= r.min) res = ['pass', 'CAP ' + p.cap + ' meets CAP ' + r.min + ' or better'];
        else if (r.split && p.cap <= r.split) res = ['unclear', 'CAP ' + p.cap + ': fine for machinery and cargo, hull must be CAP ' + r.min];
        else res = ['fail', 'CAP ' + p.cap + ' is below the required CAP ' + r.min];
        if (r.conflict_below && p.age < r.conflict_below && res[0] !== 'pass') res = ['unclear', r.c];
        return res;
      case 'sire_max':
        if (p.sire == null) return ['need', 'SIRE ' + (r.lt ? 'under ' : 'no older than ') + r.max + ' months'];
        var over = r.lt ? p.sire >= r.max : p.sire > r.max;
        if (!over) return ['pass', p.sire + ' months is within ' + r.max];
        return r.soft ? ['unclear', p.sire + ' months is over the preferred ' + r.max + ' (' + r.soft + ')'] : ['fail', p.sire + ' months is over the ' + r.max + '-month limit'];
    }
    return ['info', ''];
  }
  var ORDER = { fail: 0, unclear: 1, need: 2, pass: 3, info: 4 };
  var BADGE = { fail: 'Fails', unclear: 'Unclear · check source', need: 'Meets limits · conditions apply', pass: 'Meets stated criteria', none: 'No criteria for this profile' };
  function check(id, p) {
    var rules = RULES[id] || [], out = [], ageRule = false, hasAge = rules.some(function (r) { return r.k === 'age_max'; });
    rules.forEach(function (r) {
      var a = applies(r, p); if (!a) return;
      if (r.k === 'age_max') ageRule = true;
      if (a === 'dwt') { if (r.k !== 'info') out.push({ s: 'unclear', w: 'Depends on DWT: enter it to check', r: r }); return; }
      var j = judge(r, p); out.push({ s: j[0], w: j[1], r: r });
    });
    if (hasAge && !ageRule) out.push({ s: 'info', w: 'No age limit stated for ' + TYPE[p.type] + ' or this size', r: { f: 'age_limits', t: '' } });
    var real = out.filter(function (x) { return x.s !== 'info'; });
    var v = !real.length ? 'none' : real.reduce(function (m, x) { return ORDER[x.s] < ORDER[m] ? x.s : m; }, 'pass');
    out.sort(function (a, b) { return ORDER[a.s] - ORDER[b.s]; });
    return { v: v, lines: out };
  }
  function render(id, res) {
    var src = SRC[id];
    return '<span class="vb ' + res.v + '">' + BADGE[res.v] + '</span><ul class="vlines">' + res.lines.map(function (x) {
      return '<li class="' + x.s + '"><span class="vs" aria-hidden="true"></span><span>' + (x.w ? '<b>' + esc(x.w) + '.</b> ' : '') + esc(x.r.t || '') +
        ' <span class="vf">' + esc(FIELD[x.r.f] || '') + (src ? ' · <a href="' + esc(src) + '" rel="noopener">source</a>' : '') + '</span></span></li>';
    }).join('') + (res.v === 'none' ? '<li class="unclear"><span class="vs"></span><span>The public source sets no limit we can check for this profile. <a href="' + esc(src || '#') + '" rel="noopener">Check the source</a>.</span></li>' : '') + '</ul>';
  }
  var form = $('#vp'), tbl = $('#cmp'), sum = $('#vp-sum');
  if (!form || !tbl) return;
  function profile() {
    return { type: form.type.value, age: num(form.age.value), dwt: num(form.dwt.value), cap: num(form.cap.value), sire: num(form.sire.value) };
  }
  function run(push) {
    var p = profile();
    if (p.age == null) { tbl.classList.remove('has-profile'); sum.hidden = true; $$('td.res', tbl).forEach(function (td) { td.innerHTML = ''; }); if (push) history.replaceState(null, '', location.pathname); return; }
    var n = { pass: 0, need: 0, unclear: 0, fail: 0, none: 0 };
    $$('tr.off-row', tbl).forEach(function (tr) {
      var id = tr.getAttribute('data-id'), res = check(id, p); n[res.v]++;
      tr.setAttribute('data-v', res.v); $('td.res', tr).innerHTML = render(id, res);
    });
    tbl.classList.add('has-profile');
    sum.hidden = false;
    sum.innerHTML = '<b>' + esc(form.type.options[form.type.selectedIndex].text) + ', ' + p.age + ' years' + (p.dwt != null ? ', ' + p.dwt.toLocaleString('en-GB') + ' dwt' : '') +
      (p.cap != null ? ', CAP ' + p.cap : '') + (p.sire != null ? ', SIRE ' + p.sire + ' months old' : '') + ':</b> ' +
      '<span class="vb pass">' + n.pass + ' meet</span><span class="vb need">' + n.need + ' meet limits, conditions apply</span><span class="vb unclear">' + (n.unclear + n.none) + ' unclear</span><span class="vb fail">' + n.fail + ' fail</span>' +
      (p.dwt == null ? ' <span class="note">Add DWT for size-dependent limits.</span>' : '');
    if (push) {
      var q = new URLSearchParams(); ['type', 'age', 'dwt', 'cap', 'sire'].forEach(function (k) { if (form[k].value !== '') q.set(k, form[k].value); });
      history.replaceState(null, '', location.pathname + '?' + q.toString() + location.hash);
    }
  }
  var qs = new URLSearchParams(location.search);
  ['type', 'age', 'dwt', 'cap', 'sire'].forEach(function (k) { if (qs.has(k) && form[k]) form[k].value = qs.get(k); });
  form.addEventListener('submit', function (ev) { ev.preventDefault(); run(true); });
  form.addEventListener('reset', function () { setTimeout(function () { run(true); }, 0); });
  run(false);
  if (window.vrFilter) vrFilter('cmp', 'q', 't', 'type');
})();
