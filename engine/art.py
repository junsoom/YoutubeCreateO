"""절차적 그림: 하늘, 달, 숲, 도로, 자동차, 벙커, 신문. 괴물 실루엣은 creatures.py."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import fx
from .fonts import font


def gradient(w, h, stops):
    """stops: [(위치 0~1, (r,g,b)), ...] 세로 그라데이션."""
    y = np.linspace(0, 1, h)
    pos = [s[0] for s in stops]
    cols = np.array([s[1] for s in stops], np.float32)
    out = np.stack([np.interp(y, pos, cols[:, c]) for c in range(3)], -1)
    return np.repeat(out[:, None, :], w, 1)


def sky(w, h, stops, seed=0, stars=300, moon=None, clouds=0.5, cloud_color=(40, 48, 66)):
    """밤하늘 RGB. moon=(x, y, r) 이면 달과 달무리를 그린다."""
    rng = np.random.default_rng(seed)
    a = gradient(w, h, stops)
    # 별
    for _ in range(stars):
        x, y = rng.integers(0, w), rng.integers(0, int(h * 0.7))
        b = rng.uniform(60, 200) * (1 - y / (h * 0.7))
        a[y, x] = np.maximum(a[y, x], b)
    if moon:
        mx, my, mr = moon
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt((xx - mx) ** 2 + (yy - my) ** 2)
        halo = np.exp(-np.maximum(0, d - mr) / (mr * 2.2))[..., None]
        a += halo * np.array([60, 70, 90], np.float32) * 0.9
        disk = np.clip((mr - d) / 2, 0, 1)[..., None]
        tex = fx.value_noise(w, h, mr * 0.6, 3, seed + 9, wrap=False)[..., None]
        moon_col = np.array([225, 225, 210], np.float32) * (0.85 + 0.2 * tex)
        a = a * (1 - disk) + moon_col * disk
    if clouds > 0:
        n = fx.value_noise(w, h, w * 0.35, 5, seed + 1)
        n = np.clip((n - 0.45) * 2.6, 0, 1) * clouds
        yfac = np.clip(1 - np.linspace(0, 1, h) * 0.6, 0, 1)[:, None]
        n = (n * yfac)[..., None]
        a = a * (1 - n) + np.array(cloud_color, np.float32) * n
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _branch(draw, x, y, length, ang, width, depth, rng, color, droop=0.0):
    if depth == 0 or length < 2:
        return
    x2 = x + math.cos(ang) * length
    y2 = y - math.sin(ang) * length
    draw.line([(x, y), (x2, y2)], fill=color, width=max(1, int(width)))
    if width > 3:
        draw.ellipse([x2 - width / 2, y2 - width / 2, x2 + width / 2, y2 + width / 2], fill=color)
    n = 2 if rng.random() < 0.75 else 3
    for k in range(n):
        da = rng.uniform(0.25, 0.65) * (1 if k % 2 == 0 else -1) + rng.uniform(-0.15, 0.15)
        _branch(draw, x2, y2, length * rng.uniform(0.62, 0.80), ang + da - droop, width * 0.66,
                depth - 1, rng, color, droop)


def bare_tree(draw, x, y, height, color, rng, depth=8):
    trunk = height * 0.32
    _branch(draw, x, y, trunk, math.pi / 2 + rng.uniform(-0.08, 0.08), height * 0.035, depth, rng, color)


def pine_tree(draw, x, y, height, color, rng):
    w = height * 0.32
    layers = 7
    for i in range(layers):
        top = y - height * (0.25 + 0.75 * (i + 1) / layers)
        bot = y - height * (0.12 + 0.75 * i / layers)
        ww = w * (1 - i / layers) + 4
        jag = [(x - ww, bot), (x - ww * 0.3, bot - (bot - top) * 0.15), (x, top), (x + ww * 0.3, bot - (bot - top) * 0.15), (x + ww, bot)]
        draw.polygon(jag, fill=color)
    draw.rectangle([x - height * 0.02, y - height * 0.15, x + height * 0.02, y], fill=color)


def forest(w, h, ground_y, color, seed=0, count=14, hmin=0.3, hmax=0.6, kind="mix", ground=True, ss=2):
    """나무 실루엣 줄 (RGBA). ground_y 는 0~1 비율."""
    rng = np.random.default_rng(seed)
    W, H = w * ss, h * ss
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = tuple(color) + (255,)
    gy = ground_y * H
    xs = np.sort(rng.uniform(-0.05, 1.05, count)) * W
    for x in xs:
        th = rng.uniform(hmin, hmax) * H
        base = gy + rng.uniform(-0.01, 0.02) * H
        if kind == "pine" or (kind == "mix" and rng.random() < 0.35):
            pine_tree(d, x, base, th, col, rng)
        else:
            bare_tree(d, x, base, th, col, rng)
    if ground:
        pts = [(0, H)]
        for i in range(41):
            pts.append((i / 40 * W, gy + math.sin(i * 0.7 + seed) * H * 0.006 + rng.uniform(0, H * 0.008)))
        pts.append((W, H))
        d.polygon(pts, fill=col)
    return img.resize((w, h), Image.LANCZOS) if ss != 1 else img


def car_front(width):
    """정면에서 본 1960년대 세단 실루엣 (RGBA) 과 전조등 위치."""
    ss = 3
    W = int(width * ss)
    H = int(W * 0.55)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body = (14, 15, 19, 255)
    # 지붕·유리
    d.polygon([(W * 0.24, H * 0.42), (W * 0.31, H * 0.12), (W * 0.69, H * 0.12), (W * 0.76, H * 0.42)], fill=body)
    d.polygon([(W * 0.29, H * 0.40), (W * 0.34, H * 0.17), (W * 0.66, H * 0.17), (W * 0.71, H * 0.40)], fill=(32, 38, 50, 255))
    # 차체
    d.rounded_rectangle([W * 0.04, H * 0.40, W * 0.96, H * 0.82], radius=H * 0.08, fill=body)
    # 그릴 (크롬)
    d.rectangle([W * 0.30, H * 0.56, W * 0.70, H * 0.66], fill=(70, 74, 82, 255))
    for i in range(9):
        x = W * (0.31 + i * 0.045)
        d.line([(x, H * 0.57), (x, H * 0.65)], fill=(30, 32, 38, 255), width=ss * 2)
    d.rectangle([W * 0.03, H * 0.72, W * 0.97, H * 0.76], fill=(80, 84, 92, 255))  # 범퍼
    # 바퀴
    for x in (0.12, 0.80):
        d.rectangle([W * x, H * 0.80, W * (x + 0.09), H * 0.98], fill=(8, 8, 10, 255))
    img = img.resize((W // ss, H // ss), Image.LANCZOS)
    lights = [(0.17, 0.58), (0.83, 0.58)]
    return img, [(img.width * x, img.height * y) for x, y in lights]


def bunker(width, seed=0):
    """TNT 구역의 흙 덮인 콘크리트 이글루 벙커 (RGBA, 정면 약간 비스듬)."""
    rng = np.random.default_rng(seed)
    ss = 2
    W = int(width * ss)
    H = int(W * 0.55)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 흙 언덕
    d.ellipse([W * 0.02, H * 0.15, W * 0.98, H * 1.75], fill=(24, 30, 28, 255))
    # 풀 결
    for _ in range(300):
        x = rng.uniform(0.05, 0.95) * W
        top = H * (0.17 + 1.2 * ((x / W - 0.5) ** 2))
        y = rng.uniform(top, H)
        d.line([(x, y), (x + rng.uniform(-6, 6), y - rng.uniform(6, 18))], fill=(36, 44, 40, 255), width=2)
    # 콘크리트 정면
    face = [(W * 0.30, H), (W * 0.33, H * 0.38), (W * 0.67, H * 0.38), (W * 0.70, H)]
    d.polygon(face, fill=(78, 82, 84, 255))
    d.polygon([(W * 0.33, H * 0.38), (W * 0.67, H * 0.38), (W * 0.66, H * 0.44), (W * 0.34, H * 0.44)], fill=(96, 100, 102, 255))
    # 철문
    d.rectangle([W * 0.42, H * 0.55, W * 0.58, H], fill=(22, 22, 24, 255))
    d.line([(W * 0.50, H * 0.55), (W * 0.50, H)], fill=(40, 40, 44, 255), width=ss * 2)
    # 얼룩
    tex = fx.value_noise(W, H, 40, 3, seed + 5, wrap=False)
    a = np.asarray(img, np.float32)
    a[..., :3] *= (0.75 + 0.45 * tex)[..., None]
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
    return img.resize((W // ss, H // ss), Image.LANCZOS)


def road_plate(w, h, horizon, seed=0):
    """원근 도로 (RGB 위에 덮을 RGBA). horizon 은 0~1."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hy = horizon * h
    vx = w * 0.5
    d.polygon([(vx - 6, hy), (vx + 6, hy), (w * 1.1, h), (-w * 0.1, h)], fill=(30, 31, 34, 255))
    # 갓길 흙
    d.polygon([(vx - 6, hy), (-w * 0.1, h), (-w * 0.6, h)], fill=(20, 22, 20, 255))
    d.polygon([(vx + 6, hy), (w * 1.1, h), (w * 1.6, h)], fill=(20, 22, 20, 255))
    # 중앙 점선
    for i in range(14):
        z0, z1 = i / 14, (i + 0.5) / 14
        y0, y1 = hy + (h - hy) * z0 ** 2, hy + (h - hy) * z1 ** 2
        ww0, ww1 = 2 + 10 * z0 ** 2, 2 + 10 * z1 ** 2
        d.polygon([(vx - ww0, y0), (vx + ww0, y0), (vx + ww1, y1), (vx - ww1, y1)], fill=(150, 140, 90, 255))
    return img


