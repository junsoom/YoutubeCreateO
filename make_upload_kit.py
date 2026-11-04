"""업로드 안내문 만들기: 제목 후보, 설명(사진 출처 포함), 태그, 고정 댓글, Studio 설정.

./.venv/bin/python make_upload_kit.py episodes/001_mothman_short.json
→ output/<id>/업로드_안내.md  (+ 썸네일로 고를 만한 장면 jpg)
스펙의 "upload" 블록을 읽는다. 사진 출처는 assets/photos/credits.json 에서 자동으로 만든다.
"""
import json
import re
import sys
from pathlib import Path

from engine import render
from engine.photo import credits

LIC_URL = {"CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
           "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
           "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
           "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/"}


def credit_lines(spec):
    used = []
    for b in spec["beats"]:
        k = b.get("params", {}).get("key")
        if k and k not in used:
            used.append(k)
    out = []
    for k in used:
        c = credits().get(k)
        if not c:
            continue
        lic = c["license"].replace("No restrictions", "Public domain")
        if not lic.startswith("CC BY"):   # 퍼블릭 도메인·CC0·웹 사진은 표기 의무 없음 → 설명란 깔끔하게
            continue
        url = c.get("license_url") or LIC_URL.get(lic, "")
        mod = " (색 보정·자르기)" if lic.startswith("CC BY") else ""
        line = f"· \"{Path(c['file']).stem}\" — {c['author']} / {lic}{mod}"
        if url and lic.startswith("CC BY"):
            line += f" {url}"
        line += f"\n  {c['source']}"
        out.append(line)
    return out


def credit_lines_compact(spec):
    """설명란 5,000자 제한을 넘을 때: 라이선스별로 작가만 묶는다 (사진마다 화면에 작가·라이선스가 이미 뜬다)."""
    used = []
    for b in spec["beats"]:
        k = b.get("params", {}).get("key")
        if k and k not in used:
            used.append(k)
    groups, pd = {}, 0
    for k in used:
        c = credits().get(k)
        if not c:
            continue
        lic = c["license"].replace("No restrictions", "Public domain")
        if not lic.startswith("CC BY"):
            pd += 1
            continue
        who = re.sub(r"\s+", " ", c["author"]).strip()[:40] or "Unknown"
        g = groups.setdefault(lic, {})
        g[who] = g.get(who, 0) + 1
    out = []
    for lic in sorted(groups):
        url = LIC_URL.get(lic) or next((credits()[k].get("license_url") for k in used
                                         if credits().get(k, {}).get("license") == lic), "")
        names = ", ".join(f"{w}" + (f" ({n}장)" if n > 1 else "") for w, n in groups[lic].items())
        out.append(f"· {lic} {url}\n  {names}")
    out.append(f"· 퍼블릭 도메인·CC0 {pd}장")
    out.append("※ CC 사진은 모두 색 보정·자르기를 했습니다. 사진마다 화면 오른쪽 아래에 작가와 라이선스를 표기했습니다.")
    return out

def description(spec):
    """설명란 전체 (본문 + 사진 출처 + 해시태그). upload.py 도 같은 함수를 쓴다."""
    up = spec["upload"]
    desc = "\n".join(up["description"]) + ("\n\n[사진 출처 · Wikimedia Commons]\n" + "\n".join(credit_lines(spec)) if credit_lines(spec) else "") \
        + "\n\n" + " ".join(up["hashtags"])
    if len(desc) > 4900:   # 유튜브 설명란은 5,000자까지
        desc = "\n".join(up["description"]) + "\n\n[사진 출처 · Wikimedia Commons]\n" \
            + "\n".join(credit_lines_compact(spec)) + "\n\n" + " ".join(up["hashtags"])
    return desc.replace("<", "〈").replace(">", "〉")   # 설명란에 꺾쇠는 못 쓴다


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    up = spec["upload"]
    long_form = spec.get("format") == "long"
    out_dir = Path("output") / spec["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    desc = description(spec)
    if len(desc) > 5000:
        print(f"!! 설명란 {len(desc)}자 — 5,000자를 넘습니다. 본문을 줄이세요.")
    md = [f"# 업로드 안내 — {spec['id']}", "",
          "## 제목 (하나 고르기, 100자 이내)"]
    md += [f"{i + 1}. {t}{'  ← 추천' if i == 0 else ''}" for i, t in enumerate(up["titles"])]
    md += ["", "## 설명 (그대로 붙여 넣기)", "```", desc, "```", "",
           f"설명 글자 수: {len(desc)} / 5000", "",
           "## 태그 (Studio → 자세히 보기 → 태그, 쉼표로 붙여 넣기)", "```", ", ".join(up["tags"]), "```", "",
           "## 고정 댓글 (올린 뒤 댓글 달고 '고정')", "```", up["pinned"], "```", "",
           "## Studio 설정",
           "- 시청자층: **아동용 아님**",
           "- 연령 제한: 없음",
           "- 카테고리: 엔터테인먼트 · 언어: 한국어",
           ("- 변경되거나 합성된 콘텐츠: **예** — 실제 사진에 형체를 합성한 재현 장면이 있다" if up.get("synthetic")
            else "- 변경되거나 합성된 콘텐츠: 아니요 (실제 기록 사진 + AI 내레이션만. 실제처럼 보이는 합성 장면 없음)"),
           "- 라이선스: 표준 YouTube 라이선스",
           ("- 최종 화면: 마지막 20초에 '구독' 과 '다음 파일(롱폼)' 카드를 넣는다. 같은 주제 쇼츠가 있으면 카드로도 연결한다"
            if long_form else
            "- 관련 동영상: 같은 주제 롱폼이 올라가면 이 쇼츠의 '관련 동영상'에 롱폼을 연결한다 (쇼츠 → 롱폼 유입)"),
           ""]
    tl = json.loads((out_dir / "timeline.json").read_text())
    picks = []
    for b in tl["beats"]:
        if "eyes" in b["ev"]:
            picks.append(round(b["t0"] + b["ev"]["eyes"] + 0.8, 1))
    if not picks:   # 붉은 눈이 없는 편: 첫 장면과 임팩트 장면
        picks = [1.0] + [round(b["t0"] + (b["t1"] - b["t0"]) * 0.6, 1) for b, s in zip(tl["beats"], spec["beats"])
                         if s.get("impact")][1:3]
    if long_form:
        thumbs = sorted(out_dir.glob("썸네일_*.jpg"))
        md += ["## 썸네일 (업로드할 때 '썸네일 업로드' 로 직접 올리기)",
               (f"만들어 둔 파일: {thumbs[0].name}" if thumbs
                else "아직 없음 → ./.venv/bin/python make_thumbnail.py 로 만든다"),
               "다시 만들 장면 후보: " + ", ".join(f"{t}초" for t in picks), ""]
    else:
        md += ["## 쇼츠 썸네일 (모바일 앱에서 장면 고르기)",
               "눈에 잘 띄는 장면: " + ", ".join(f"{t}초" for t in picks), ""]
    (out_dir / "업로드_안내.md").write_text("\n".join(md))
    comp = render.Composer(tl, spec)
    for t in picks:
        comp.frame(t, int(t * 30)).save(out_dir / f"썸네일후보_{t}초.jpg", quality=90)
    print("\n".join(md))


if __name__ == "__main__":
    main()
