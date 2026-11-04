"""화면 효과: 노이즈, 안개, 필름 그레인, 비네팅, 발광."""
import numpy as np
from PIL import Image, ImageFilter, ImageChops


def value_noise(w, h, cell, octaves=4, seed=0, wrap=True):
    """부드러운 노이즈 (0~1, float32). wrap=True 면 가로로 이어 붙여도 이음새가 없다."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = max(2, cell / (2 ** o))
        gw, gh = max(2, int(w / c) + 1), max(2, int(h / c) + 2)
        g = rng.random((gh, gw)).astype(np.float32)
        if wrap:
            big = np.tile(g, (1, 3))
            im = Image.fromarray((big * 255).astype(np.uint8)).resize((w * 3, h), Image.BICUBIC)
            a = np.asarray(im, np.float32)[:, w:2 * w] / 255
        else:
            a = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
        out += a * amp
        tot += amp
        amp *= 0.5
    return out / tot


def fog(w, h, color=(150, 165, 185), density=0.5, cell=420, seed=0, top=0.0, bottom=1.0, contrast=1.6):
    """가로로 흐를 수 있는 안개 레이어 (RGBA). top~bottom 세로 범위에 몰린다."""
    n = value_noise(w, h, cell, 4, seed)
    n = np.clip((n - 0.5) * contrast + 0.5, 0, 1)
    y = np.linspace(0, 1, h)[:, None]
    mid, half = (top + bottom) / 2, max(1e-3, (bottom - top) / 2)
    band = np.clip(1 - np.abs(y - mid) / half, 0, 1) ** 0.8
    a = (n * band * density * 255).astype(np.uint8)
    rgb = np.empty((h, w, 3), np.uint8)
    rgb[:] = color
    return Image.fromarray(np.dstack([rgb, a]), "RGBA")


def scroll(img, dx):
    """가로로 감기는 스크롤 (wrap)."""
    dx = int(dx) % img.width
    if dx == 0:
        return img
    return ImageChops.offset(img, dx, 0)


def vignette(w, h, strength=0.65, power=2.2):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (x - w / 2) / (w / 2), (y - h / 2) / (h / 2)
    r = np.sqrt(nx ** 2 * 0.8 + ny ** 2 * 0.6)
    return (1 - strength * np.clip(r, 0, 1.4) ** power / (1.4 ** power) * 1.6).clip(0.15, 1)[..., None].astype(np.float32)


class Grader:
    """최종 색감: 비네팅 + 필름 그레인 + 약간의 청록/붉은 톤."""

    def __init__(self, w, h, seed=3, grain=10.0):
        self.vig = vignette(w, h)
        rng = np.random.default_rng(seed)
        self.grains = []
        for _ in range(6):
            g = rng.standard_normal((h // 2, w // 2)).astype(np.float32)
            g = np.asarray(Image.fromarray(np.clip(g * 40 + 128, 0, 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), np.float32)
            self.grains.append(((g - 128) / 40 * grain)[..., None])

    def __call__(self, img, i, flash=0.0, fade=1.0):
        a = np.asarray(img, np.float32)
        a = a * self.vig + self.grains[i % len(self.grains)]
        # 그림자에 청록, 밝은 곳은 그대로
        a[..., 2] += 6
        a[..., 0] -= 2
        a = 255 * (np.clip(a, 0, 255) / 255) ** 0.88   # 살짝 밝게 (폰 화면에서 뭉개지지 않게)
        if flash > 0:
            a = a + (255 - a) * flash
        if fade < 1:
            a = a * fade
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def glow(img, radii=(6, 18, 48), gains=(1.0, 0.8, 0.6)):
    """RGB(검은 바탕) 광원 이미지를 여러 번 흐려 더한 발광 레이어."""
    acc = np.asarray(img, np.float32).copy()
    for r, g in zip(radii, gains):
        acc += np.asarray(img.filter(ImageFilter.GaussianBlur(r)), np.float32) * g * 2.2
    return Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8))


def add(base, light, gain=1.0, at=(0, 0)):
    """base(RGB) 위에 light(RGB) 를 더하기(발광) 합성."""
    x, y = int(at[0]), int(at[1])
    region = (max(0, x), max(0, y), min(base.width, x + light.width), min(base.height, y + light.height))
    if region[2] <= region[0] or region[3] <= region[1]:
        return base
    crop_l = light.crop((region[0] - x, region[1] - y, region[2] - x, region[3] - y))
    b = np.asarray(base.crop(region), np.float32)
    l = np.asarray(crop_l, np.float32) * gain
    base.paste(Image.fromarray(np.clip(b + l, 0, 255).astype(np.uint8)), region[:2])
    return base


def paste(base, sprite, at, alpha=1.0):
    """RGBA 스프라이트를 base(RGB) 에 알파 합성."""
    if alpha <= 0:
        return base
    if alpha < 1:
        sprite = sprite.copy()
        sprite.putalpha(sprite.getchannel("A").point(lambda v: int(v * alpha)))
    base.paste(sprite, (int(at[0]), int(at[1])), sprite)
    return base


def view(plate, cx, cy, zoom, w, h):
    """plate 에서 (cx,cy) 중심, zoom 배로 w×h 화면을 잘라 낸다 (소수점 이동이 부드럽다)."""
    bw, bh = w / zoom, h / zoom
    x0 = min(max(0, cx - bw / 2), plate.width - bw)
    y0 = min(max(0, cy - bh / 2), plate.height - bh)
    return plate.resize((w, h), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))


def ease(p):
    p = min(1, max(0, p))
    return p * p * (3 - 2 * p)


def glitch(img, seed, strength=1.0):
    """가로 띠 밀림 + RGB 어긋남."""
    a = np.asarray(img).copy()
    rng = np.random.default_rng(seed)
    H = a.shape[0]
    for _ in range(int(6 * strength) + 1):
        y = rng.integers(0, H - 40)
        h = rng.integers(8, 80)
        a[y:y + h] = np.roll(a[y:y + h], int(rng.integers(-90, 90) * strength), axis=1)
    out = a.copy()
    k = int(10 * strength)
    out[..., 0] = np.roll(a[..., 0], k, axis=1)
    out[..., 2] = np.roll(a[..., 2], -k, axis=1)
    return Image.fromarray(out)


def punch(img, zoom, dx=0.0, dy=0.0):
    """가운데 기준 확대 + 이동 (펀치 줌·흔들림)."""
    if zoom <= 1.0005 and abs(dx) < 0.5 and abs(dy) < 0.5:
        return img
    W, H = img.size
    bw, bh = W / zoom, H / zoom
    x0 = min(max(0, (W - bw) / 2 + dx), W - bw)
    y0 = min(max(0, (H - bh) / 2 + dy), H - bh)
    return img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))
