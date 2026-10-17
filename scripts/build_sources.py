import json, re, datetime
res=json.load(open('data/url_check.json'))
drop={'https://www.ocimf.org/document-libary','https://logitechglobal.com/primorsk-trade-port/tanker-vetting-and-risk-assessment-policy/'}
seen=set(); out=[]
def slug(s):
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')[:60]
today=datetime.date.today().isoformat()
for r in res:
    u=r['url']
    if u in drop or u in seen: continue
    uscg = 'dco.uscg.mil' in u
    if uscg and not u.endswith('/Detentions/'): continue
    if r['status']!=200 and not uscg: continue
    seen.add(u)
    s=dict(id=slug(r['owner']+'-'+r['name'].split('–')[-1]), name=r['name'], owner=r['owner'], url=u,
           type='pdf' if r.get('pdf') else 'html', category=r['cat'],
           verified_status=r['status'] if not uscg else 'ok-via-external-fetch (403 to box client)',
           verified_at=today)
    if uscg:
        s['type']='html'; s['note']='USCG blocks scripted clients from this box (HTTP 403). Page verified loading via an external fetch on '+today+'. Monitor will log a fetch error until run from a different network.'
    if r.get('final') and r['final']!=u: s['final_url']=r['final']
    out.append(s)
ids=[s['id'] for s in out]; assert len(ids)==len(set(ids)), [i for i in ids if ids.count(i)>1]
json.dump({'generated':today,'count':len(out),'sources':out},open('sources.json','w'),indent=2,ensure_ascii=False)
print(len(out))
from collections import Counter; print(Counter(s['category'] for s in out)); print(Counter(s['type'] for s in out))
