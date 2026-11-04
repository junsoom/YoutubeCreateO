"""장면. 각 장면은 frame(u) 로 u 초 시점의 화면(RGB, W×H)을 돌려준다.

무거운 준비(배경 그리기, 스프라이트)는 setup() 에서 한 번만, 처음 frame() 을 부를 때 한다.
ev: 대사의 특정 단어가 나오는 시각 (장면 시작 기준 초). 스펙의 "events" 로 정한다.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import art, creatures, fx
from .fonts import font


class Scene:
    def __init__(self, W, H, dur, ev=None, seed=0, **p):
        self.W, self.H, self.dur, self.ev, self.seed, self.p = W, H, dur, ev or {}, seed, p
        self._ready = False

    def frame(self, u):
        if not self._ready:
            self.setup()
            self._ready = True
        return self.draw(u)

    def e(self, name, default):
        return self.ev.get(name, default)

    def setup(self):
        pass

    def draw(self, u):
        raise NotImplementedError

    def shake(self, u, amp):
        return (amp * (math.sin(u * 37.1) + 0.5 * math.sin(u * 91.7)),
                amp * (math.cos(u * 41.3) + 0.5 * math.sin(u * 73.9)))


# ── 1. 밤길 추격 ─────────────────────────────────────────

class RoadChase(Scene):
    def setup(self):
        W, H = self.W, self.H
        PW, PH = int(W * 1.2), int(H * 1.2)
        self.PW, self.PH = PW, PH
        hz = 0.47
        plate = art.sky(PW, PH, [(0, (8, 12, 22)), (0.42, (30, 40, 58)), (0.5, (44, 52, 68)), (1, (12, 14, 18))],
                        seed=self.seed, moon=(PW * 0.52, PH * 0.29, PW * 0.075), clouds=0.55, cloud_color=(62, 70, 90))
        far = art.forest(PW, PH, hz + 0.01, (20, 25, 33), seed=self.seed + 1, count=45, hmin=0.05, hmax=0.12, ss=1)
        plate.paste(far, (0, 0), far)
        f1 = fx.fog(PW, PH, (60, 70, 86), 0.55, 300, self.seed + 2, hz - 0.08, hz + 0.06)
        plate.paste(f1, (0, 0), f1)
        road = art.road_plate(PW, PH, hz + 0.005)
        plate.paste(road, (0, 0), road)
        near = art.forest(PW, PH, hz + 0.16, (6, 7, 10), seed=self.seed + 3, count=12, hmin=0.45, hmax=0.75, ss=1, ground=False)
        a = np.asarray(near, np.float32).copy()
        x = np.linspace(0, 1, PW)
        side = np.clip((np.abs(x - 0.5) - 0.24) / 0.06, 0, 1)
        a[..., 3] *= side[None, :]
        near = Image.fromarray(a.astype(np.uint8), "RGBA")
        plate.paste(near, (0, 0), near)
        self.plate = plate
        self.car, self.lights = art.car_front(W * 0.5)
        self.flare = art.flare(W * 0.55)
        cone = art.light_cone(W, int(H * 0.9), (W / 2, int(H * 0.9)), 0.95, H * 0.9, (255, 235, 190))
        self.cone = cone.transpose(Image.FLIP_TOP_BOTTOM)   # 아래(화면 앞쪽)로 비추는 빛
        self.fog = fx.fog(W, H, (90, 100, 115), 0.35, 260, self.seed + 4, 0.35, 0.75)
        # 날아오는 모스맨 (날갯짓 8프레임)
        self.flaps = []
        for k in range(8):
            fl = math.sin(k / 8 * 2 * math.pi)
            spr, eyes, r = creatures.mothman(H * 0.16, 1.0, fl, "fly", ss=2)
            self.flaps.append((spr, eyes, r))
        self.eye = creatures.eye_glow(self.flaps[0][2] * 1.1)

    def draw(self, u):
        W, H = self.W, self.H
        p = u / self.dur
        sx, sy = self.shake(u, 6)
        img = fx.view(self.plate, self.PW / 2 + sx, self.PH * 0.5 + sy, 1.0 + 0.08 * p, W, H)
        # 괴물: 차 뒤 하늘에서 점점 다가온다
        k = int(u / 0.11) % 8
        spr, eyes, r = self.flaps[k]
        cx = W * (0.5 + 0.06 * math.sin(u * 0.9))
        cy = H * (0.25 + 0.02 * math.sin(u * 2.1)) - 0.06 * H * (1 - p)
        a = fx.ease(u / 1.4)
        ox, oy = cx - spr.width / 2, cy - spr.height * 0.25
        fx.paste(img, spr, (ox, oy), 0.92 * a)
        for ex, ey in eyes:
            fx.add(img, self.eye, a * (0.85 + 0.15 * math.sin(u * 13)), (ox + ex - self.eye.width / 2, oy + ey - self.eye.height / 2))
        # 안개
        f = fx.scroll(self.fog, u * 40)
        img.paste(f, (0, 0), f)
        # 차: 화면 쪽으로 다가온다
        s = 0.80 + 0.35 * p
        car = self.car.resize((int(self.car.width * s), int(self.car.height * s)), Image.BILINEAR)
        bx = W / 2 - car.width / 2 + sx * 0.5
        by = H * (0.585 + 0.05 * p) - car.height + sy * 0.5
        fx.add(img, self.cone, 0.9, (0, by + car.height * 0.55))
        fx.paste(img, car, (bx, by))
        flick = 0.92 + 0.08 * math.sin(u * 50)
        for lx, ly in self.lights:
            fx.add(img, self.flare, flick, (bx + lx * s - self.flare.width / 2, by + ly * s - self.flare.height / 2))
        return img


# ── 2. TNT 구역 (위치 소개) ─────────────────────────────

class TNTArea(Scene):
    def setup(self):
        W, H = self.W, self.H
        PW, PH = int(W * 1.25), int(H * 1.2)
        self.PW, self.PH = PW, PH
        gy = 0.60
        plate = art.sky(PW, PH, [(0, (8, 11, 20)), (0.5, (34, 42, 58)), (0.6, (50, 56, 70)), (1, (12, 14, 16))],
                        seed=self.seed, moon=(PW * 0.22, PH * 0.17, PW * 0.05), clouds=0.6)
        far = art.forest(PW, PH, gy, (24, 30, 38), seed=self.seed + 1, count=30, hmin=0.10, hmax=0.20, kind="bare", ss=1)
        plate.paste(far, (0, 0), far)
        g = Image.fromarray(art.gradient(PW, PH, [(0, (14, 18, 18)), (gy, (16, 20, 20)), (1, (6, 7, 8))]).astype(np.uint8))
        mask = Image.new("L", (PW, PH), 0)
        ImageDraw.Draw(mask).rectangle([0, gy * PH, PW, PH], fill=255)
        plate.paste(g, (0, 0), mask)
        f0 = fx.fog(PW, PH, (70, 80, 95), 0.6, 320, self.seed + 2, gy - 0.10, gy + 0.05)
        plate.paste(f0, (0, 0), f0)
        for (x, y, w, dim) in ((0.86, 0.615, 0.26, 0.55), (0.55, 0.63, 0.36, 0.35), (0.18, 0.66, 0.55, 0.0)):
            b = art.bunker(W * w, seed=int(x * 100))
            if dim:
                a = np.asarray(b, np.float32).copy()
                a[..., :3] = a[..., :3] * (1 - dim) + np.array([60, 68, 82]) * dim
                b = Image.fromarray(a.astype(np.uint8), "RGBA")
            plate.paste(b, (int(PW * x - b.width / 2), int(PH * y - b.height * 0.95)), b)
            fz = fx.fog(PW, PH, (70, 80, 95), 0.35, 260, self.seed + int(x * 10), y - 0.05, y + 0.03)
            plate.paste(fz, (0, 0), fz)
        self.plate = plate
        self.fogs = [fx.fog(W, H, (80, 90, 105), 0.40, 300, self.seed + 7, 0.50, 0.85),
                     fx.fog(W, H, (100, 110, 125), 0.25, 500, self.seed + 8, 0.40, 1.0)]

    def draw(self, u):
        p = u / self.dur
        img = fx.view(self.plate, self.PW * (0.45 + 0.08 * fx.ease(p)), self.PH * 0.52, 1.0 + 0.12 * p, self.W, self.H)
        for i, f in enumerate(self.fogs):
            f = fx.scroll(f, u * (25 + 30 * i))
            img.paste(f, (0, 0), f)
        return img


# ── 3. 정체 드러남 (날개 펴기, 붉은 눈) ──────────────────

class Reveal(Scene):
    LEVELS = 14

    def setup(self):
        W, H = self.W, self.H
        PW, PH = int(W * 1.15), int(H * 1.15)
        self.PW, self.PH = PW, PH
        gy = 0.74
        plate = art.sky(PW, PH, [(0, (2, 3, 6)), (0.5, (12, 15, 22)), (gy, (22, 26, 32)), (1, (8, 9, 10))],
                        seed=self.seed, stars=60, clouds=0.4)
        b = art.bunker(W * 0.9, seed=3)
        a = np.asarray(b, np.float32).copy()
        a[..., :3] = a[..., :3] * 0.5 + np.array([40, 46, 56]) * 0.5
        b = Image.fromarray(a.astype(np.uint8), "RGBA")
        plate.paste(b, (int(PW * 0.62 - b.width / 2), int(PH * gy - b.height * 0.9)), b)
        trees = art.forest(PW, PH, gy - 0.02, (16, 19, 25), seed=self.seed + 1, count=10, hmin=0.25, hmax=0.4, kind="bare", ground=False, ss=1)
        plate.paste(trees, (0, 0), trees)
        f0 = fx.fog(PW, PH, (60, 68, 80), 0.75, 300, self.seed + 2, 0.45, 0.85)
        plate.paste(f0, (0, 0), f0)
        g = Image.fromarray(art.gradient(PW, PH, [(0, (16, 18, 18)), (1, (5, 5, 6))]).astype(np.uint8))
        m = Image.new("L", (PW, PH), 0)
        ImageDraw.Draw(m).rectangle([0, gy * PH, PW, PH], fill=255)
        plate.paste(g, (0, 0), m.filter(ImageFilter.GaussianBlur(6)))
        self.plate = plate
        self.gy = gy
        hh = H * 0.36
        self.sprites = [creatures.mothman(hh, k / (self.LEVELS - 1), 0, "stand", ss=2) for k in range(self.LEVELS)]
        self.eye = creatures.eye_glow(self.sprites[0][2] * 1.15)
        # 아래쪽에서 비추는 전조등 빛 (안개에 퍼지는 빛줄기)
        self.beam = art.light_cone(W, H, (W * 0.5, H * 1.05), 0.55, H * 0.95, (200, 205, 220), power=1.2)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.55)) ** 2 + ((yy - H * 0.42) / (H * 0.30)) ** 2)
        self.back = Image.fromarray(np.clip(np.exp(-r ** 2 * 1.6)[..., None] * np.array([80, 95, 120]), 0, 255).astype(np.uint8))
        self.fogs = [fx.fog(W, H, (110, 120, 135), 0.35, 280, self.seed + 5, 0.55, 0.95),
                     fx.fog(W, H, (90, 100, 115), 0.20, 450, self.seed + 6, 0.30, 0.80)]

    def draw(self, u):
        W, H = self.W, self.H
        p = u / self.dur
        t_w = self.e("wings", self.dur * 0.35)
        t_e = self.e("eyes", self.dur * 0.65)
        zoom = 1.0 + 0.10 * p + 0.10 * fx.ease((u - t_e) / 2.5)
        img = fx.view(self.plate, self.PW / 2, self.PH * (0.52 - 0.04 * fx.ease((u - t_e) / 2.5)), zoom, W, H)
        fx.add(img, self.beam, 0.55 + 0.05 * math.sin(u * 3))
        fx.add(img, self.back, 0.9 + 0.1 * math.sin(u * 1.7))
        spread = 0.12 + 0.88 * fx.ease((u - t_w) / 1.6)
        x = spread * (self.LEVELS - 1)
        i0 = int(x)
        i1 = min(self.LEVELS - 1, i0 + 1)
        fr = x - i0
        sc = zoom
        spr, eyes, r = self.sprites[i0]
        cx, foot = W / 2, H * (0.70 + 0.10 * (zoom - 1))
        def place(s):
            if sc != 1:
                s = s.resize((int(s.width * sc), int(s.height * sc)), Image.BILINEAR)
            return s, (cx - s.width / 2, foot - s.height * (1.22 / 1.30))
        s0, at = place(spr)
        fx.paste(img, s0, at, 1.0 if fr < 0.5 else 1.0)
        if fr > 0.05 and i1 != i0:
            s1, at1 = place(self.sprites[i1][0])
            fx.paste(img, s1, at1, fr)
        # 안개를 몸 앞에도 살짝
        for i, f in enumerate(self.fogs):
            f = fx.scroll(f, u * (20 + 25 * i))
            img.paste(f, (0, 0), f)
        # 눈: 처음엔 희미하게, 이벤트에서 확 켜진다
        glow = 0.08 + 0.92 * fx.ease((u - t_e) / 0.35)
        glow *= 0.9 + 0.1 * math.sin(u * 11)
        for ex, ey in eyes:
            gx = at[0] + ex * sc
            gy_ = at[1] + ey * sc
            e = self.eye if sc == 1 else self.eye.resize((int(self.eye.width * sc), int(self.eye.height * sc)), Image.BILINEAR)
            fx.add(img, e, glow, (gx - e.width / 2, gy_ - e.height / 2))
        # 치수 표시
        d = ImageDraw.Draw(img)
        a1 = fx.ease((u - 0.4) / 0.5) * (1 - fx.ease((u - t_e + 0.3) / 0.4))
        if a1 > 0.02:
            top = at[1] + 0.22 / 1.30 * s0.height
            x0 = cx - 0.36 * W
            col = (int(230 * a1), int(230 * a1), int(230 * a1))
            d.line([(x0, top), (x0, foot)], fill=col, width=3)
            for yy in (top, foot):
                d.line([(x0 - 14, yy), (x0 + 14, yy)], fill=col, width=3)
            d.text((x0 + 22, (top + foot) / 2 - 30), "약 2m", font=font("title", 56), fill=col, stroke_width=3, stroke_fill=(0, 0, 0))
        a2 = fx.ease((u - t_w - 1.2) / 0.5) * (1 - fx.ease((u - t_e + 0.3) / 0.4))
        if a2 > 0.02:
            yy = at[1] + 0.16 / 1.30 * s0.height
            col = (int(230 * a2),) * 3
            d.line([(W * 0.06, yy), (W * 0.94, yy)], fill=col, width=3)
            for xx in (W * 0.06, W * 0.94):
                d.line([(xx, yy - 14), (xx, yy + 14)], fill=col, width=3)
            tw = d.textlength("날개 약 3m", font=font("title", 56))
            d.text((W / 2 - tw / 2, yy - 82), "날개 약 3m", font=font("title", 56), fill=col, stroke_width=3, stroke_fill=(0, 0, 0))
        return img


# ── 4. 신문 기사 ─────────────────────────────────────────

class Newspaper(Scene):
    def setup(self):
        W, H = self.W, self.H
        PW, PH = int(W * 1.3), int(H * 1.15)
        self.PW, self.PH = PW, PH
        desk = Image.fromarray(art.gradient(PW, PH, [(0, (26, 18, 12)), (1, (12, 8, 6))]).astype(np.uint8))
        fig, _, _ = creatures.mothman(W * 0.30, 0.75, 0, "stand", rim=(90, 90, 90), body=(30, 28, 26), membrane=(70, 66, 60), ss=2)
        pw = int(W * 1.12)
        page = art.newspaper(pw, int(pw * 1.45), self.p.get("masthead", "THE REGISTER"),
                             self.p.get("dateline", "POINT PLEASANT, W. VA.  ·  WEDNESDAY, NOVEMBER 16, 1966"),
                             self.p.get("headline", "COUPLES SEE\nMAN-SIZED BIRD...\nCREATURE...\nSOMETHING"),
                             self.p.get("sub", "Red-eyed thing chases car near TNT area"), seed=self.seed, figure=fig)
        page = page.convert("RGBA").rotate(-2.5, Image.BICUBIC, expand=True)
        self.page_at = (int(PW / 2 - page.width / 2), int(PH * 0.08))
        desk.paste(page, self.page_at, page)
        # 스탠드 조명
        yy, xx = np.mgrid[0:PH, 0:PW].astype(np.float32)
        r = np.sqrt((xx - PW * 0.45) ** 2 + (yy - PH * 0.30) ** 2) / (PW * 0.9)
        light = np.clip(1.15 - r, 0.25, 1.1)[..., None] * np.array([1.0, 0.93, 0.80])
        a = np.asarray(desk, np.float32) * light
        self.plate = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        self.head_y = self.page_at[1] + pw * 0.33
        # 빨간 도장
        st = Image.new("RGBA", (int(W * 0.8), int(W * 0.36)), (0, 0, 0, 0))
        d = ImageDraw.Draw(st)
        red = (200, 28, 24, 235)
        d.rounded_rectangle([6, 6, st.width - 6, st.height - 6], radius=20, outline=red, width=12)
        f = font("title", st.height * 0.48)
        tw = d.textlength("MOTHMAN", font=f)
        d.text(((st.width - tw) / 2, st.height * 0.08), "MOTHMAN", font=f, fill=red)
        f2 = font("title", st.height * 0.26)
        tw = d.textlength("모 스 맨", font=f2)
        d.text(((st.width - tw) / 2, st.height * 0.62), "모 스 맨", font=f2, fill=red)
        n = fx.value_noise(st.width, st.height, 12, 2, 4, wrap=False)
        a = np.asarray(st, np.float32).copy()
        a[..., 3] *= np.clip(n * 1.8 - 0.2, 0, 1)
        self.stamp = Image.fromarray(a.astype(np.uint8), "RGBA").rotate(8, Image.BICUBIC, expand=True)

    def draw(self, u):
        W, H = self.W, self.H
        p = fx.ease(u / self.dur)
        zoom = 1.55 - 0.40 * p
        img = fx.view(self.plate, self.PW / 2, self.head_y + (self.PH * 0.48 - self.head_y) * p, zoom, W, H)
        t_s = self.e("stamp", self.dur * 0.55)
        if u >= t_s:
            k = fx.ease((u - t_s) / 0.12)
            sc = 1.8 - 0.8 * k
            s = self.stamp.resize((int(self.stamp.width * sc), int(self.stamp.height * sc)), Image.BILINEAR)
            fx.paste(img, s, (W / 2 - s.width / 2, H * 0.42 - s.height / 2), min(1, 0.3 + k))
        return img


# ── 5. 숲속 수많은 붉은 눈 (목격담) ───────────────────────

class Sightings(Scene):
    def setup(self):
        W, H = self.W, self.H
        PW, PH = int(W * 1.2), int(H * 1.15)
        self.PW, self.PH = PW, PH
        plate = art.sky(PW, PH, [(0, (10, 14, 24)), (0.5, (40, 48, 66)), (1, (20, 24, 30))], seed=self.seed, stars=40,
                        moon=(PW * 0.5, PH * 0.20, PW * 0.06), clouds=0.5, cloud_color=(58, 66, 86))
        for i, (gy, col, hmin, hmax, cnt) in enumerate(((0.55, (16, 19, 25), 0.25, 0.4, 25), (0.68, (10, 12, 16), 0.35, 0.55, 14), (0.85, (4, 5, 7), 0.6, 0.85, 7))):
            layer = art.forest(PW, PH, gy, col, seed=self.seed + i, count=cnt, hmin=hmin, hmax=hmax, kind="bare", ss=1)
            plate.paste(layer, (0, 0), layer)
            f = fx.fog(PW, PH, (70, 80, 98), 0.55 - 0.12 * i, 300, self.seed + 10 + i, gy - 0.15, gy + 0.02)
            plate.paste(f, (0, 0), f)
        self.plate = plate
        rng = np.random.default_rng(self.seed)
        self.eyes = []
        n = 34
        for k in range(n):
            depth = rng.uniform(0.25, 1.0)
            self.eyes.append(dict(x=rng.uniform(0.08, 0.92) * W, y=rng.uniform(0.28, 0.62) * H,
                                  r=4 + 12 * depth, t=(k / n) ** 1.3 * self.dur * 0.8 + rng.uniform(0, 0.2),
                                  blink=rng.uniform(0, 10), dim=0.35 + 0.65 * depth))
        self.eye_cache = {}
        self.fog = fx.fog(W, H, (70, 78, 92), 0.30, 350, self.seed + 20, 0.4, 0.9)

    def _eye(self, r):
        k = int(r)
        if k not in self.eye_cache:
            self.eye_cache[k] = creatures.eye_glow(k)
        return self.eye_cache[k]

    def draw(self, u):
        W, H = self.W, self.H
        p = u / self.dur
        img = fx.view(self.plate, self.PW * (0.5 + 0.05 * math.sin(p * 2)), self.PH * 0.5, 1.0 + 0.08 * p, W, H)
        for e in self.eyes:
            if u < e["t"]:
                continue
            a = fx.ease((u - e["t"]) / 0.25) * e["dim"]
            if math.sin(u * 1.3 + e["blink"]) > 0.985:
                a = 0
            g = self._eye(e["r"])
            for dx in (-1, 1):
                fx.add(img, g, a, (e["x"] + dx * e["r"] * 1.6 - g.width / 2, e["y"] - g.height / 2))
        f = fx.scroll(self.fog, u * 30)
        img.paste(f, (0, 0), f)
        # 숫자 카운터
        cnt = int(min(100, 100 * fx.ease(u / (self.dur * 0.8))))
        txt = f"{cnt}+" if cnt >= 100 else f"{cnt}"
        d = ImageDraw.Draw(img)
        f = font("title", 190)
        tw = d.textlength(txt, font=f)
        d.text((W / 2 - tw / 2, H * 0.40), txt, font=f, fill=(235, 50, 40), stroke_width=6, stroke_fill=(0, 0, 0))
        f2 = font("title", 58)
        lab = "목격자"
        tw = d.textlength(lab, font=f2)
        d.text((W / 2 - tw / 2, H * 0.40 - 70), lab, font=f2, fill=(230, 230, 230), stroke_width=4, stroke_fill=(0, 0, 0))
        return img


# ── 6. 실버 브리지 붕괴 ─────────────────────────────────

class Bridge(Scene):
    """세계 좌표 (가로 WW, 세로 H) 에 다리를 두고, 매 프레임 화면 좌표로 바꿔 그린다."""

    def setup(self):
        W, H = self.W, self.H
        WW = int(W * 2.0)
        self.WW = WW
        self.water = 0.58 * H
        sk = art.sky(WW, H, [(0, (8, 10, 24)), (0.30, (30, 30, 58)), (0.50, (120, 66, 58)), (0.58, (196, 112, 66)), (1, (196, 112, 66))],
                     seed=self.seed, stars=80, clouds=0.45, cloud_color=(50, 36, 48))
        hills = Image.new("RGBA", (WW, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(hills)
        rng = np.random.default_rng(self.seed)
        pts = [(0, self.water)]
        for i in range(60):
            x = i / 59 * WW
            pts.append((x, self.water - H * (0.025 + 0.02 * math.sin(i * 0.35) + 0.01 * rng.random())))
        pts.append((WW, self.water))
        d.polygon(pts, fill=(28, 20, 32, 255))
        for _ in range(70):   # 마을 불빛
            x = rng.uniform(0, WW)
            y = self.water - rng.uniform(2, H * 0.02)
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 200, 120, 255))
        sk.paste(hills, (0, 0), hills)
        # 강: 하늘 반사
        a = np.asarray(sk, np.float32)
        wy = int(self.water)
        refl = a[max(0, 2 * wy - H):wy][::-1]
        n = fx.value_noise(WW, H - wy, 30, 3, self.seed + 3, wrap=False)[..., None]
        refl = refl[: H - wy] * (0.45 + 0.25 * n) * np.linspace(1, 0.4, H - wy)[:, None, None]
        a[wy:wy + len(refl)] = refl
        self.plate = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        self._geometry()
        self.mist = fx.fog(W, H, (150, 125, 125), 0.7, 220, self.seed + 4, 0.42, 0.58)

    def _geometry(self):
        H, WW = self.H, self.WW
        deck = self.water - H * 0.07
        self.deck = deck
        t1, t2 = WW * 0.27, WW * 0.73
        ttop = self.water - H * 0.25
        a1, a2 = WW * 0.02, WW * 0.98
        mid = deck - H * 0.012

        def chain_y(x):
            if x < t1:
                return ttop + (deck - ttop) * ((t1 - x) / (t1 - a1)) ** 1.15
            if x > t2:
                return ttop + (deck - ttop) * ((x - t2) / (a2 - t2)) ** 1.15
            u = (x - (t1 + t2) / 2) / ((t2 - t1) / 2)
            return mid + (ttop - mid) * u ** 2
        # 조각: 각자 회전 중심과 떨어지는 시각
        pieces = []
        cuts = list(np.linspace(a1, t1, 4)) + list(np.linspace(t1, t2, 10))[1:] + list(np.linspace(t2, a2, 4))[1:]
        for x0, x1 in zip(cuts[:-1], cuts[1:]):
            main = t1 <= x0 < t2
            # 오하이오 쪽(오른쪽) 탑 근처에서 먼저 끊어져 번진다
            delay = (abs(x0 - t2) / (t2 - t1)) * 0.9 if main else (0.6 + 0.4 * abs((x0 + x1) / 2 - (t1 + t2) / 2) / WW)
            segs = []
            xs = np.linspace(x0, x1, 8)
            segs.append(("line", [(x, chain_y(x)) for x in xs], 5, (52, 50, 58)))
            segs.append(("poly", [(x0, deck - 6), (x1, deck - 6), (x1, deck + 6), (x0, deck + 6)], 0, (30, 28, 34)))
            for x in np.arange(x0, x1, 22):
                segs.append(("line", [(x, chain_y(x)), (x, deck - 6)], 2, (44, 42, 50)))
            for x in np.arange(x0, x1, 30):  # 트러스
                segs.append(("line", [(x, deck - 6), (x + 15, deck - 18), (x + 30, deck - 6)], 2, (40, 38, 46)))
            cars = [(x, deck - 10) for x in np.arange(x0 + 10, x1, 70)]
            pieces.append(dict(segs=segs, cx=(x0 + x1) / 2, cy=deck, delay=delay,
                               rot=(0.35 if (x0 + x1) / 2 < (t1 + t2) / 2 else -0.35) * (1 if main else 0.5),
                               vx=(x0 + x1 - t1 - t2) * 0.03, cars=cars))
        for tx, dl, rot in ((t1, 0.7, -0.22), (t2, 0.15, 0.28)):
            segs = [("poly", [(tx - 12, self.water + 5), (tx - 8, ttop), (tx + 8, ttop), (tx + 12, self.water + 5)], 0, (36, 34, 42))]
            for k in range(5):
                y = ttop + (self.water - ttop) * (k + 0.5) / 5
                segs.append(("line", [(tx - 22, y), (tx + 22, y)], 4, (36, 34, 42)))
            segs.append(("poly", [(tx - 24, ttop - 6), (tx + 24, ttop - 6), (tx + 20, ttop + 6), (tx - 20, ttop + 6)], 0, (50, 48, 56)))
            pieces.append(dict(segs=segs, cx=tx, cy=self.water, delay=dl, rot=rot, vx=0, cars=[], tower=True))
        self.pieces = pieces
        self.t1, self.t2 = t1, t2
        # 물보라: 조각이 수면에 닿는 시각을 미리 계산해 둔다 (어느 워커가 그려도 같게)
        rng = np.random.default_rng(self.seed + 99)
        self.splash = []
        for pc in pieces:
            if pc.get("tower"):
                hit = pc["delay"] + 1.7
            else:
                hit = pc["delay"] + math.sqrt(max(1.0, self.water - pc["cy"]) / 450)
            for _ in range(45 if not pc.get("tower") else 70):
                self.splash.append(dict(x=pc["cx"] + pc["vx"] * (hit - pc["delay"]) + rng.uniform(-70, 70), t0=hit,
                                        vx=rng.uniform(-90, 90), vy=-rng.uniform(250, 700), r=rng.uniform(2, 6)))

    def _xf(self, pc, ct):
        """조각 변환: ct 초 뒤 위치."""
        tau = max(0.0, ct - pc["delay"])
        if pc.get("tower"):
            ang = pc["rot"] * tau ** 2 * 0.8
            dy = 0.5 * 120 * tau ** 2 * (1 if tau > 1.2 else 0.15)
        else:
            ang = pc["rot"] * tau ** 2
            dy = 0.5 * 900 * tau ** 2
        dx = pc["vx"] * tau
        c, s = math.cos(ang), math.sin(ang)
        cx, cy = pc["cx"], pc["cy"]
        return lambda x, y: (cx + (x - cx) * c - (y - cy) * s + dx, cy + (x - cx) * s + (y - cy) * c + dy), tau

    def draw(self, u):
        W, H = self.W, self.H
        t_c = self.e("collapse", self.dur * 0.45)
        ct = u - t_c
        sx, sy = self.shake(u, 10 * fx.ease(ct / 0.2) * (1 - fx.ease((ct - 1.5) / 2.5))) if ct > 0 else (0, 0)
        zoom = 1.0 + 0.05 * u / self.dur
        cxw = self.WW * (0.42 + 0.08 * fx.ease(u / max(t_c, 0.1))) + sx
        cyw = H * 0.5 + sy
        img = fx.view(self.plate, cxw, cyw, zoom, W, H)
        x0 = cxw - W / zoom / 2
        y0 = cyw - H / zoom / 2
        x0 = min(max(0, x0), self.WW - W / zoom)
        y0 = min(max(0, y0), H - H / zoom)
        ss = 2
        layer = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        lights = Image.new("RGB", (W, H), (0, 0, 0))
        dl = ImageDraw.Draw(lights)

        def S(pt):
            return ((pt[0] - x0) * zoom * ss, (pt[1] - y0) * zoom * ss)
        car_shift = (u * 60) % 70
        for pc in self.pieces:
            f, tau = self._xf(pc, ct if ct > 0 else -1)
            for kind, pts, wdt, col in pc["segs"]:
                q = [S(f(x, y)) for x, y in pts]
                if kind == "line":
                    d.line(q, fill=col + (255,), width=max(1, int(wdt * zoom * ss)))
                else:
                    d.polygon(q, fill=col + (255,))
            for (x, y) in pc["cars"]:
                X, Y = f(x + car_shift - 35, y)
                sxy = S((X, Y))
                if Y < self.water:
                    px, py = sxy[0] / ss, sxy[1] / ss
                    dl.ellipse([px - 3, py - 2, px + 3, py + 2], fill=(255, 220, 150))
        lay = layer.resize((W, H), Image.LANCZOS)
        # 수면 아래는 가린다
        wy = (self.water - y0) * zoom
        a = np.asarray(lay).copy()
        a[int(max(0, wy + 2)):, :, 3] = 0
        lay = Image.fromarray(a, "RGBA")
        img.paste(lay, (0, 0), lay)
        fx.add(img, fx.glow(lights, (2, 6), (1.0, 0.5)), 1.0)
        # 물보라 입자
        if self.splash:
            sp = Image.new("RGB", (W, H), (0, 0, 0))
            sd = ImageDraw.Draw(sp)
            for s in self.splash:
                tt = ct - s["t0"]
                if tt > 2.2:
                    continue
                X = s["x"] + s["vx"] * tt
                Y = self.water + s["vy"] * tt + 0.5 * 700 * tt ** 2
                if Y > self.water + 4:
                    continue
                px, py = (X - x0) * zoom, (Y - y0) * zoom
                b = int(200 * (1 - tt / 2.2))
                sd.ellipse([px - s["r"], py - s["r"], px + s["r"], py + s["r"]], fill=(b, b, b))
            fx.add(img, sp.filter(ImageFilter.GaussianBlur(1.5)), 1.0)
        # 물안개
        if ct > 0.8:
            m = fx.scroll(self.mist, u * 20)
            al = min(1.0, (ct - 0.8) / 2.0)
            if al < 1:
                m = m.copy()
                m.putalpha(m.getchannel("A").point(lambda v: int(v * al)))
            img.paste(m, (0, int((self.water - y0) * zoom - H * 0.55)), m)
        return img


# ── 7. 그 뒤 (교각 위의 그림자) ─────────────────────────

class Aftermath(Scene):
    def setup(self):
        W, H = self.W, self.H
        PW, PH = int(W * 1.2), int(H * 1.15)
        self.PW, self.PH = PW, PH
        wy = 0.62
        plate = art.sky(PW, PH, [(0, (2, 3, 8)), (0.5, (14, 16, 30)), (wy, (30, 32, 48)), (1, (6, 7, 10))],
                        seed=self.seed, moon=(PW * 0.7, PH * 0.16, PW * 0.045), clouds=0.6)
        d = ImageDraw.Draw(plate)
        # 강물 + 달빛 반사
        a = np.asarray(plate, np.float32).copy()
        y0 = int(wy * PH)
        n = fx.value_noise(PW, PH - y0, 25, 3, 3, wrap=False)
        streak = np.exp(-((np.arange(PW) - PW * 0.7) / (PW * 0.06)) ** 2)[None, :] * (n > 0.55)
        a[y0:] = a[y0:] * 0.4 + (streak[..., None] * np.array([120, 125, 140]))
        plate = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(plate)
        # 부서진 교각
        self.pier_x, self.pier_top = PW * 0.40, PH * 0.47
        px, pt = self.pier_x, self.pier_top
        d.polygon([(px - 70, y0 + 10), (px - 55, pt), (px - 10, pt - 20), (px + 25, pt + 8), (px + 55, pt), (px + 70, y0 + 10)], fill=(12, 12, 16))
        for k in range(4):
            yy = pt + (y0 - pt) * (k + 1) / 5
            d.line([(px - 62, yy), (px + 62, yy)], fill=(20, 20, 26), width=3)
        d.line([(px + 25, pt + 8), (px + 140, pt - 40), (px + 150, pt - 30)], fill=(14, 14, 18), width=7)  # 휘어진 철골
        self.plate = plate
        self.spr, self.eyes, r = creatures.mothman(H * 0.15, 0.1, 0, "stand", ss=2)
        self.eye = creatures.eye_glow(r * 1.2)
        self.fogs = [fx.fog(W, H, (90, 100, 115), 0.4, 300, self.seed + 5, 0.50, 0.85)]

    def draw(self, u):
        W, H = self.W, self.H
        p = u / self.dur
        zoom = 1.0 + 0.18 * fx.ease(p)
        cx, cy = self.pier_x, self.pier_top - H * 0.05
        vcx = self.PW / 2 + (cx - self.PW / 2) * fx.ease(p)
        vcy = self.PH / 2 + (cy - self.PH / 2) * fx.ease(p)
        img = fx.view(self.plate, vcx, vcy, zoom, W, H)
        bw, bh = W / zoom, H / zoom
        x0 = min(max(0, vcx - bw / 2), self.PW - bw)
        y0 = min(max(0, vcy - bh / 2), self.PH - bh)
        t_gone = self.e("gone", self.dur * 0.8)
        a = 1 - fx.ease((u - t_gone) / 0.8)
        s = self.spr.resize((int(self.spr.width * zoom), int(self.spr.height * zoom)), Image.BILINEAR)
        foot_x = (cx - x0) * zoom
        foot_y = (self.pier_top - 18 - y0) * zoom
        at = (foot_x - s.width / 2, foot_y - s.height * (1.22 / 1.30))
        fx.paste(img, s, at, a)
        e = self.eye.resize((int(self.eye.width * zoom), int(self.eye.height * zoom)), Image.BILINEAR)
        blink = 0 if 0.98 < (u * 0.7) % 1 else 1
        for ex, ey in self.eyes:
            fx.add(img, e, a * blink * (0.9 + 0.1 * math.sin(u * 9)), (at[0] + ex * zoom - e.width / 2, at[1] + ey * zoom - e.height / 2))
        for f in self.fogs:
            f = fx.scroll(f, u * 25)
            img.paste(f, (0, 0), f)
        return img


# ── 8. 끝 화면 (구독 유도) ──────────────────────────────

class EndCard(Scene):
    def setup(self):
        W, H = self.W, self.H
        self.bg = Image.new("RGB", (W, H), (4, 4, 6))
        self.fog = fx.fog(W, H, (60, 64, 76), 0.45, 300, self.seed, 0.2, 0.9)
        self.eye = creatures.eye_glow(26)

    def draw(self, u):
        from . import config
        W, H = self.W, self.H
        img = self.bg.copy()
        f = fx.scroll(self.fog, u * 30)
        img.paste(f, (0, 0), f)
        a = fx.ease(u / 0.6)
        for dx in (-1, 1):
            fx.add(img, self.eye, a, (W / 2 + dx * 44 - self.eye.width / 2, H * 0.36 - self.eye.height / 2))
        d = ImageDraw.Draw(img)
        k = int(255 * fx.ease((u - 0.3) / 0.5))
        sname, snext = H * 0.054, H * 0.024      # 화면 높이에 비례 (가로 영상에서 겹치지 않게)
        f1 = font("title", int(sname))
        name = config.CHANNEL_NAME
        y_name = H * 0.44
        tw = d.textlength(name, font=f1)
        d.text((W / 2 - tw / 2, y_name), name, font=f1, fill=(k, k, k),
               stroke_width=max(2, int(H * 0.0026)), stroke_fill=(0, 0, 0))
        nxt = self.p.get("next", "")
        if nxt:
            f2 = font("gothic", int(snext))
            tw = d.textlength(nxt, font=f2)
            kk = int(200 * fx.ease((u - 0.8) / 0.5))
            d.text((W / 2 - tw / 2, y_name + sname * 1.45), nxt, font=f2, fill=(kk, int(kk * 0.3), int(kk * 0.25)))
        return img


SCENES = {"road": RoadChase, "tnt": TNTArea, "reveal": Reveal, "news": Newspaper, "sightings": Sightings,
          "bridge": Bridge, "aftermath": Aftermath, "end": EndCard}
