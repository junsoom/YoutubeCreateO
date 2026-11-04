"""괴물 실루엣. 새 괴물은 같은 모양의 함수(sprite, eyes)를 추가한다.

반환: (RGBA 몸 스프라이트, [(눈 x, 눈 y), ...] 스프라이트 좌표, 눈 반지름)
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops


def _lerp(a, b, s):
    return (a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s)


def _bezier(p0, p1, p2, u):
    return ((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u ** 2 * p2[0],
            (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u ** 2 * p2[1])


def _wing(sgn, s, flap):
    """날개 한쪽 다각형과 손가락 뼈 (정규 좌표: 키 1.0, x 는 몸 중심 기준)."""
    sh = (sgn * 0.11, 0.18)
    wrist = _lerp((sgn * 0.20, 0.07), (sgn * 0.60, -0.08), s)
    tip = _lerp((sgn * 0.27, 0.32), (sgn * 1.18, 0.10), s)
    wrist = (wrist[0], wrist[1] + flap * 0.12 * s)
    tip = (tip[0], tip[1] + flap * 0.34 * s)
    attach = _lerp((sgn * 0.16, 0.86), (sgn * 0.09, 0.60), s)
    ctrl = _lerp((sgn * 0.33, 0.70), (sgn * 0.78, 0.62 + flap * 0.15), s)
    fingers = [_bezier(tip, ctrl, attach, u) for u in (0.0, 0.30, 0.56, 0.80, 1.0)]
    poly = [sh]
    mid = _lerp(sh, wrist, 0.5)
    poly.append((mid[0], mid[1] - 0.03 * s))
    poly.append(wrist)
    poly.append(tip)
    for a, b in zip(fingers[:-1], fingers[1:]):
        # 박쥐 날개처럼 안쪽으로 파인 가장자리
        m = _lerp(a, b, 0.5)
        inward = _lerp(m, wrist, 0.16 + 0.06 * s)
        for u in np.linspace(0.15, 0.85, 5):
            poly.append(_bezier(a, inward, b, u))
        poly.append(b)
    poly.append((sgn * 0.08, 0.50))
    bones = [(wrist, f) for f in fingers[:-1]] + [(sh, wrist)]
    return poly, bones


def mothman(height, spread=0.0, flap=0.0, legs="stand", rim=(150, 170, 205), body=(10, 10, 14),
            membrane=(20, 21, 27), ss=3):
    H = height * ss
    W = int(H * 2.5)
    CH = int(H * 1.30)
    cx, top = W / 2, H * 0.22

    def P(p):
        return (cx + p[0] * H, top + p[1] * H)

    mask_w = Image.new("L", (W, CH), 0)   # 날개
    mask_b = Image.new("L", (W, CH), 0)   # 몸
    dw, db = ImageDraw.Draw(mask_w), ImageDraw.Draw(mask_b)
    bones_all = []
    for sgn in (-1, 1):
        poly, bones = _wing(sgn, spread, flap)
        dw.polygon([P(p) for p in poly], fill=255)
        bones_all += bones
    # 몸통 (머리는 어깨에 파묻힌 듯 낮게)
    torso = [(-0.05, 0.15), (-0.12, 0.17), (-0.14, 0.23), (-0.125, 0.34), (-0.085, 0.50), (-0.105, 0.58),
             (0.105, 0.58), (0.085, 0.50), (0.125, 0.34), (0.14, 0.23), (0.12, 0.17), (0.05, 0.15)]
    db.polygon([P(p) for p in torso], fill=255)
    hx, hy = P((0, 0.10))
    db.ellipse([hx - 0.065 * H, hy - 0.075 * H, hx + 0.065 * H, hy + 0.07 * H], fill=255)
    if legs == "stand":
        for sgn in (-1, 1):
            leg = [(sgn * 0.10, 0.56), (sgn * 0.01, 0.58), (sgn * 0.035, 0.78), (sgn * 0.04, 0.965),
                   (sgn * 0.095, 1.0), (sgn * 0.075, 0.955), (sgn * 0.09, 0.78)]
            db.polygon([P(p) for p in leg], fill=255)
    else:  # 날 때: 다리를 모아 뒤로
        for sgn in (-1, 1):
            leg = [(sgn * 0.08, 0.56), (sgn * 0.005, 0.58), (sgn * 0.015, 0.80), (sgn * 0.03, 0.86), (sgn * 0.06, 0.80)]
            db.polygon([P(p) for p in leg], fill=255)

    full = ImageChops.lighter(mask_w, mask_b)
    a_w = np.asarray(mask_w, np.float32)[..., None] / 255
    a_b = np.asarray(mask_b, np.float32)[..., None] / 255
    col = np.array(membrane, np.float32) * a_w * (1 - a_b) + np.array(body, np.float32) * a_b
    # 날개 뼈 (조금 밝게)
    bone_img = Image.new("L", (W, CH), 0)
    bd = ImageDraw.Draw(bone_img)
    for a, b in bones_all:
        bd.line([P(a), P(b)], fill=255, width=max(2, int(H * 0.008)))
    bone = np.asarray(bone_img.filter(ImageFilter.GaussianBlur(H * 0.003)), np.float32)[..., None] / 255
    col = col * (1 - bone * 0.6) + np.array([38, 40, 48], np.float32) * bone * 0.6 * a_w
    # 왼쪽 위에서 오는 달빛 테두리
    k = max(2, int(H * 0.01))
    rim_m = ImageChops.subtract(full, ImageChops.offset(full, k, k)).filter(ImageFilter.GaussianBlur(k * 0.6))
    r = np.asarray(rim_m, np.float32)[..., None] / 255
    col = col * (1 - r * 0.8) + np.array(rim, np.float32) * r * 0.8
    alpha = np.asarray(full, np.float32)
    rgba = np.dstack([np.clip(col, 0, 255), alpha]).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA").resize((W // ss, CH // ss), Image.LANCZOS)
    eyes = [((cx + sgn * 0.034 * H) / ss, (top + 0.10 * H) / ss) for sgn in (-1, 1)]
    return img, eyes, 0.024 * H / ss


def eye_glow(radius, color=(255, 30, 20), intensity=1.0, squint=0.65):
    """붉은 눈 하나의 발광 스프라이트 (RGB, 더하기 합성용). 중심이 스프라이트 중앙."""
    R = max(2.0, radius)
    s = int(R * 14)
    img = Image.new("RGB", (s, s), (0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    d.ellipse([c - R, c - R * squint, c + R, c + R * squint], fill=tuple(int(v * intensity) for v in color))
    core = (int(255 * intensity), int(190 * intensity), int(160 * intensity))
    d.ellipse([c - R * 0.45, c - R * 0.3 * squint, c + R * 0.45, c + R * 0.3 * squint], fill=core)
    acc = np.asarray(img, np.float32)
    for rad, g in ((R * 0.8, 1.2), (R * 2.2, 1.4), (R * 5, 1.0)):
        acc = acc + np.asarray(img.filter(ImageFilter.GaussianBlur(rad)), np.float32) * g
    return Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8))
