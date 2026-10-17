// Vetting Radar – tiny client-side filters (no dependencies)
function vrFilter(tableId, inputId, selectId, col){
  const t=document.getElementById(tableId); if(!t) return;
  const q=document.getElementById(inputId), s=selectId?document.getElementById(selectId):null;
  const count=document.getElementById(tableId+'-count');
  function run(){
    const term=(q.value||'').toLowerCase().trim(), sel=s?s.value:'';
    let n=0;
    t.querySelectorAll('tbody tr').forEach(tr=>{
      const okText=!term||tr.innerText.toLowerCase().includes(term);
      const okSel=!sel||tr.dataset[col]===sel;
      const show=okText&&okSel; tr.style.display=show?'':'none'; if(show) n++;
    });
    if(count) count.textContent=n;
  }
  q.addEventListener('input',run); if(s) s.addEventListener('change',run); run();
}
