import json,time,urllib.request,urllib.parse,sys
UA={"User-Agent":"File404ResearchBot/1.0 (research notes; contact: local)"}
def api(params):
    params=dict(params,format='json')
    u="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode(params)
    for i in range(5):
        try:
            r=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60)
            time.sleep(4); return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(20); continue
            raise
    raise Exception('fail')
out=json.load(open('commons_cats.json')) if __import__('os').path.exists('commons_cats.json') else {}
for cat in sys.argv[1:]:
    if cat in out: continue
    d=api({'action':'query','generator':'categorymembers','gcmtitle':cat,'gcmtype':'file|subcat','gcmlimit':'100','prop':'imageinfo','iiprop':'size|extmetadata','iiextmetadatafilter':'LicenseShortName|Artist|DateTimeOriginal|ImageDescription|UsageTerms'})
    pages=d.get('query',{}).get('pages',{})
    res=[]
    for p in pages.values():
        ii=(p.get('imageinfo') or [{}])[0]; em=ii.get('extmetadata',{})
        res.append({'title':p['title'],'w':ii.get('width'),'h':ii.get('height'),'lic':em.get('LicenseShortName',{}).get('value'),'artist':em.get('Artist',{}).get('value','')[:120],'date':em.get('DateTimeOriginal',{}).get('value','')[:40],'desc':em.get('ImageDescription',{}).get('value','')[:200]})
    out[cat]=res
    json.dump(out,open('commons_cats.json','w'),ensure_ascii=False,indent=1)
    print(cat,len(res))
