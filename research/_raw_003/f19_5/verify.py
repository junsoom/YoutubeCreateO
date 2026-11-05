import json,time,urllib.request,urllib.parse,re
UA={"User-Agent":"File404ResearchBot/1.0 (research notes; contact: local)"}
T=[l.strip() for l in open('titles.txt') if l.strip()]
out={}
for i in range(0,len(T),20):
    chunk=T[i:i+20]
    u="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode({'action':'query','format':'json','titles':'|'.join(chunk),'prop':'imageinfo','iiprop':'size|extmetadata','iiextmetadatafilter':'LicenseShortName|Artist|DateTimeOriginal|ImageDescription'})
    for k in range(6):
        try:
            d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60)); time.sleep(5); break
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(25); continue
            raise
    norm={n['to']:n['from'] for n in d['query'].get('normalized',[])}
    for p in d['query']['pages'].values():
        if 'missing' in p: out[p['title']]='MISSING'; continue
        ii=p['imageinfo'][0]; em=ii['extmetadata']; g=lambda k: re.sub('<[^>]+>','',em.get(k,{}).get('value','')).strip()
        out[p['title']]=dict(w=ii['width'],h=ii['height'],lic=g('LicenseShortName'),a=g('Artist')[:70],d=g('DateTimeOriginal')[:20],desc=g('ImageDescription')[:300])
json.dump(out,open('verified.json','w'),ensure_ascii=False,indent=1)
for t in T:
    k=t if t in out else None
    v=out.get(t,'NOT RETURNED (normalization?)')
    print(t[5:], '|', v if isinstance(v,str) else f"{v['w']}x{v['h']} | {v['lic']} | {v['a'][:40]} | {v['d']}")
