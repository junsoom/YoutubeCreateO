"""웹 이미지 검색 (Bing). 관련성 높은 사진 후보 찾기.

./.venv/bin/python web_image_search.py "mothman silver bridge photo" [개수]
스톡 사진 회사(게티·알라미·셔터스톡 등)와 영화 스틸은 걸러낸다 — 이들은 저작권 신고를 적극적으로 한다.
"""
import json
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
BLOCK = ("gettyimages", "alamy", "shutterstock", "istockphoto", "dreamstime", "depositphotos", "123rf", "adobe.com",
         "stock.adobe", "apimages", "reuters", "bridgeman", "imdb", "pinimg", "agefotostock", "superstock", "newscom",
         "fandom", "tmdb", "movieposter", "lookaside.instagram")


def search(q, n=20):
    """Bing 이미지 비동기 결과 페이지에서 원본 주소·출처 페이지를 뽑는다."""
    import html as H
    u = "https://www.bing.com/images/async?" + urllib.parse.urlencode({"q": q, "first": 0, "count": 60, "mmasync": 1, "setlang": "en"})
    page = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'class="iusc"[^>]*?\sm="([^"]+)"', page):
        try:
            d = json.loads(H.unescape(m.group(1)))
        except Exception:
            continue
        src = (d.get("murl", "") + " " + d.get("purl", "")).lower()
        if any(b in src for b in BLOCK):
            continue
        out.append(dict(title=d.get("t", "")[:80], image=d.get("murl"), page=d.get("purl")))
        if len(out) >= n:
            break
    return out


if __name__ == "__main__":
    for r in search(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 20):
        print(json.dumps(r, ensure_ascii=False))
