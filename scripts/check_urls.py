import csv, requests, concurrent.futures as cf, json
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 VettingRadarBot/0.1"}
rows=[r for r in csv.reader(open('data/candidates_all.tsv'),delimiter='\t') if r]
def chk(r):
    name,owner,url,cat=r
    try:
        x=requests.get(url,headers=UA,timeout=40,allow_redirects=True)
        ct=x.headers.get('content-type','')
        return dict(name=name,owner=owner,url=url,cat=cat,status=x.status_code,ct=ct.split(';')[0],final=x.url,size=len(x.content),pdf=x.content[:4]==b'%PDF')
    except Exception as e:
        return dict(name=name,owner=owner,url=url,cat=cat,status=0,err=str(e)[:120])
with cf.ThreadPoolExecutor(12) as ex: res=list(ex.map(chk,rows))
json.dump(res,open('data/url_check.json','w'),indent=1)
for r in res: print(r['status'],r.get('ct',''),r.get('size',''),r.get('pdf',''),r['url'][:100],r.get('err',''), ('-> '+r['final'][:80]) if r.get('final') and r['final']!=r['url'] else '')
