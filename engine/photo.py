"""실제 사진 장면 (2026-10-29 사용자 피드백: 그림 대신 실제 사진, 리얼하고 무섭게).

params:
  key       assets/photos/<key>.jpg (출처는 credits.json)
  mode      "fill" 화면 가득 / "fit" 가로 맞춤 + 흐린 배경
  crop      [l, t, r, b] 원본에서 쓸 부분 (0~1). 스캔 테두리·글자 띠 제거용
  focus     [[x0, y0], [x1, y1]] 카메라 중심 시작→끝 (crop 기준 0~1)
  zoom      [z0, z1] 확대 시작→끝
  grade     "cold"(기본) | "bw" | "sepia" | "color"
  eyes      [[x, y, r], ...] 붉은 눈을 켤 자리 (crop 기준 0~1, r 은 폭 대비)
  label     사진 왼쪽 위 작은 표시 (예: "진위 불명")
  counter   [끝 숫자, "글자"]  숫자가 올라간다
  stamp_word 스탬프 이벤트 (events.stamp) 때 찍을 빨간 도장 글자
  glitch    ["ev:이름" 또는 초, ...] 화면 깨짐
  figure    {"x","y" 발 위치, "h" 사진 높이 대비 키, "spread" 날개 0~1} 사진 위에 괴물 실루엣 합성 (재현용, events.figure 에 서서히 나타남)
            반드시 label 로 "재현 이미지" 를 표시한다. 실루엣의 눈은 eyes 에 자동으로 더해진다.
  label_ev  label 을 이 이벤트부터 보여 준다
  shake     흔들림 세기 (기본 0)
  exposure  밝기 배율 (흰 종이·낮 사진은 0.5~0.6)
events: eyes (눈 켜짐), stamp (도장)
"""
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import fx
from .creatures import eye_glow
from .fonts import font
from .scenes import Scene

PHOTOS = Path(__file__).resolve().parent.parent / "assets" / "photos"


@lru_cache(maxsize=1)
def credits():
    p = PHOTOS / "credits.json"
    return json.loads(p.read_text()) if p.exists() else {}


def credit_text(key):
    c = credits().get(key)
    if not c:
        return ""
    who = c["author"].strip() or "Unknown"
    if len(who) > 34:
        who = who[:33] + "…"
    lic = c["license"].replace("No restrictions", "Public domain")
    return f"사진: {who} · {lic} · Wikimedia Commons"


def grade(img, kind="cold", exposure=1.0):
    a = np.asarray(img.convert("RGB"), np.float32) / 255
    lum = (a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114)[..., None]
    if kind == "color":
        sat, tint = 0.75, np.array([0.0, 0.01, 0.03])
    elif kind == "bw":
        sat, tint = 0.0, np.array([0.0, 0.01, 0.02])
    elif kind == "sepia":
        sat, tint = 0.0, np.array([0.06, 0.03, -0.02])
    else:  # cold: 거의 흑백 + 차가운 청록
        sat, tint = 0.22, np.array([-0.02, 0.02, 0.05])
    a = lum + (a - lum) * sat
    # 대비 S 커브 + 검정 눌러 주기
    a = np.clip(a, 0, 1)
    a = a * a * (3 - 2 * a) * 0.55 + a * 0.45
    a = np.clip((a - 0.04) / 0.96, 0, 1) ** 1.12
    shadow = (1 - lum) ** 2
    a = a + tint * shadow * 1.6
    if exposure != 1.0:   # 밝은 사진(흰 종이, 낮 하늘)을 밤처럼 누른다. 밝은 곳일수록 더 누른다.
        a = a * exposure * (1 - 0.25 * (1 - exposure) * a)
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def _cover(iw, ih, W, H):
    return max(W / iw, H / ih)


