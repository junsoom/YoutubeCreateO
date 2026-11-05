import json, sys
for fn in sys.argv[1:]:
    d = json.load(open(fn))
    for p in d['query']['pages'].values():
        print('=====', p.get('title'))
        print(p.get('extract', '')[:int(60000)])
