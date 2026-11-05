import json,time,urllib.request,urllib.parse,sys,os,re
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
F='res.json'
out=json.load(open(F)) if os.path.exists(F) else {}
P={'prop':'imageinfo','iiprop':'size|extmetadata','iiextmetadatafilter':'LicenseShortName|Artist|DateTimeOriginal|ImageDescription|Credit'}
for q in sys.argv[1:]:
    if q in out: continue
    if q.startswith('Category:'):
        d=api(dict(P,action='query',generator='categorymembers',gcmtitle=q,gcmtype='file',gcmlimit='60'))
    else:
        d=api(dict(P,action='query',generator='search',gsrsearch=q,gsrnamespace='6',gsrlimit='25'))
    res=[]
    for p in d.get('query',{}).get('pages',{}).values():
        ii=(p.get('imageinfo') or [{}])[0]; em=ii.get('extmetadata',{})
        g=lambda k: re.sub('<[^>]+>','',em.get(k,{}).get('value',''))
        res.append({'t':p['title'],'w':ii.get('width'),'h':ii.get('height'),'lic':g('LicenseShortName'),'a':g('Artist')[:80],'d':g('DateTimeOriginal')[:25],'desc':g('ImageDescription')[:160]})
    out[q]=res
    json.dump(out,open(F,'w'),ensure_ascii=False,indent=0)
    print(q,len(res),flush=True)
