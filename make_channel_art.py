"""채널 아트: 배너 + 프로필 사진 → output/channel_art/

./.venv/bin/python make_channel_art.py

유튜브 규격
- 배너 2560x1440. 모든 기기에서 보이는 안전 영역은 가운데 1546x423 → 로고·문구는 이 안에만.
  PC 는 가로 전체 x 423 띠, TV 는 전체가 보인다.
- 프로필 800x800, 원으로 잘려 보인다. 아주 작게(24~98px)도 보이니 단순하게.
그림은 전부 코드로 만든다 (사진 없음 → 출처 표기 필요 없음). 글꼴은 OFL (Anton, Space Mono, 나눔고딕, 검은고딕).
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from engine import config, fx
from engine.creatures import eye_glow
from engine.fonts import font

OUT = Path(__file__).resolve().parent / "output" / "channel_art"
RED = (226, 30, 26)
TAGLINE = "기록에서 지워진 이야기를 다시 엽니다"
TOPICS = ["미스터리", "미확인 생물", "미제 사건", "괴현상"]


def background(W, H, seed=1, doc=True):
    """어두운 기밀 문서 + 안개 + 주사선."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (W, H), (9, 10, 13))
    if doc:
        layer = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(layer)
        f = font("mono", 26)
        y = 30
        words = ["CLASSIFIED", "CASE NO.", "FILE NOT FOUND", "ACCESS DENIED", "UNIDENTIFIED", "REDACTED", "1966", "1967",
                 "WITNESS", "REPORT", "SIGHTING", "STATUS: UNKNOWN", "ERROR 404", "RECORD MISSING"]
        while y < H:
            x = 40 + rng.integers(0, 60)
            while x < W - 100:
                if rng.random() < 0.18:   # 검게 지운 줄 (리댁션)
                    w = rng.integers(120, 420)
                    d.rectangle([x, y + 4, x + w, y + 30], fill=70)
                    x += w + 24
                else:
                    t = rng.choice(words) if rng.random() < 0.25 else "".join(rng.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ")) for _ in range(rng.integers(4, 12)))
                    d.text((x, y), t, font=f, fill=int(rng.integers(26, 46)))
                    x += int(d.textlength(t, font=f)) + 22
            y += 44
        layer = layer.filter(ImageFilter.GaussianBlur(0.7))
        a = np.asarray(img, np.float32) + np.asarray(layer, np.float32)[..., None] * np.array([0.55, 0.62, 0.66])
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    fog = fx.fog(W, H, (46, 58, 66), 0.55, max(W, H) * 0.25, seed + 3, 0.0, 1.0, contrast=1.4)
    img.paste(fog, (0, 0), fog)
    a = np.asarray(img, np.float32)
    a[::4] *= 0.86   # 주사선
    a *= fx.vignette(W, H, 0.75, 2.0)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def red_glow(img, cx, cy, rx, ry, gain=1.0):
    W, H = img.size
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    g = np.exp(-r * 1.6)[..., None] * np.array([120, 10, 8]) * gain
    a = np.asarray(img, np.float32) + g
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def glitch_text(img, xy, text, f, color=RED, split=10, slices=5, seed=0):
    """빨간 글자 + RGB 어긋남 + 가로 띠 밀림."""
    W, H = img.size
    layer = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = xy
    d.text((x - split, y), text, font=f, fill=(110, 0, 0))
    d.text((x + split, y), text, font=f, fill=(0, 46, 74))
    d.text((x, y), text, font=f, fill=color)
    bbox = d.textbbox((x, y), text, font=f)
    a = np.asarray(layer).copy()
    rng = np.random.default_rng(seed)
    for _ in range(slices):
        y0 = int(rng.integers(int(bbox[1]), int(bbox[3]) - 10))
        h = int(rng.integers(6, max(8, int(bbox[3] - bbox[1]) // 7)))
        a[y0:y0 + h] = np.roll(a[y0:y0 + h], int(rng.integers(-28, 28)), axis=1)
    layer = Image.fromarray(a)
    fx.add(img, layer.filter(ImageFilter.GaussianBlur(14)), 0.55)
    fx.add(img, layer, 1.0)
    return bbox


def banner():
    W, H = 2560, 1440
    sx0, sy0, sw, sh = (W - 1546) // 2, (H - 423) // 2, 1546, 423
    img = background(W, H, seed=4)
    img = red_glow(img, sx0 + 360, H / 2, 520, 260, 0.9)
    # PC 에서만 보이는 오른쪽 끝: 어둠 속 붉은 눈
    e = eye_glow(9)
    for dx in (-26, 26):
        fx.add(img, e, 0.75, (W - 250 + dx - e.width / 2, H / 2 - 40 - e.height / 2))
    d = ImageDraw.Draw(img)
    # 로고
    fl = font("logo", 228)
    x, y = sx0 + 60, sy0 + 78
    d.text((x, y), "File", font=fl, fill=(236, 236, 232))
    fw = d.textlength("File", font=fl)
    bb = glitch_text(img, (x + fw + 14, y), "404", fl, seed=3)
    d = ImageDraw.Draw(img)
    # 로고 위 작은 오류 문구
    fm = font("mono", 30)
    d.text((x + 6, sy0 + 34), "ERROR 404 — FILE NOT FOUND", font=fm, fill=(200, 40, 34))
    cw = d.textlength("ERROR 404 — FILE NOT FOUND", font=fm)
    d.rectangle([x + 18 + cw, sy0 + 40, x + 34 + cw, sy0 + 68], fill=(200, 40, 34))   # 커서
    # 세로 구분선
    lx = bb[2] + 52
    d.rectangle([lx, sy0 + 92, lx + 5, sy0 + sh - 80], fill=RED)
    # 오른쪽: 한국어 문구
    tx = lx + 44
    ft = font("title", 58)
    lines = ["기록에서 지워진", "이야기를 다시 엽니다"]
    ty = sy0 + 104
    for ln in lines:
        d.text((tx, ty), ln, font=ft, fill=(240, 240, 236))
        ty += 76
    fs = font("gothic", 31)
    ty += 22
    xx = tx
    for k, tpc in enumerate(TOPICS):
        if k:
            d.ellipse([xx + 8, ty + 16, xx + 18, ty + 26], fill=RED)
            xx += 32
        d.text((xx, ty), tpc, font=fs, fill=(170, 176, 180))
        xx += d.textlength(tpc, font=fs) + 8
    right = max(xx, tx + d.textlength(lines[1], font=ft))
    return img, (sx0, sy0, sw, sh), right


def guide(img, safe):
    """기기별로 보이는 영역 표시 (확인용)."""
    g = img.copy()
    d = ImageDraw.Draw(g)
    W, H = g.size
    sx0, sy0, sw, sh = safe
    d.rectangle([0, sy0, W - 1, sy0 + sh], outline=(80, 200, 255), width=4)
    d.text((20, sy0 - 50), "PC 에서 보이는 띠 (2560x423)", font=font("gothic", 36), fill=(80, 200, 255))
    d.rectangle([sx0, sy0, sx0 + sw, sy0 + sh], outline=(255, 220, 0), width=6)
    d.text((sx0, sy0 + sh + 12), "모든 기기 안전 영역 (1546x423)", font=font("gothic", 36), fill=(255, 220, 0))
    d.text((20, 20), "TV 에서는 전체 (2560x1440)", font=font("gothic", 36), fill=(200, 200, 200))
    return g


def profile_a():
    """404 글리치 마크."""
    S = 800
    img = background(S, S, seed=7, doc=False)
    img = red_glow(img, S / 2, S * 0.56, 300, 220, 0.8)
    d = ImageDraw.Draw(img)
    ff = font("logo", 128)
    tw = d.textlength("FILE", font=ff)
    d.text(((S - tw) / 2, 150), "FILE", font=ff, fill=(236, 236, 232))
    f4 = font("logo", 300)
    tw = d.textlength("404", font=f4)
    glitch_text(img, ((S - tw) / 2, 268), "404", f4, split=12, slices=6, seed=5)
    return circle_check(img)


def profile_b():
    """어둠 속 붉은 눈 + 404."""
    S = 800
    img = background(S, S, seed=9, doc=False)
    e = eye_glow(30)
    for dx in (-88, 88):
        fx.add(img, e, 1.0, (S / 2 + dx - e.width / 2, S * 0.40 - e.height / 2))
    d = ImageDraw.Draw(img)
    f4 = font("logo", 170)
    tw = d.textlength("404", font=f4)
    glitch_text(img, ((S - tw) / 2, S * 0.53), "404", f4, split=7, slices=4, seed=8)
    return circle_check(img)


def circle_check(img):
    return img


def circle_preview(img, size=200):
    """원형으로 잘렸을 때 모습 (확인용)."""
    S = img.width
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse([0, 0, S, S], fill=255)
    out = Image.new("RGB", (S, S), (255, 255, 255))
    out.paste(img, (0, 0), m)
    return out.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, safe, right = banner()
    print("배너 오른쪽 끝 글자 x =", int(right), "/ 안전 영역 끝 x =", safe[0] + safe[2])
    b.save(OUT / "banner_2560x1440.png", optimize=True)
    b.convert("RGB").save(OUT / "banner_2560x1440.jpg", quality=92)
    guide(b, safe).resize((1280, 720), Image.LANCZOS).save(OUT / "banner_영역확인.jpg", quality=88)
    for name, fn in (("A_404", profile_a), ("B_붉은눈", profile_b)):
        p = fn()
        p.save(OUT / f"profile_{name}_800.png", optimize=True)
        circle_preview(p).save(OUT / f"profile_{name}_원형미리보기.png")
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
