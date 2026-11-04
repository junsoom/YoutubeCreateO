"""롱폼 썸네일 (1280×720): 영상의 한 장면 + 아래 굵은 2줄(흰/빨강) + 빨간 화살표.

./.venv/bin/python make_thumbnail.py episodes/005_mothman_long.json 291.5 "다리가 무너지기 13개월 전" "붉은 눈이 나타났다" --arrow 0.80 0.30
→ output/<id>/썸네일_<초>.jpg
화살표는 화면 비율 좌표(x, y)를 가리킨다. 렌더 후 timeline.json 이 있어야 한다.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from engine import render
from engine.fonts import font

TW, TH = 1280, 720


def arrow(d, tip, tail, w=22, color=(230, 28, 28)):
    (x1, y1), (x0, y0) = tip, tail
    ang = math.atan2(y1 - y0, x1 - x0)
    head = 70
    bx, by = x1 - head * math.cos(ang), y1 - head * math.sin(ang)
    for c, ww in (((0, 0, 0), w + 10), (color, w)):
        d.line((x0, y0, bx, by), fill=c, width=ww)
        p = [(x1, y1),
             (bx + (head * 0.6) * math.cos(ang + math.pi / 2), by + (head * 0.6) * math.sin(ang + math.pi / 2)),
             (bx + (head * 0.6) * math.cos(ang - math.pi / 2), by + (head * 0.6) * math.sin(ang - math.pi / 2))]
        d.polygon(p, fill=c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("t", type=float)
    ap.add_argument("line1")
    ap.add_argument("line2")
    ap.add_argument("--arrow", nargs=2, type=float)
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    out = Path("output") / spec["id"]
    tl = json.loads((out / "timeline.json").read_text())
    comp = render.Composer(tl, spec)
    fps = spec.get("fps", 30)
    comp.cards = []   # 자막 끄기
    img = comp.frame(a.t, int(a.t * fps)).convert("RGB").resize((TW, TH), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    # 아래 어둡게
    shade = Image.new("L", (TW, TH), 0)
    sd = ImageDraw.Draw(shade)
    for y in range(TH // 2, TH):
        sd.line((0, y, TW, y), fill=int(200 * (y - TH / 2) / (TH / 2)))
    img = Image.composite(Image.new("RGB", (TW, TH)), img, shade)
    d = ImageDraw.Draw(img)
    for i, (txt, col) in enumerate(((a.line1, (255, 255, 255)), (a.line2, (235, 30, 30)))):
        size = 92
        f = font("title", size)
        while d.textlength(txt, font=f) > TW * 0.92:
            size -= 4
            f = font("title", size)
        w = d.textlength(txt, font=f)
        y = TH - 250 + i * 118
        d.text(((TW - w) / 2, y), txt, font=f, fill=col, stroke_width=8, stroke_fill=(0, 0, 0))
    if a.arrow:
        tx, ty = a.arrow[0] * TW, a.arrow[1] * TH
        arrow(d, (tx - 30, ty + 30), (tx - 260, ty + 200))
    p = out / f"썸네일_{a.t}.jpg"
    img.save(p, quality=92)
    print(p)


if __name__ == "__main__":
    main()
