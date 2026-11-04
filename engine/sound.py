"""효과음·배경음 합성. 외부 음원 없이 numpy 로 직접 만든다 (저작권 걱정 없음)."""
import numpy as np

from .config import SR

RNG = np.random.default_rng(7)


def t_axis(sec):
    return np.arange(int(sec * SR)) / SR


def band(x, lo=None, hi=None):
    """FFT 대역 필터 (짧은 버퍼용)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, n).astype(np.float32)


def env(n, a, d, sustain=0.0):
    """attack a 초, 지수 감쇠 d 초."""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * (sustain + (1 - sustain) * np.exp(-np.maximum(0, t - a) / d))
    return e.astype(np.float32)


def noise(sec):
    return RNG.standard_normal(int(sec * SR)).astype(np.float32)


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) or 1
    return (x / m * peak).astype(np.float32)


# ── 효과음 ──────────────────────────────────────────

def boom(sec=2.5):
    t = t_axis(sec)
    f = 30 + 90 * np.exp(-t * 6)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.005, 0.9)
    n = band(noise(sec), hi=400) * env(len(t), 0.002, 0.25) * 0.6
    return norm(s + n)


def hit_metal(sec=2.0, base=180):
    t = t_axis(sec)
    parts = [1, 2.76, 5.40, 8.93, 13.3]
    s = sum(np.sin(2 * np.pi * base * p * t + RNG.uniform(0, 6)) * np.exp(-t * (2 + p)) / p for p in parts)
    return norm(s * env(len(t), 0.002, 1.0))


def whoosh(sec=1.2):
    n = noise(sec)
    t = t_axis(sec)
    e = np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 2
    return norm(band(n, 300, 2500) * e)


def riser(sec=3.0):
    t = t_axis(sec)
    p = t / sec
    f = 80 + 600 * p ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4
    hiss = band(noise(sec), 1500, 9000) * p ** 2
    return norm((tone + hiss) * p ** 1.5)


def heartbeat(sec, bpm=62):
    out = np.zeros(int(sec * SR), np.float32)
    beat = 60 / bpm
    def thump(freq, s=0.25):
        tt = t_axis(s)
        return np.sin(2 * np.pi * freq * tt) * env(len(tt), 0.004, 0.06)
    a, b = thump(55), thump(48)
    t = 0.0
    while t < sec:
        for off, th, g in ((0, a, 1.0), (0.28, b, 0.7)):
            i = int((t + off) * SR)
            j = min(len(out), i + len(th))
            if i < len(out):
                out[i:j] += th[: j - i] * g
        t += beat
    return norm(out)


def screech(sec=1.6):
    """새/짐승 비슷한 비명. 고음 사인 글라이드 + 대역 잡음."""
    t = t_axis(sec)
    f = 1500 + 900 * np.sin(np.pi * t / sec) + 60 * np.sin(2 * np.pi * 23 * t)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR)
    s += 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.51) / SR)
    rough = 0.6 + 0.4 * np.sin(2 * np.pi * 37 * t)
    n = band(noise(sec), 1800, 5000) * 0.8
    e = np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 0.6
    return norm((s * rough + n) * e)


def typewriter(n_keys, gap=0.07):
    out = np.zeros(int((n_keys * gap + 0.2) * SR), np.float32)
    click = band(noise(0.03), 1500, 7000) * env(int(0.03 * SR), 0.0005, 0.008)
    for k in range(n_keys):
        i = int((k * gap + RNG.uniform(-0.01, 0.01) + 0.01) * SR)
        out[i:i + len(click)] += click * RNG.uniform(0.6, 1.0)
    return norm(out)


def splash(sec=2.5):
    t = t_axis(sec)
    n = band(noise(sec), 400, 6000) * env(len(t), 0.02, 0.7)
    return norm(n)


def collapse(sec=5.0):
    """다리 붕괴: 금속 파열음 + 긴 굉음 + 물보라."""
    out = np.zeros(int(sec * SR), np.float32)
    def put(x, at, g):
        i = int(at * SR)
        j = min(len(out), i + len(x))
        out[i:j] += x[: j - i] * g
    put(hit_metal(2.5, 140), 0.0, 0.9)
    put(hit_metal(2.0, 95), 0.35, 0.7)
    put(hit_metal(1.8, 210), 0.8, 0.5)
    rumble = band(noise(sec), 20, 300) * env(int(sec * SR), 0.3, 2.0)
    put(norm(rumble), 0.1, 0.9)
    put(boom(3.0), 1.3, 1.0)
    put(splash(3.0), 1.7, 0.6)
    return norm(out)


# ── 배경음 (어두운 앰비언트) ─────────────────────────

def drone(sec, root=55.0, seed=0, dark=1.0):
    """스테레오 (2, n). 낮은 음 + 바람 + 불협 고음."""
    r = np.random.default_rng(seed)
    t = t_axis(sec)
    n = len(t)
    L = np.zeros(n, np.float32)
    R = np.zeros(n, np.float32)
    for ratio, g in ((1, 1.0), (1.5, 0.45), (2, 0.35), (1.0067, 0.6), (2.996, 0.12)):
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * r.uniform(0.03, 0.09) * t + r.uniform(0, 6))
        ph = r.uniform(0, 6)
        L += g * lfo * np.sin(2 * np.pi * root * ratio * t + ph)
        R += g * lfo * np.sin(2 * np.pi * root * ratio * 1.002 * t + ph + 0.4)
    # 바람: 저역 잡음, 천천히 부풀었다 줄었다
    windL = band(noise(sec), 80, 900) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t) ** 2)
    windR = band(noise(sec), 80, 900) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t + 1) ** 2)
    L += windL * 0.5
    R += windR * 0.5
    # 불협 고음 (A5 + Bb5), 아주 작게
    hi = (np.sin(2 * np.pi * 880 * t) + np.sin(2 * np.pi * 932.3 * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t))
    L += hi * 0.025 * dark
    R += hi * 0.025 * dark
    m = max(np.abs(L).max(), np.abs(R).max())
    return np.stack([L, R]) / m


def pulse(sec, bpm=70, root=55.0):
    """긴장감 있는 낮은 맥박 (붕괴 장면 앞 같은 곳)."""
    out = np.zeros(int(sec * SR), np.float32)
    beat = 60 / bpm
    tt = t_axis(0.5)
    p = np.sin(2 * np.pi * root * tt) * env(len(tt), 0.01, 0.15)
    t = 0
    while t < sec:
        i = int(t * SR)
        j = min(len(out), i + len(p))
        out[i:j] += p[: j - i]
        t += beat
    return norm(out)


def static(sec=0.35):
    """글리치용 지직 소리."""
    n = noise(sec)
    t = t_axis(sec)
    gate = (np.sin(2 * np.pi * 31 * t) > -0.2).astype(np.float32)
    return norm(band(n, 800, 7000) * gate * env(len(t), 0.002, sec * 0.6))


def hit(sec=0.6):
    """강조 단어용 낮은 '쿵' (펀치 줌과 같이)."""
    t = t_axis(sec)
    f = 48 + 70 * np.exp(-t * 30)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.002, 0.16)
    click = band(noise(sec), 2000, 8000) * env(len(t), 0.0005, 0.006) * 0.35
    return norm(body + click)


# ── 임팩트 모음 ─────────────────────────────────────
# 같은 '쿵' 이 영상 내내 반복되면 귀가 금방 지친다. 성격이 다른 임팩트를 섞어 쓴다.
# (타자기 소리는 채널 고유 소리라 손대지 않는다)

def thud(sec=1.2, base=44):
    """마른 '툭' — 꼬리가 거의 없다. 증거·문서·사실을 못박을 때."""
    t = t_axis(sec)
    f = base * (1 + 0.9 * np.exp(-t * 22))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.003, 0.17)
    n = band(noise(sec), 60, 900) * env(len(t), 0.001, 0.045) * 0.5
    return norm(s + n)


def sub_drop(sec=3.2):
    """배를 누르는 저음 하강 — 추락·침몰·사망자 수 같은 무거운 사실."""
    t = t_axis(sec)
    f = 78 * np.exp(-t * 1.1) + 21
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.03, 1.5)
    return norm(s)


def stab(sec=1.8, root=116.0):
    """불협 현악 스탭 — 반전·폭로 순간."""
    t = t_axis(sec)
    s = sum(np.sin(2 * np.pi * root * r * t + RNG.uniform(0, 6)) * np.exp(-t * (1.3 + 0.45 * i))
            for i, r in enumerate((1.0, 1.06, 1.49, 2.01, 2.98)))
    s = s * (1 + 0.25 * np.sin(2 * np.pi * 5.5 * t))      # 활 떨림
    return norm(band(s, None, 3200) * env(len(t), 0.008, 0.85))


def knock(sec=0.9):
    """나무를 두드리는 소리 — 문·관·바닥, 가까이서 나는 소리."""
    t = t_axis(sec)
    s = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d)
            for f, d in ((210, 26), (380, 34), (720, 45), (1250, 60)))
    n = band(noise(sec), 400, 4000) * env(len(t), 0.0005, 0.012) * 0.5
    return norm(s * env(len(t), 0.001, 0.09) + n)


def rumble(sec=3.5):
    """땅울림 — 서서히 차올랐다 가라앉는다. 눈사태·붕괴 전조."""
    t = t_axis(sec)
    e = np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 1.6
    n = band(noise(sec), 18, 180) * e
    s = np.sin(2 * np.pi * 27 * t) * e * 0.5
    return norm(n + s)


def vary(x, seed, amount=1.0):
    """같은 효과음이 반복될 때 조금씩 다르게 (음높이·길이·음색을 살짝 바꾼다)."""
    r = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    ratio = float(np.exp(r.uniform(-0.13, 0.13) * amount))
    n = max(8, int(len(x) / ratio))
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    tilt = float(r.uniform(-0.35, 0.35)) * amount
    y = y + (band(y, 1200, None) * tilt if tilt > 0 else band(y, None, 300) * -tilt)
    return norm(y) * float(r.uniform(0.86, 1.0))


# ── 배경음 이어 붙이기 ──────────────────────────────

def drone_loop(sec, root=55.0, seed=0, seg=48.0, xf=4.0):
    """긴 영상용 배경음: seg 초짜리 드론을 크로스페이드로 이어 붙인다 (메모리 절약)."""
    if sec <= seg + xf:
        return drone(sec, root, seed)
    n = int(sec * SR)
    out = np.zeros((2, n), np.float32)
    L = int(seg * SR)
    X = int(xf * SR)
    fade_in = np.linspace(0, 1, X, dtype=np.float32)
    pos, k = 0, 0
    while pos < n:
        part = drone(seg + xf, root, seed + k).astype(np.float32)
        part[:, :X] *= fade_in if pos > 0 else 1
        part[:, -X:] *= fade_in[::-1]
        j = min(n, pos + part.shape[1])
        out[:, pos:j] += part[:, : j - pos]
        pos += L
        k += 1
    return out
