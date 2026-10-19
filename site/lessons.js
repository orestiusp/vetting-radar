// Vetting Radar – safety lessons: hub filters, print and copy buttons, GoatCounter events (no dependencies)
(function(){
  function gc(path,title){try{if(window.goatcounter&&window.goatcounter.count)window.goatcounter.count({path:path,title:title||path,event:true});}catch(e){}}
  document.addEventListener('DOMContentLoaded',function(){
    // print / save as PDF (toolbox talk) and copy link (lesson page)
    document.querySelectorAll('[data-print]').forEach(function(b){b.addEventListener('click',function(){window.print();});});
    document.querySelectorAll('[data-copy]').forEach(function(b){b.addEventListener('click',function(){
      var done=function(){b.textContent='Link copied';setTimeout(function(){b.textContent='Copy link';},2000);};
      if(navigator.clipboard)navigator.clipboard.writeText(location.href.split('#')[0]).then(done,function(){});});});
    // hub filters
    var form=document.getElementById('lf'); if(!form) return;
    form.addEventListener('submit',function(ev){ev.preventDefault();});
    var q=document.getElementById('lf-q'), sel={topic:'lf-topic',vt:'lf-vt',sire:'lf-sire',src:'lf-src'};
    Object.keys(sel).forEach(function(k){sel[k]=document.getElementById(sel[k]);});
    var cards=[].slice.call(document.querySelectorAll('#lcards .lcard'));
    var pills=[].slice.call(document.querySelectorAll('.topicbar a[data-topic]'));
    var count=document.getElementById('lf-count'), empty=document.getElementById('lf-empty'), reset=document.getElementById('lf-reset');
    var KEYS={topic:'topic',vt:'vessel',sire:'sire',src:'source'};
    function run(push){
      var term=(q.value||'').toLowerCase().trim(), n=0, v={};
      Object.keys(sel).forEach(function(k){v[k]=sel[k]?sel[k].value:'';});
      cards.forEach(function(c){
        var vt=(c.dataset.vt||'').split(' ');
        var ok=(!term||(c.textContent.toLowerCase()+' '+(c.dataset.k||'')).indexOf(term)>-1)&&(!v.topic||c.dataset.topic===v.topic)
          &&(!v.vt||vt.indexOf(v.vt)>-1||(v.vt!=='other'&&vt.indexOf('all-tankers')>-1))
          &&(!v.sire||(c.dataset.sire||'').split(' ').indexOf(v.sire)>-1)&&(!v.src||c.dataset.src===v.src);
        c.hidden=!ok; if(ok)n++;
      });
      count.textContent=n; empty.hidden=n>0; reset.hidden=!(term||v.topic||v.vt||v.sire||v.src);
      pills.forEach(function(p){p.classList.toggle('on',p.dataset.topic===v.topic);});
      if(push&&window.history&&history.replaceState){
        var u=new URLSearchParams(); Object.keys(KEYS).forEach(function(k){if(v[k])u.set(KEYS[k],v[k]);});
        history.replaceState(null,'',location.pathname+(u.toString()?'?'+u.toString():''));
      }
    }
    // deep links: lessons.html?topic=mooring&sire=9
    var params=new URLSearchParams(location.search);
    Object.keys(KEYS).forEach(function(k){var x=params.get(KEYS[k]); if(x&&sel[k]&&[].some.call(sel[k].options,function(o){return o.value===x;}))sel[k].value=x;});
    Object.keys(sel).forEach(function(k){if(sel[k])sel[k].addEventListener('change',function(){run(true); if(sel[k].value)gc('filter-'+KEYS[k]+'-'+sel[k].value,'Lessons filter: '+KEYS[k]);});});
    var searched=false, t=null;
    q.addEventListener('input',function(){run(false); clearTimeout(t); t=setTimeout(function(){if(!searched&&q.value.trim().length>2){searched=true;gc('filter-search','Lessons search used');}},1200);});
    pills.forEach(function(p){p.addEventListener('click',function(ev){ev.preventDefault(); sel.topic.value=p.dataset.topic; run(true); if(p.dataset.topic)gc('filter-topic-'+p.dataset.topic,'Lessons filter: topic');});});
    reset.addEventListener('click',function(){q.value='';Object.keys(sel).forEach(function(k){if(sel[k])sel[k].value='';});run(true);});
    run(false);
  });
})();
