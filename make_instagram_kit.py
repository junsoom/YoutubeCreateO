"""인스타그램 키트: 릴스 캡션 + 카드뉴스(캐러셀) 슬라이드.

./.venv/bin/python make_instagram_kit.py episodes/002_loch_ness_short.json
→ output/<id>/instagram/ 에 slide_01.jpg … (1080×1350), 캡션.txt
릴스 영상은 유튜브 쇼츠 mp4 를 그대로 올린다 (9:16, 90초 이하).
스펙의 "instagram" 블록이 있으면 그걸 쓰고, 없으면 쇼츠 장면에서 자동으로 고른다:
  "instagram": {"slides": [{"key": "surgeon", "text": "...[강조]...", "grade": "bw", "exposure": 0.6}], "caption": [...]}
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from engine import config, paths
from engine.fonts import font
from engine.photo import PHOTOS, credits, grade

W, H = 1080, 1350
YELLOW = (255, 214, 64)
WHITE = (238, 238, 238)
RED = (214, 32, 32)


def _photo(key, g="cold", exposure=0.75, focus=(0.5, 0.45)):
    src = Image.open(PHOTOS / f"{key}.jpg").convert("RGB")
    src = grade(src, g, exposure)
    sc = max(W / src.width, H / src.height)
    im = src.resize((int(src.width * sc) + 1, int(src.height * sc) + 1), Image.LANCZOS)
    x = int(np.clip(focus[0] * im.width - W / 2, 0, im.width - W))
    y = int(np.clip(focus[1] * im.height - H / 2, 0, im.height - H))
    im = im.crop((x, y, x + W, y + H))
    # 아래쪽 글자 자리 어둡게 + 비네트
    a = np.asarray(im, np.float32)
    yy = np.linspace(0, 1, H)[:, None, None]
    xx = np.linspace(-1, 1, W)[None, :, None]
    shade = 1 - 0.78 * np.clip((yy - 0.45) / 0.45, 0, 1) ** 1.3
    vig = 1 - 0.35 * (xx ** 2) - 0.25 * ((yy * 2 - 1) ** 2)
    a = a * shade * vig
    noise = np.random.default_rng(len(key)).normal(0, 7, (H, W, 1))
    return Image.fromarray(np.clip(a + noise, 0, 255).astype(np.uint8))


def _wrap(text, f, maxw, draw):
    """[강조] 표시를 살려 줄바꿈. 반환: [[(단어, 강조여부), ...], ...]"""
    lines, cur, cw = [], [], 0
    hl = False
    out_words = []
    for w in text.replace("|", " | ").split():   # 괄호가 여러 단어에 걸칠 수 있다
        if w.startswith("["):
            hl = True
        clean = w.replace("[", "").replace("]", "")
        out_words.append((clean, hl))
        if w.endswith("]") or "]" in w:
            hl = False
    for w, h in out_words:
        if w == "|":
            lines.append(cur); cur, cw = [], 0
            continue
        ww = draw.textlength(w + " ", font=f)
        if cur and cw + ww > maxw:
            lines.append(cur); cur, cw = [], 0
        cur.append((w, h)); cw += ww
    if cur:
        lines.append(cur)
    return lines


def _text(img, text, y, size=64, kind="title", center=True, maxw=940):
    d = ImageDraw.Draw(img)
    f = font(kind, size)
    for row in _wrap(text, f, maxw, d):
        rw = sum(d.textlength(w + " ", font=f) for w, _ in row)
        x = (W - rw) / 2 if center else 70
        for w, h in row:
            d.text((x, y), w, font=f, fill=YELLOW if h else WHITE, stroke_width=4, stroke_fill=(0, 0, 0))
            x += d.textlength(w + " ", font=f)
        y += int(size * 1.32)
    return y


def _header(img, num_label):
    d = ImageDraw.Draw(img)
    f = font("mono", 30)
    d.text((60, 56), f"{config.CHANNEL_NAME.upper()}  ·  {num_label}", font=f, fill=(225, 225, 225))
    d.rectangle((60, 100, 160, 104), fill=RED)


def _clean(s):
    return re.sub(r"[\[\]|]", "", s)


def auto_slides(spec):
    beats = [b for b in spec["beats"] if b["scene"] == "photo" and b.get("lines")]
    pick = [beats[0]] + [b for b in beats[1:] if b.get("impact")]
    for b in beats:   # 4~6장 채우기
        if len(pick) >= 5:
            break
        if b not in pick:
            pick.append(b)
    pick.sort(key=beats.index)
    out = []
    for b in pick[:5]:
        p = b["params"]
        out.append(dict(key=p["key"], text=" ".join(b["lines"]), grade=p.get("grade", "cold"),
                        exposure=p.get("exposure", 0.75)))
    return out


def main(path):
    spec = json.loads(Path(path).read_text())
    ig = spec.get("instagram", {})
    out = paths.out_dir(spec) / "instagram"
    out.mkdir(parents=True, exist_ok=True)
    label = spec.get("title", ["", ""])[0].split("·")[-1].strip() if spec.get("title") else spec["id"]
    num = re.search(r"#\d+", spec.get("title", [""])[0] or "")
    num = num.group(0) if num else "FILE"
    slides = ig.get("slides") or auto_slides(spec)

    # 1) 표지
    s0 = slides[0]
    img = _photo(s0["key"], s0.get("grade", "cold"), s0.get("exposure", 0.75), s0.get("focus", (0.5, 0.45)))
    _header(img, num)
    big = spec.get("title", ["", label])[1] if spec.get("title") else label
    y = _text(img, big, 860, size=96)
    _text(img, label, y + 10, size=44, kind="gothic")
    img.save(out / "slide_01.jpg", quality=92)
    # 2) 본문
    for i, s in enumerate(slides[1:], 2):
        img = _photo(s["key"], s.get("grade", "cold"), s.get("exposure", 0.75), s.get("focus", (0.5, 0.45)))
        _header(img, f"{num}  {i:02d}/{len(slides) + 1:02d}")
        _text(img, s["text"], 900 if len(_clean(s["text"])) < 40 else 840, size=62)
        img.save(out / f"slide_{i:02d}.jpg", quality=92)
    # 3) 마지막: 유튜브로
    img = Image.new("RGB", (W, H), (8, 8, 10))
    d = ImageDraw.Draw(img)
    f = font("logo", 230)
    tw = d.textlength("404", font=f)
    d.text(((W - tw) / 2, 330), "404", font=f, fill=RED)
    f2 = font("mono", 40)
    t2 = "FILE NOT FOUND"
    d.text(((W - d.textlength(t2, font=f2)) / 2, 600), t2, font=f2, fill=(200, 200, 200))
    _text(img, "남은 기록은|유튜브 [File404] 에서", 760, size=64)
    nxt = ig.get("next") or next((b["params"].get("next") for b in spec["beats"] if b["params"].get("next")), "")
    if nxt:
        _text(img, nxt, 1060, size=40, kind="gothic")
    img.save(out / f"slide_{len(slides) + 1:02d}.jpg", quality=92)

    # 캡션
    up = spec.get("upload", {})
    cap = ig.get("caption") or [up.get("titles", [""])[0].split("#")[0].strip(), ""] + up.get("description", [])[:2]
    tags = ["#" + t.replace(" ", "") for t in up.get("tags", [])[:12]]
    tags += ["#미스터리", "#미스테리", "#공포", "#실화", "#소름", "#릴스", "#File404"]
    seen, tg = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t); tg.append(t)
    used = []
    for s in slides + [dict(key=b["params"].get("key")) for b in spec["beats"]]:
        k = s.get("key")
        if k and k not in used:
            used.append(k)
    cred = []
    for k in used:
        c = credits().get(k)
        if c and c["license"].startswith("CC BY"):
            cred.append(f"{c['author'][:40]} / {c['license']}")
    txt = "\n".join(cap) + "\n\n▶ 전체 영상은 프로필 링크 · 유튜브 File404\n\n" + " ".join(tg[:25])
    if cred:
        txt += "\n\n사진: " + " · ".join(cred) + " (Wikimedia Commons, 색 보정)"
    (out / "캡션.txt").write_text(txt + "\n")
    print("완료:", out, len(slides) + 1, "장")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
