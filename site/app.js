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
