import json,sys,urllib.request,urllib.parse,time
UA={'User-Agent':'File404Research/1.0 (contact: local)'}
def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60).read())
item=sys.argv[1]
md=get(f'https://archive.org/metadata/{item}')
srv=md['server']; d=md['dir']
for q in sys.argv[2:]:
    u=f'https://{srv}/fulltext/inside.php?'+urllib.parse.urlencode({'item_id':item,'doc':item,'path':d,'q':q})
    try:
        r=get(u)
    except Exception as e:
        print(q,'ERR',e); continue
    print('==',item,q,len(r.get('matches',[])))
    for m in r.get('matches',[])[:6]:
        pg=m.get('par',[{}])[0].get('page')
        print('  p',pg,':',m['text'].replace('\n',' ')[:400])
    time.sleep(2)