def light_cone(w, h, apex, spread, length, color=(255, 240, 200), power=1.4):
    """전조등·손전등 빛줄기 (RGB, 더하기 합성용)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xx - apex[0], yy - apex[1]
    dist = np.sqrt(dx ** 2 + dy ** 2) + 1e-3
    ang = np.abs(np.arctan2(dx, -dy + 1e-3))  # 위쪽 기준
    a = np.clip(1 - ang / spread, 0, 1) ** power * np.clip(1 - dist / length, 0, 1) ** 1.5
    out = a[..., None] * np.array(color, np.float32) * 0.5
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def flare(size, color=(255, 235, 200)):
    """렌즈 발광 점 (RGB, 더하기 합성용)."""
    s = int(size)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.sqrt((xx - s / 2) ** 2 + (yy - s / 2) ** 2) / (s / 2)
    core = np.exp(-r * 9) * 1.4 + np.exp(-r * 3) * 0.5
    streak = np.exp(-np.abs(yy - s / 2) / (s * 0.012)) * np.exp(-np.abs(xx - s / 2) / (s * 0.35)) * 0.6
    a = np.clip(core + streak, 0, 1.5)[..., None] * np.array(color, np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def paper(w, h, seed=0):
    """누렇게 바랜 신문지 바탕."""
    n = fx.value_noise(w, h, 90, 5, seed, wrap=False)
    n2 = fx.value_noise(w, h, 18, 2, seed + 1, wrap=False)
    base = np.array([214, 198, 160], np.float32)
    a = base * (0.82 + 0.22 * n[..., None]) * (0.95 + 0.08 * n2[..., None])
    # 가장자리 탄 자국
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    e = np.minimum(np.minimum(x, w - x), np.minimum(y, h - y)) / (min(w, h) * 0.12)
    a *= (0.55 + 0.45 * np.clip(e, 0, 1) ** 0.6)[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def newspaper(w, h, masthead, dateline, headline, sub, seed=0, figure=None):
    """신문 1면 재현 (RGB). 본문은 읽을 수 없는 회색 줄로 처리한다."""
    rng = np.random.default_rng(seed)
    img = paper(w, h, seed)
    d = ImageDraw.Draw(img)
    ink = (34, 30, 26)
    m = int(w * 0.06)
    f = font("serif", w * 0.085)
    tw = d.textlength(masthead, font=f)
    d.text(((w - tw) / 2, h * 0.04), masthead, font=f, fill=ink)
    d.line([(m, h * 0.115), (w - m, h * 0.115)], fill=ink, width=4)
    fd = font("type", w * 0.026)
    tw = d.textlength(dateline, font=fd)
    d.text(((w - tw) / 2, h * 0.122), dateline, font=fd, fill=ink)
    d.line([(m, h * 0.148), (w - m, h * 0.148)], fill=ink, width=2)
    # 헤드라인 (여러 줄)
    y = h * 0.165
    for line in headline.split("\n"):
        fh = font("type", w * 0.078)
        tw = d.textlength(line, font=fh)
        sc = min(1.0, (w - 2 * m) / max(tw, 1))
        fh = font("type", w * 0.078 * sc)
        tw = d.textlength(line, font=fh)
        d.text(((w - tw) / 2, y), line, font=fh, fill=ink, stroke_width=1, stroke_fill=ink)
        y += w * 0.09 * sc
    fs = font("type", w * 0.032)
    tw = d.textlength(sub, font=fs)
    d.text(((w - tw) / 2, y + h * 0.005), sub, font=fs, fill=ink)
    y += h * 0.05
    d.line([(m, y), (w - m, y)], fill=ink, width=2)
    # 그림 상자
    top = y + h * 0.02
    colw = (w - 2 * m - 2 * 20) / 3
    if figure is not None:
        fx0, fy0 = m + colw + 20, top
        fw, fh_ = int(colw * 2 + 20), int(h * 0.36)
        d.rectangle([fx0, fy0, fx0 + fw, fy0 + fh_], fill=(60, 56, 50))
        fig = figure.copy()
        fig.thumbnail((fw - 20, fh_ - 20))
        bg = Image.new("RGB", (fw - 8, fh_ - 8), (176, 166, 140))
        bg.paste(fig, ((bg.width - fig.width) // 2, bg.height - fig.height), fig)
        img.paste(bg, (int(fx0 + 4), int(fy0 + 4)))
        cap = "Witness sketch (reconstruction)"
        fc = font("type", w * 0.022)
        d.text((fx0, fy0 + fh_ + 8), cap, font=fc, fill=ink)
    # 본문 줄
    for c in range(3):
        x0 = m + c * (colw + 20)
        yy = top
        while yy < h * 0.95:
            if figure is not None and c > 0 and yy < top + h * 0.40:
                yy += 14
                continue
            ln = colw * (rng.uniform(0.7, 1.0) if rng.random() > 0.12 else rng.uniform(0.2, 0.6))
            d.rectangle([x0, yy, x0 + ln, yy + 5], fill=(110, 100, 86))
            yy += 14 if rng.random() > 0.08 else 26
    return img.filter(ImageFilter.GaussianBlur(0.6))
