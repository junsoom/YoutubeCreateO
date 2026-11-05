import json, sys, time, urllib.request, urllib.parse

UA = "File404ResearchBot/1.0 (research notes; contact via user) python-urllib"
API = "https://commons.wikimedia.org/w/api.php"
OUT = "/Users/junhyunglee/.hermes/cache/scratch/f19_5/commons_results.json"


def call(params):
    params = dict(params, format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.load(r)
            time.sleep(4)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20)
                continue
            raise
    return {}


def meta_for_titles(titles):
    res = {}
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        d = call({"action": "query", "titles": "|".join(chunk), "prop": "imageinfo",
                  "iiprop": "size|extmetadata", "iiextmetadatafilter":
                  "LicenseShortName|Artist|DateTimeOriginal|ImageDescription|Credit|UsageTerms"})
        for p in d.get("query", {}).get("pages", []):
            if p.get("missing"):
                res[p["title"]] = None
                continue
            ii = (p.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata", {})
            g = lambda k: (em.get(k, {}) or {}).get("value", "")
            res[p["title"]] = {"w": ii.get("width"), "h": ii.get("height"),
                               "lic": g("LicenseShortName"), "artist": g("Artist")[:200],
                               "date": g("DateTimeOriginal")[:80], "desc": g("ImageDescription")[:300],
                               "credit": g("Credit")[:150]}
    return res


def search(q, n=20):
    d = call({"action": "query", "list": "search", "srsearch": q, "srnamespace": 6, "srlimit": n})
    return [x["title"] for x in d.get("query", {}).get("search", [])]


def category(c, n=200):
    d = call({"action": "query", "list": "categorymembers", "cmtitle": c, "cmtype": "file", "cmlimit": n})
    return [x["title"] for x in d.get("query", {}).get("categorymembers", [])]


if __name__ == "__main__":
    mode = sys.argv[1]
    try:
        store = json.load(open(OUT))
    except Exception:
        store = {}
    titles = []
    for arg in sys.argv[2:]:
        if mode == "search":
            t = search(arg)
        elif mode == "cat":
            t = category(arg)
        else:
            t = [arg]
        print("##", arg, len(t))
        titles += t
    titles = [t for t in dict.fromkeys(titles) if t not in store]
    m = meta_for_titles(titles) if titles else {}
    store.update(m)
    json.dump(store, open(OUT, "w"), ensure_ascii=False, indent=1)
    for t in titles:
        v = m.get(t)
        if v:
            print(f"{t} | {v['lic']} | {v['w']}x{v['h']} | {v['date'][:30]} | {v['artist'][:60]}")
        else:
            print(t, "MISSING")
