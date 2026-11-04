#!/usr/bin/env python3
# 임시 수집 스크립트 (016_nessie_3_science.md 용). 작업 끝나면 삭제한다.
# 위키미디어 공용 메타데이터만 수집. 이미지 다운로드 없음.
import json, time, urllib.parse, urllib.request, urllib.error, sys, re

API = "https://commons.wikimedia.org/w/api.php"
UA = "File404ResearchBot/1.0 (https://example.org/file404; research@example.org) python-urllib"

def call(params, tries=4):
    params = dict(params); params["format"] = "json"; params["formatversion"] = "2"
    url = API + "?" + urllib.parse.urlencode(params)
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                sys.stderr.write("429 -> sleep 20\n"); time.sleep(20); continue
            sys.stderr.write("HTTP %s %s\n" % (e.code, url)); time.sleep(5)
        except Exception as e:
            sys.stderr.write("ERR %s\n" % e); time.sleep(5)
    return {}

def search(term, limit=12):
    d = call({"action": "query", "generator": "search", "gsrsearch": term,
              "gsrnamespace": "6", "gsrlimit": str(limit),
              "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime",
              "iiextmetadatafilter": "LicenseShortName|License|Artist|Credit|DateTimeOriginal|ImageDescription|UsageTerms|Permission|ObjectName"})
    out = []
    for p in (d.get("query", {}) or {}).get("pages", []) or []:
        ii = (p.get("imageinfo") or [{}])[0]
        em = ii.get("extmetadata", {}) or {}
        def g(k):
            v = em.get(k, {}).get("value", "")
            import re
            v = re.sub(r"<[^>]+>", " ", str(v))
            v = v.replace("&amp;", "&").replace("&#160;", " ").replace("&quot;", '"')
            return " ".join(v.split())
        out.append({
            "title": p.get("title"),
            "w": ii.get("width"), "h": ii.get("height"), "mime": ii.get("mime"),
            "lic": g("LicenseShortName"), "usage": g("UsageTerms"),
            "artist": g("Artist")[:160], "credit": g("Credit")[:120],
            "date": g("DateTimeOriginal")[:60],
            "desc": g("ImageDescription")[:400],
            "url": ii.get("descriptionurl"),
        })
    return out

TERMS = json.load(open(sys.argv[1]))
res = {}
for t in TERMS:
    res[t] = search(t)
    sys.stderr.write("done: %s (%d)\n" % (t, len(res[t])))
    time.sleep(4)
json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
print("saved", sys.argv[2])