class Photo(Scene):
    def setup(self):
        W, H = self.W, self.H
        p = self.p
        self.key = p["key"]
        src = Image.open(PHOTOS / f"{self.key}.jpg").convert("RGB")
        if p.get("crop"):
            l, t, r, b = p["crop"]
            src = src.crop((int(l * src.width), int(t * src.height), int(r * src.width), int(b * src.height)))
        self.src = grade(src, p.get("grade", "cold"), p.get("exposure", 1.0))
        self.mode = p.get("mode", "fill" if src.height > src.width else "fit")
        iw, ih = self.src.size
        self.wide = W > H   # 롱폼(가로 화면)
        if self.mode == "fit":
            # 쇼츠: 가로 맞춤. 롱폼: 화면 안에 다 들어가게 (세로 사진은 양옆 흐린 배경)
            sc = W / iw if not self.wide else min(W / iw, H * p.get("fit_h", 0.9) / ih)
            self.fw = int(round(iw * sc))
            self.fh = int(round(ih * sc))
            self.fx0 = (W - self.fw) // 2
            self.fy = int(H * p.get("fit_y", 0.42 if not self.wide else 0.5) - self.fh / 2)
            s = _cover(iw, ih, W, H) * 1.1
            bg = self.src.resize((int(iw * s), int(ih * s)), Image.BILINEAR)
            bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
            bg = bg.filter(ImageFilter.GaussianBlur(28))
            self.bg = Image.fromarray((np.asarray(bg, np.float32) * 0.32).astype(np.uint8))
            self.vw, self.vh = self.fw, self.fh
        else:
            self.vw, self.vh = W, H
        z = p.get("zoom", [1.0, 1.12])
        self.z0, self.z1 = z
        f = p.get("focus", [[0.5, 0.5], [0.5, 0.5]])
        self.f0, self.f1 = f
        self.eyes = p.get("eyes", [])
        self.eye_cache = {}
        self.glitches = []
        rng = np.random.default_rng(self.seed)
        self.noise = rng.standard_normal(4096)
        self.credit = credit_text(self.key)
        self.fig_src = None
        if p.get("figure"):
            from .creatures import mothman
            f = p["figure"]
            iw, ih = self.src.size
            spr, eyes, r = mothman(ih * f.get("h", 0.08), f.get("spread", 0.3), 0, "stand",
                                   rim=(60, 64, 76), body=(6, 6, 8), membrane=(12, 12, 15), ss=2)
            spr = spr.filter(ImageFilter.GaussianBlur(0.8))
            ox = f["x"] * iw - spr.width / 2
            oy = f["y"] * ih - spr.height * (1.22 / 1.30)
            self.fig_src = self.src.copy()
            self.fig_src.paste(spr, (int(ox), int(oy)), spr)
            self.eyes = list(self.eyes) + [[(ox + ex) / iw, (oy + ey) / ih, r * 2.0 / iw] for ex, ey in eyes]

    def _box(self, u):
        """원본에서 잘라 올 영역 (x0, y0, x1, y1)."""
        iw, ih = self.src.size
        k = fx.ease(u / self.dur) if self.p.get("ease", True) else u / self.dur
        z = self.z0 + (self.z1 - self.z0) * k
        base = _cover(iw, ih, self.vw, self.vh)
        bw, bh = self.vw / (base * z), self.vh / (base * z)
        cx = (self.f0[0] + (self.f1[0] - self.f0[0]) * k) * iw
        cy = (self.f0[1] + (self.f1[1] - self.f0[1]) * k) * ih
        sh = self.p.get("shake", 0)
        if sh:
            sx, sy = self.shake(u, sh)
            cx += sx * bw / self.vw
            cy += sy * bh / self.vh
        bw, bh = min(bw, iw), min(bh, ih)          # 줌 1.0 에서 부동소수점 오차로 원본보다 커지는 것 막기
        x0 = max(0.0, min(max(0, cx - bw / 2), iw - bw))
        y0 = max(0.0, min(max(0, cy - bh / 2), ih - bh))
        return x0, y0, x0 + bw, y0 + bh

    def _eye(self, r):
        k = max(2, int(r))
        if k not in self.eye_cache:
            self.eye_cache[k] = eye_glow(k, squint=0.7)
        return self.eye_cache[k]

    def draw(self, u):
        W, H = self.W, self.H
        box = self._box(u)
        view = self.src.resize((self.vw, self.vh), Image.BILINEAR, box=box)
        if self.fig_src is not None:
            fa = fx.ease((u - self.e("figure", self.dur * 0.4)) / 1.2)
            if fa > 0:
                fv = self.fig_src.resize((self.vw, self.vh), Image.BILINEAR, box=box)
                view = Image.blend(view, fv, fa)
        # 깜빡임: 오래된 영사기처럼 밝기가 미세하게 흔들린다
        fl = 1 + 0.035 * self.noise[int(u * 24) % 4096] * (0.6 + 0.4 * math.sin(u * 0.7))
        view = Image.fromarray(np.clip(np.asarray(view, np.float32) * fl, 0, 255).astype(np.uint8))
        # 붉은 눈
        if self.eyes:
            t_e = self.e("eyes", self.dur * 0.6)
            a = fx.ease((u - t_e) / 0.3)
            if a > 0:
                a *= 0.88 + 0.12 * math.sin(u * 12)
                sc = self.vw / (box[2] - box[0])
                iw = self.src.width
                for ex, ey, er in self.eyes:
                    px = (ex * iw - box[0]) * sc
                    py = (ey * self.src.height - box[1]) * sc
                    g = self._eye(er * iw * sc)
                    fx.add(view, g, a, (px - g.width / 2, py - g.height / 2))
        if self.mode == "fit":
            img = self.bg.copy()
            img.paste(view, (self.fx0, self.fy))
            d = ImageDraw.Draw(img)
            d.rectangle([self.fx0 - 2, self.fy - 2, self.fx0 + self.fw + 1, self.fy + self.fh + 1], outline=(0, 0, 0), width=3)
        else:
            img = view
        # 글리치
        for g in self.p.get("glitch_t", []):
            if 0 <= u - g < 0.28:
                img = self._glitch(img, u)
        return img

    def _glitch(self, img, u):
        a = np.asarray(img).copy()
        rng = np.random.default_rng(int(u * 1000))
        H = a.shape[0]
        for _ in range(7):
            y = rng.integers(0, H - 40)
            h = rng.integers(8, 70)
            a[y:y + h] = np.roll(a[y:y + h], rng.integers(-90, 90), axis=1)
        out = a.copy()
        out[..., 0] = np.roll(a[..., 0], 9, axis=1)
        out[..., 2] = np.roll(a[..., 2], -9, axis=1)
        return Image.fromarray(out)

    # 색 보정이 끝난 뒤 위에 얹는 글자들 (출처, 표시, 숫자, 도장)
    def overlay(self, img, u):
        W, H = self.W, self.H
        d = ImageDraw.Draw(img)
        from . import config as _cfg
        if self.credit and getattr(_cfg, "SHOW_CREDIT", True):
            f = font("gothic", 25 if not self.wide else 20)
            tw = d.textlength(self.credit, font=f)
            if self.wide:   # 롱폼은 화면 오른쪽 아래 모서리 (가리는 버튼 없음)
                y, x = H - 40, W - tw - 30
            else:
                y = (self.fy + self.fh + 10) if self.mode == "fit" else int(H * 0.615)
                x = W - tw - 26
            d.text((x, y), self.credit, font=f, fill=(205, 205, 205), stroke_width=2, stroke_fill=(0, 0, 0))
        if self.p.get("label") and u >= (self.e(self.p["label_ev"], 0) if self.p.get("label_ev") else 0):
            f = font("gothic", 34)
            lab = self.p["label"]
            if self.wide:
                y, x0 = 48, 48
            else:
                y, x0 = ((self.fy + 18) if self.mode == "fit" else int(H * 0.25)), 24
            tw = d.textlength(lab, font=f)
            d.rectangle([x0, y - 6, x0 + tw + 28, y + 44], fill=(150, 18, 16))
            d.text((x0 + 14, y), lab, font=f, fill=(255, 255, 255))
        if self.p.get("counter"):
            end, lab = self.p["counter"]
            n = int(min(end, end * fx.ease(u / (self.dur * 0.75))))
            txt = f"{n}+" if n >= end else f"{n}"
            f = font("title", 200)
            tw = d.textlength(txt, font=f)
            cy = (self.fy + self.fh / 2) if self.mode == "fit" else H * (0.42 if not self.wide else 0.45)
            d.text((W / 2 - tw / 2, cy - 100), txt, font=f, fill=(225, 40, 32), stroke_width=7, stroke_fill=(0, 0, 0))
            f2 = font("title", 60)
            tw = d.textlength(lab, font=f2)
            d.text((W / 2 - tw / 2, cy - 180), lab, font=f2, fill=(235, 235, 235), stroke_width=4, stroke_fill=(0, 0, 0))
        if self.p.get("stamp_word"):
            t_s = self.e("stamp", self.dur * 0.5)
            if u >= t_s:
                st = _stamp(self.p["stamp_word"], self.p.get("stamp_sub", ""), W)
                k = fx.ease((u - t_s) / 0.12)
                sc = 1.8 - 0.8 * k
                s = st.resize((int(st.width * sc), int(st.height * sc)), Image.BILINEAR)
                cy = (self.fy + self.fh * 0.7) if self.mode == "fit" else H * 0.47
                fx.paste(img, s, (W / 2 - s.width / 2, cy - s.height / 2), min(1, 0.3 + k))
        return img


