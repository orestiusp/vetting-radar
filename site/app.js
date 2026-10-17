// Vetting Radar – tiny client-side filters (no dependencies)
function vrFilter(tableId, inputId, selectId, col){
  const t=document.getElementById(tableId); if(!t) return;
  const q=document.getElementById(inputId), s=selectId?document.getElementById(selectId):null;
  const count=document.getElementById(tableId+'-count');
  function run(){
    const term=(q.value||'').toLowerCase().trim(), sel=s?s.value:'';
    let n=0;
    t.querySelectorAll('tbody tr:not(.rr-row)').forEach(tr=>{
      const okText=!term||tr.innerText.toLowerCase().includes(term);
      const okSel=!sel||tr.dataset[col]===sel;
      const show=okText&&okSel; tr.style.display=show?'':'none'; if(show) n++;
      const rr=tr.nextElementSibling; if(rr&&rr.classList.contains('rr-row')) rr.style.display=tr.style.display; // reader-report box follows its owner row
    });
    if(count) count.textContent=n;
  }
  q.addEventListener('input',run); if(s) s.addEventListener('change',run); run();
}
// sponsor slots: re-check start/end dates in the browser so an expired banner falls back to the placeholder between builds
document.addEventListener('DOMContentLoaded',()=>{
  const d=new Date(), today=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
  document.querySelectorAll('aside.sp').forEach(sp=>{
    const alts=[...sp.querySelectorAll('template.sp-alt')], ph=sp.querySelector('template.sp-ph'); if(!alts.length||!ph) return;
    const cur=alts.find(t=>t.dataset.start<=today&&today<=t.dataset.end)||ph, body=sp.querySelector('.sp-body');
    if(body) body.replaceWith(cur.content.cloneNode(true));
  });
});
