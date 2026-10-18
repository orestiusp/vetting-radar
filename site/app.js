// Vetting Radar – tiny client-side filters (no dependencies)
function vrFilter(tableId, inputId, selectId, col){
  const t=document.getElementById(tableId); if(!t) return;
  const q=document.getElementById(inputId), s=selectId?document.getElementById(selectId):null;
  const count=document.getElementById(tableId+'-count');
  function run(){
    const term=(q.value||'').toLowerCase().trim(), sel=s?s.value:'';
    let n=0;
    t.querySelectorAll('tbody tr:not(.rr-row)').forEach(tr=>{
      const okText=!term||tr.textContent.toLowerCase().includes(term);
      const okSel=!sel||tr.dataset[col]===sel;
      const show=okText&&okSel; tr.style.display=show?'':'none'; if(show) n++;
      const rr=tr.nextElementSibling; if(rr&&rr.classList.contains('rr-row')) rr.style.display=tr.style.display; // reader-report box follows its owner row
    });
    if(count) count.textContent=n;
  }
  q.addEventListener('input',run); if(s) s.addEventListener('change',run); run();
}
// mobile menu (hamburger) and active Compare tab kept in view
document.addEventListener('DOMContentLoaded',()=>{
  const h=document.querySelector('header.site'), b=h&&h.querySelector('.navtoggle');
  if(b){
    const set=on=>{h.classList.toggle('open',on);b.setAttribute('aria-expanded',on?'true':'false');b.setAttribute('aria-label',on?'Close menu':'Menu');};
    b.addEventListener('click',()=>set(!h.classList.contains('open')));
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&h.classList.contains('open')){set(false);b.focus();}});
    h.querySelectorAll('nav.main a').forEach(a=>a.addEventListener('click',()=>set(false)));
  }
  const on=document.querySelector('.subnav a.on'), w=on&&on.parentElement;
  if(on&&w.scrollWidth>w.clientWidth) w.scrollLeft=on.offsetLeft-(w.clientWidth-on.offsetWidth)/2;
});
// wide tables: fade + hint at the scrolling edge, stronger edge on the fixed column once scrolled
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.tablewrap').forEach(tw=>{
    const box=document.createElement('div'); box.className='tscroll'; tw.parentNode.insertBefore(box,tw); box.appendChild(tw);
    const hint=document.createElement('p'); hint.className='thint'; hint.setAttribute('aria-hidden','true'); hint.textContent='Scroll sideways for more columns →'; box.parentNode.insertBefore(hint,box);
    const upd=()=>{const max=tw.scrollWidth-tw.clientWidth, s=max>4;
      box.classList.toggle('scrolls',s); box.classList.toggle('more-r',s&&tw.scrollLeft<max-4); box.classList.toggle('more-l',s&&tw.scrollLeft>4);
      hint.classList.toggle('on',s&&getComputedStyle(tw).overflowX!=='visible');};
    tw.addEventListener('scroll',upd,{passive:true}); window.addEventListener('resize',upd); upd();
    new MutationObserver(upd).observe(tw,{subtree:true,attributes:true,attributeFilter:['class','open','style']}); // lookup adds the "Your vessel" column
  });
});
// newsletter signup safety net: if the Beehiiv embed has not drawn a real form within ~4 s (Beehiiv hides it for
// visitors who already subscribed from this site, or its script is blocked/slow), show a plain "Subscribe free" button.
document.addEventListener('DOMContentLoaded',()=>{
  const boxes=[...document.querySelectorAll('.signup .bh-crop')].map(c=>c.closest('.signup')); if(!boxes.length) return;
  // the loader marks the iframe data-bhv-sized once the form inside has reported its size; until then its wrapper is height:0
  const drawn=s=>{const f=s.querySelector('.bh-form iframe'); if(!f) return false; const w=f.parentElement;
    return f.hasAttribute('data-bhv-sized') && (parseFloat(f.style.height)||0)>150 && !(w&&w.style.height==='0px');};
  const subscribed=/(^|;\s*)bhv_[\w-]+_subscribed=/.test(document.cookie);
  const check=()=>boxes.forEach(s=>{const ok=drawn(s), fb=s.querySelector('.bh-fb'); if(!fb) return;
    if(!ok && subscribed && !fb.dataset.sub){fb.dataset.sub='1'; const t=fb.querySelector('.bh-fb-t'); t.classList.add('done');
      t.innerHTML='<b>You\u2019re subscribed from this browser \u2713</b>Want the brief at another address too?';}
    fb.classList.toggle('on',!ok); s.classList.toggle('bh-off',!ok);
    const n=s.querySelector('.bh-fallback'); if(n) n.hidden=!ok;});
  setTimeout(check,4000); setTimeout(check,10000); // the second pass hides the button again if the form arrives late
});