@lru_cache(maxsize=4)
def _stamp(word, sub, W):
    st = Image.new("RGBA", (int(W * 0.8), int(W * 0.36)), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    red = (205, 26, 22, 240)
    d.rounded_rectangle([6, 6, st.width - 6, st.height - 6], radius=20, outline=red, width=12)
    f = font("title", st.height * (0.48 if sub else 0.6))
    tw = d.textlength(word, font=f)
    d.text(((st.width - tw) / 2, st.height * (0.08 if sub else 0.14)), word, font=f, fill=red)
    if sub:
        f2 = font("title", st.height * 0.26)
        tw = d.textlength(sub, font=f2)
        d.text(((st.width - tw) / 2, st.height * 0.62), sub, font=f2, fill=red)
    n = fx.value_noise(st.width, st.height, 12, 2, 4, wrap=False)
    a = np.asarray(st, np.float32).copy()
    a[..., 3] *= np.clip(n * 1.8 - 0.2, 0, 1)
    return Image.fromarray(a.astype(np.uint8), "RGBA").rotate(8, Image.BICUBIC, expand=True)


class PhotoEnd(Photo):
    """끝 화면: 사진을 아주 어둡게 깔고 채널명 + 다음 편 예고."""

    def draw(self, u):
        img = super().draw(u)
        a = np.asarray(img, np.float32) * 0.28
        return Image.fromarray(a.astype(np.uint8))

    def overlay(self, img, u):
        """끝 화면: 글리치 'ERROR 404 · FILE NOT FOUND' → 채널명 → 다음 파일 예고."""
        from . import config
        W, H = self.W, self.H
        d = ImageDraw.Draw(img)
        # 글자 크기·위치는 모두 화면 높이에 비례한다 (세로 1920 / 가로 1080 둘 다 겹치지 않게)
        s404 = H * 0.156           # 1920 → 300
        ssub = H * 0.027           # 1920 → 52
        sname = H * 0.068          # 1920 → 130
        snext = H * 0.023          # 1920 → 44
        # 404: 빨간 글자를 RGB 로 어긋나게 겹쳐 흔들리는 화면 오류처럼
        a = fx.ease(u / 0.35)
        f = font("title", int(s404))
        txt = "404"
        tw = d.textlength(txt, font=f)
        x, y = W / 2 - tw / 2, H * 0.24
        jit = max(2, int(H * 0.005)) if (int(u * 12) % 7 == 0) else max(1, int(H * 0.0016))
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for dx, col in ((-jit, (120, 0, 0)), (jit, (0, 40, 70)), (0, (230, 30, 26))):
            ld.text((x + dx, y), txt, font=f, fill=col)
        fx.add(img, layer, a)
        d = ImageDraw.Draw(img)
        f2 = font("type", int(ssub))
        sub = "FILE NOT FOUND"
        n = int(max(0, u - 0.3) / 0.05)
        y_sub = y + s404 * 1.1
        tw = d.textlength(sub, font=f2)
        d.text((W / 2 - tw / 2, y_sub), sub[:n], font=f2, fill=(220, 220, 215))
        k = int(255 * fx.ease((u - 1.0) / 0.5))
        name = config.CHANNEL_NAME
        f1 = font("logo" if name.isascii() else "title", int(sname if name.isascii() else sname * 0.86))
        y_name = y_sub + ssub * 2.2
        tw = d.textlength(name, font=f1)
        d.text((W / 2 - tw / 2, y_name), name, font=f1, fill=(k, k, k), stroke_width=max(2, int(H * 0.0026)),
               stroke_fill=(0, 0, 0))
        nxt = self.p.get("next", "")
        if nxt:
            f3 = font("gothic", int(snext))
            tw = d.textlength(nxt, font=f3)
            kk = int(215 * fx.ease((u - 1.4) / 0.5))
            d.text((W / 2 - tw / 2, y_name + sname * 1.45), nxt, font=f3, fill=(kk, int(kk * 0.32), int(kk * 0.26)))
        return img


class Chapter(Photo):
    """롱폼 챕터 카드: 아주 어둡고 흐린 사진 위에 'CHAPTER 02' + 한국어 제목.
    params: key(배경 사진, 생략 가능), num, title, sub(작은 설명)"""

    def setup(self):
        if self.p.get("key"):
            super().setup()
        else:
            self.credit = ""
            self.mode = "none"
        W, H = self.W, self.H
        self.fog = fx.fog(W, H, (60, 66, 78), 0.35, 400, self.seed + 2, 0.2, 1.0)

    def draw(self, u):
        W, H = self.W, self.H
        if self.p.get("key"):
            img = super().draw(u).filter(ImageFilter.GaussianBlur(6))
            img = Image.fromarray((np.asarray(img, np.float32) * 0.22).astype(np.uint8))
        else:
            img = Image.new("RGB", (W, H), (6, 7, 9))
        f = fx.scroll(self.fog, u * 25)
        img.paste(f, (0, 0), f)
        return img

    def overlay(self, img, u):
        W, H = self.W, self.H
        d = ImageDraw.Draw(img)
        lab = f"FILE 404  ·  CHAPTER {int(self.p.get('num', 1)):02d}"
        fm = font("mono", int(H * 0.034))
        n = int(max(0, u - 0.15) / 0.035)
        tw = d.textlength(lab, font=fm)
        d.text(((W - tw) / 2, H * 0.36), lab[:n], font=fm, fill=(214, 36, 30))
        a = fx.ease((u - 0.5) / 0.4)
        if a > 0:
            ft = font("title", int(H * 0.085))
            t = self.p.get("title", "")
            tw = d.textlength(t, font=ft)
            k = int(240 * a)
            d.text(((W - tw) / 2, H * 0.43), t, font=ft, fill=(k, k, k), stroke_width=3, stroke_fill=(0, 0, 0))
            lw = int(W * 0.12 * a)
            d.rectangle([W / 2 - lw, H * 0.56, W / 2 + lw, H * 0.56 + 4], fill=(214, 36, 30))
            if self.p.get("sub"):
                fs = font("gothic", int(H * 0.03))
                tw = d.textlength(self.p["sub"], font=fs)
                d.text(((W - tw) / 2, H * 0.59), self.p["sub"], font=fs, fill=(int(170 * a),) * 3)
        if u < 0.25:
            img = fx.glitch(img, int(u * 1000), 1.0 - u / 0.25)
        return img
