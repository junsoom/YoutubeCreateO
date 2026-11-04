"""스펙(JSON) → 타임라인(대사·자막·이벤트) → 프레임 렌더 + 소리 믹스 → mp4.

스펙 모양:
{
  "id": "mothman_short", "format": "short",
  "title": ["UMA FILE #001", "붉은 눈의 나방인간"],
  "beats": [
    {"scene": "road", "lines": ["...", "..."], "events": {"collapse": "무너졌고"},
     "sfx": [{"name": "screech", "at": 0.6, "gain": 0.4}, {"name": "boom", "at": "word:붉게"}],
     "stamp": ["POINT PLEASANT, W.VA.", "NOV. 15, 1966"], "pad": 0.4, "params": {...}}
  ]
}
"""
import json
import math
import os
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import config, fx, sound, tts
from .fonts import font
from .scenes import SCENES
from .photo import Chapter, Photo, PhotoEnd

SCENES = {**SCENES, "photo": Photo, "photo_end": PhotoEnd, "chapter": Chapter}

FF = tts.FFMPEG
SR = config.SR
LEAD, GAP, PAD, XF = 0.1, 0.06, 0.2, 0.25


# ── 타임라인 ───────────────────────────────────────────

def _norm(s):
    return "".join(ch for ch in s if ch.isalnum())


def _align(tokens, words, t0):
    """화면 토큰(띄어쓰기 단위) 마다 시작 시각을 TTS 단어 시각에서 찾는다."""
    disp = [_norm(tts.clean(tk)) for tk in tokens]
    spoken = [_norm(w["text"]) for w in words]
    D, S = sum(map(len, disp)), sum(map(len, spoken))
    starts = []
    pos = 0
    # 말한 글자 위치 → 시각
    marks = []
    acc = 0
    for w, s in zip(words, spoken):
        marks.append((acc, w["t0"], w["t1"], len(s)))
        acc += len(s)
    for d in disp:
        c = pos * S / max(D, 1)
        t = words[-1]["t1"] if words else 0
        for a, w0, w1, n in marks:
            if a <= c < a + max(n, 1):
                t = w0 + (w1 - w0) * (c - a) / max(n, 1)
                break
        starts.append(t0 + t)
        pos += len(d)
    return starts


def _chunks(tokens, max_chars=14):
    """자막 한 장에 들어갈 토큰 묶음 (최대 2줄 × max_chars 글자 정도). '|' 는 강제로 끊는다."""
    out, cur, n = [], [], 0
    for i, tk in enumerate(tokens):
        hard = tk.endswith("|")
        L = len(tts.clean(tk))
        if cur and n + L > max_chars * 2:
            out.append(cur)
            cur, n = [], 0
        cur.append(i)
        n += L + 1
        if hard:
            out.append(cur)
            cur, n = [], 0
    if cur:
        out.append(cur)
    return out


def build(spec):
    beats = []
    t = 0.0
    audio = []
    for bi, b in enumerate(spec["beats"]):
        lead = b.get("lead", 0.05 if bi == 0 else LEAD)
        cur = t + lead
        lines = []
        src = b.get("lines", [])
        if src and b.get("join", True):
            # 장면의 대사를 한 번에 녹음한다 → 문장 사이 억양·쉼이 사람처럼 이어진다 (2026-10-30)
            a, words = tts.say(" ".join(src), b.get("voice"), b.get("rate"), b.get("pitch"), b.get("deepen"))
            toks_all = " ".join(src).replace("|", "| ").split()
            starts_all = _align(toks_all, words, cur)
            end_all = cur + len(a) / SR
            k = 0
            for li, line in enumerate(src):
                toks = line.replace("|", "| ").split()
                st = starts_all[k:k + len(toks)]
                k += len(toks)
                t1 = (starts_all[k] - 0.08) if k < len(toks_all) else end_all
                lines.append(dict(text=line, tokens=toks, starts=st, t0=st[0], t1=t1))
            audio.append((cur, a))
            cur = end_all + GAP
        else:
            for line in src:
                a, words = tts.say(line, b.get("voice"), b.get("rate"), b.get("pitch"))
                toks = line.replace("|", "| ").split()
                starts = _align(toks, words, cur)
                end = cur + len(a) / SR
                lines.append(dict(text=line, tokens=toks, starts=starts, t0=cur, t1=end))
                audio.append((cur, a))
                cur = end + GAP
        dur = max(b.get("min", 0), cur - GAP + b.get("pad", PAD) - t) if lines else b.get("min", 2.5)
        beat = dict(i=bi, scene=b["scene"], t0=t, t1=t + dur, lines=lines, params=b.get("params", {}),
                    stamp=b.get("stamp"), sfx=b.get("sfx", []), seed=b.get("seed", bi * 11 + 3),
                    flash=b.get("flash", []), cut=b.get("cut", "fade"),
                    impact=b.get("impact", []))
        # 이벤트: "단어" → 장면 기준 시각
        ev = {}
        for name, key in b.get("events", {}).items():
            ev[name] = _find(beat, key) - t if isinstance(key, str) else key
        beat["ev"] = ev
        if "glitch" in beat["params"]:
            beat["params"] = {**beat["params"], "glitch_t": [_at(beat, g) - t for g in beat["params"]["glitch"]]}
        _auto_impacts(beat, bi, spec)
        beats.append(beat)
        t += dur
    return dict(beats=beats, total=t, audio=audio)


def _auto_impacts(beat, bi, spec):
    """임팩트(펀치 줌 + '쿵')는 스펙의 "impact" 에 적은 순간에만 넣는다.
    2026-10-30 사용자: 많으면 안 좋다, 가장 임팩트 있는 곳 3번 정도만."""
    hits = [_at(beat, x) for x in beat.get("impact", [])]
    beat["hits"] = hits
    explicit = []
    for s_ in beat["sfx"]:
        try:
            explicit.append(_at(beat, s_.get("at", 0)))
        except Exception:
            pass
    sfx = list(beat["sfx"])
    for h in hits:
        if all(abs(h - e) > 0.25 for e in explicit):
            sfx.append({"name": "hit", "at": h - beat["t0"], "gain": 0.4})
    if bi > 0 and beat["cut"] == "glitch":
        sfx.append({"name": "static", "at": 0.0, "gain": 0.16})
    beat["sfx"] = sfx


def _find(beat, key):
    """beat 안에서 key 글자를 포함한 첫 단어의 시작 시각(절대)."""
    for ln in beat["lines"]:
        for tk, st in zip(ln["tokens"], ln["starts"]):
            if key in tts.clean(tk):
                return st
    raise KeyError(f"단어 '{key}' 를 찾지 못했다 (장면 {beat['scene']})")


def _at(beat, at):
    if isinstance(at, str) and at.startswith("word:"):
        return _find(beat, at[5:])
    if isinstance(at, str) and at.startswith("ev:"):
        return beat["t0"] + beat["ev"][at[3:]]
    return beat["t0"] + float(at)


# ── 자막·제목 그리기 ─────────────────────────────────────

HL = (255, 214, 40)


def subtitle_img(tokens, W, size=80):
    """토큰 목록 → 가운데 정렬 자막 RGBA. [강조] 는 노란색."""
    f = font("title", size)
    d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    space = d0.textlength(" ", font=f)
    maxw = W * 0.84
    lines, cur, cw = [], [], 0
    hl = False
    items = []
    for tk in tokens:
        raw = tk.replace("|", "")
        segs = []
        buf = ""
        for ch in raw:
            if ch == "[":
                if buf:
                    segs.append((buf, hl))
                buf, hl = "", True
            elif ch == "]":
                if buf:
                    segs.append((buf, hl))
                buf, hl = "", False
            else:
                buf += ch
        if buf:
            segs.append((buf, hl))
        w = sum(d0.textlength(s, font=f) for s, _ in segs)
        items.append((segs, w))
    for segs, w in items:
        if cur and cw + space + w > maxw:
            lines.append((cur, cw))
            cur, cw = [], 0
        cw += (space if cur else 0) + w
        cur.append((segs, w))
    if cur:
        lines.append((cur, cw))
    lh = int(size * 1.25)
    img = Image.new("RGBA", (W, lh * len(lines) + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 10
    for row, rw in lines:
        x = (W - rw) / 2
        for segs, w in row:
            for s, h in segs:
                d.text((x, y), s, font=f, fill=HL if h else (255, 255, 255), stroke_width=max(4, size // 11), stroke_fill=(0, 0, 0))
                x += d.textlength(s, font=f)
            x += space
        y += lh
    # 그림자
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.7)))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 6))
    out.alpha_composite(img)
    return out


def title_img(lines, W):
    label, big = lines
    img = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f1 = font("gothic", 40)
    tw = d.textlength(label, font=f1)
    d.rectangle([(W - tw) / 2 - 18, 6, (W + tw) / 2 + 18, 64], fill=(190, 26, 22, 255))
    d.text(((W - tw) / 2, 12), label, font=f1, fill=(255, 255, 255))
    f2 = font("title", 92)
    tw = d.textlength(big, font=f2)
    if tw > W * 0.92:
        f2 = font("title", int(92 * W * 0.92 / tw))
        tw = d.textlength(big, font=f2)
    d.text(((W - tw) / 2, 88), big, font=f2, fill=(255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0))
    return img


def stamp_img(lines, n_chars):
    """타자기 위치 표시: 앞에서부터 n_chars 글자만."""
    img = Image.new("RGBA", (980, 70 * len(lines) + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    left = n_chars
    for i, ln in enumerate(lines):
        if left <= 0:
            break
        s = ln[:left]
        left -= len(ln)
        f = font("type", 50) if ln.isascii() else font("gothic", 44)
        if i == 0:
            d.ellipse([0, 22, 22, 44], fill=(230, 40, 30, 255))
        d.text((38, 10 + i * 66), s, font=f, fill=(240, 240, 235, 255), stroke_width=3, stroke_fill=(0, 0, 0, 200))
    return img


# ── 소리 ───────────────────────────────────────────────

SFX = {"boom": sound.boom, "whoosh": sound.whoosh, "riser": sound.riser, "screech": sound.screech,
       "collapse": sound.collapse, "splash": sound.splash, "metal": sound.hit_metal,
       "static": sound.static, "hit": sound.hit,
       # 임팩트 모음 (2026-10-30 사용자: 같은 '쿵' 이 반복돼 지겹다 → 성격이 다른 소리를 섞는다)
       "thud": sound.thud, "sub": sound.sub_drop, "stab": sound.stab,
       "knock": sound.knock, "rumble": sound.rumble}

# 같은 소리가 또 나올 때 조금씩 다르게 만든다. 타자기(채널 고유 소리)와 박자 소리는 그대로 둔다.
NO_VARY = {"typewriter", "heartbeat", "pulse"}


def _movavg(x, k):
    """이동 평균 (누적합, O(N)). np.convolve 는 긴 영상에서 너무 느리다."""
    k = max(1, int(k))
    c = np.cumsum(np.concatenate([np.zeros(1, np.float64), x.astype(np.float64)]))
    y = (c[k:] - c[:-k]) / k
    pad_l = (len(x) - len(y)) // 2
    return np.pad(y, (pad_l, len(x) - len(y) - pad_l), mode="edge").astype(np.float32)


def process_voice(v, room=True):
    """저음 보강 + 짧은 방 울림 + 부드러운 압축 + 아주 작은 방 소음 (실제 녹음 느낌)."""
    n = len(v)
    X = np.fft.rfft(v)
    f = np.fft.rfftfreq(n, 1 / SR)
    shelf = 1 + (config.VOICE_LOW_BOOST - 1) / (1 + (f / 180.0) ** 2)
    presence = 1 + 0.12 / (1 + ((f - 2800) / 900.0) ** 2)   # 발음 또렷하게
    air = 1 / (1 + (f / 10000.0) ** 4) * 0.3 + 0.7             # 쇳소리 같은 고음 살짝 깎기
    v = np.fft.irfft(X * shelf * presence * air, n).astype(np.float32)
    if config.VOICE_REVERB > 0:
        L = int(0.6 * SR)
        rng = np.random.default_rng(5)
        ir = rng.standard_normal(L).astype(np.float32) * np.exp(-np.arange(L) / SR / 0.12)
        ir = sound.band(ir, 250, 3000)
        ir[: int(0.012 * SR)] = 0
        ir /= np.sqrt(np.sum(ir ** 2))
        m = 1 << int(np.ceil(np.log2(n + L)))
        wet = np.fft.irfft(np.fft.rfft(v, m) * np.fft.rfft(ir, m), m)[:n].astype(np.float32)
        v = v + wet * config.VOICE_REVERB
    v = v / (np.abs(v).max() or 1)
    v = np.tanh(v * 1.3) / np.tanh(1.3)
    from . import voicefx
    v = voicefx.apply(v, getattr(config, "VOICE_FX", "none"))
    room = getattr(config, "VOICE_ROOM", 0) if room else 0
    if room:
        v = v + sound.band(np.random.default_rng(9).standard_normal(n).astype(np.float32), 100, 3000) * room
    return (v * 0.92).astype(np.float32)


def mix(tl, spec, path):
    total = tl["total"] + 0.3
    n = int(total * SR)
    voice = np.zeros(n, np.float32)
    for t0, a in tl["audio"]:
        a = process_voice(a, room=False)   # 장면 단위로 처리 → 긴 영상도 메모리 적게
        i = int(t0 * SR)
        j = min(n, i + len(a))
        voice[i:j] += a[: j - i]
    room = getattr(config, "VOICE_ROOM", 0)
    if room:
        rng = np.random.default_rng(9)
        for i in range(0, n, SR * 30):
            m = min(n, i + SR * 30)
            voice[i:m] += sound.band(rng.standard_normal(m - i).astype(np.float32), 100, 3000) * room
    music = sound.drone_loop(total, root=spec.get("root", 49.0), seed=1) * 0.30
    # 장면별 음악 세기 (예: 붕괴 직후 순간 정적)
    gain = np.ones(n, np.float32)
    for b in tl["beats"]:
        g = b["params"].get("music", 1.0)
        gain[int(b["t0"] * SR):int(b["t1"] * SR)] = g
    gain = _movavg(gain, SR // 2)
    # 말할 때 음악 줄이기 (사이드체인)
    envv = _movavg(np.abs(voice), SR // 10)
    duck = 1 - 0.45 * np.clip(envv * 12, 0, 1)
    music = music * gain * duck
    fxs = np.zeros(n, np.float32)
    seen = {}          # 소리마다 몇 번째인지 (두 번째부터 조금씩 다르게)
    for bi, b in enumerate(tl["beats"]):
        for si, s in enumerate(b["sfx"]):
            name = s["name"]
            if name == "heartbeat":
                x = sound.heartbeat(s.get("dur", b["t1"] - b["t0"]), s.get("bpm", 64))
            elif name == "typewriter":
                x = sound.typewriter(s.get("keys", 24))
            elif name == "pulse":
                x = sound.pulse(s.get("dur", b["t1"] - b["t0"]), s.get("bpm", 70))
            else:
                x = SFX[name]()
            k = seen[name] = seen.get(name, 0) + 1
            if name not in NO_VARY and k > 1:
                x = sound.vary(x, seed=bi * 131 + si * 17 + k, amount=s.get("vary", 1.0))
            t = _at(b, s.get("at", 0)) + s.get("offset", 0)
            if s.get("end_at") is not None:   # 이 시각에 끝나게 (riser 등)
                t = _at(b, s["end_at"]) - len(x) / SR
            i = max(0, int(t * SR))
            j = min(n, i + len(x))
            fxs[i:j] += x[: j - i] * s.get("gain", 0.5)
    L = voice + music[0] + fxs
    R = voice + music[1] + fxs
    st = np.stack([L, R], 1)
    st = np.tanh(st * 1.1) / np.tanh(1.1)
    rms = np.sqrt(np.mean(st ** 2))
    st = st * min(0.16 / max(rms, 1e-4), 0.98 / np.abs(st).max())
    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ── 프레임 ─────────────────────────────────────────────

class Composer:
    def __init__(self, tl, spec):
        self.tl, self.spec = tl, spec
        self.W, self.H = config.SHORT_SIZE if spec.get("format", "short") == "short" else config.LONG_SIZE
        self.scenes = {}
        self.grader = fx.Grader(self.W, self.H)
        self.title = title_img(spec["title"], self.W) if spec.get("title") else None
        wide = self.W > self.H
        # 자막 기본값: 쇼츠는 아래 72%·76px·한 줄 14자, 롱폼은 아래 82%·56px·한 줄 24자
        self.sub_size = spec.get("sub_size", 56 if wide else 76)
        self.sub_y = spec.get("sub_y", 0.82 if wide else 0.72)
        self.sub_chars = spec.get("sub_chars", 24 if wide else 14)
        self.sub_cache = {}
        # 자막 카드 목록: (시작, 끝, 토큰)
        self.cards = []
        for b in tl["beats"]:
            for ln in b["lines"]:
                ch = _chunks(ln["tokens"], self.sub_chars)
                for k, idx in enumerate(ch):
                    s = ln["starts"][idx[0]]
                    e = ln["starts"][ch[k + 1][0]] if k + 1 < len(ch) else ln["t1"] + 0.12
                    self.cards.append((s - 0.05, e, tuple(ln["tokens"][i] for i in idx)))

        self.hits = sorted(h for b in tl["beats"] for h in b.get("hits", []))

    def _impact(self, t):
        """지금 시각의 펀치 줌 배율과 흔들림."""
        z, sh = 1.0, 0.0
        for h in self.hits:
            dt = t - h
            if 0 <= dt < 0.45:
                k = min(1.0, dt / 0.04) * (1 - fx.ease(dt / 0.45))
                z = max(z, 1 + 0.055 * k)
                sh = max(sh, 7 * k)
        return z, sh

    def scene(self, i):
        if i not in self.scenes:
            b = self.tl["beats"][i]
            self.scenes[i] = SCENES[b["scene"]](self.W, self.H, b["t1"] - b["t0"], b["ev"], b["seed"], **b["params"])
        return self.scenes[i]

    def frame(self, t, fi):
        beats = self.tl["beats"]
        i = next((k for k, b in enumerate(beats) if b["t0"] <= t < b["t1"]), len(beats) - 1)
        b = beats[i]
        u = t - b["t0"]
        img = self.scene(i).frame(u)
        if i > 0 and u < XF and b["cut"] == "fade":
            pb = beats[i - 1]
            prev = self.scene(i - 1).frame(t - pb["t0"])
            img = Image.blend(prev, img, fx.ease(u / XF))
        # 임팩트: 글리치 컷 (장면 시작 0.15초) + 펀치 줌 (강조 단어)
        z, sh = self._impact(t)
        if i > 0 and b["cut"] == "glitch" and u < 0.25:
            z = max(z, 1 + 0.07 * (1 - fx.ease(u / 0.25)))
        if z > 1.0005 or sh > 0.5:
            img = fx.punch(img, z, sh * math.sin(t * 91), sh * math.cos(t * 77))
        if i > 0 and b["cut"] == "glitch" and u < 0.15:
            img = fx.glitch(img, int(t * 1000), 1.0 - u / 0.15 * 0.5)
        # 다 쓴 장면은 메모리에서 내린다 (8GB 맥)
        for k in [k for k in self.scenes if k < i - 1]:
            del self.scenes[k]
        flash = 0.0
        if i > 0 and b["cut"] == "glitch" and u < 0.12:
            flash = 0.18 * (1 - u / 0.12)
        for f in b["flash"]:
            ft = _at(b, f) - b["t0"]
            if 0 <= u - ft < 0.35:
                flash = max(flash, 0.85 * (1 - (u - ft) / 0.35))
        fade = 1.0
        if i == len(beats) - 1:
            fade = 1 - fx.ease((t - (b["t1"] - 0.4)) / 0.4)
        img = self.grader(img, fi, flash, fade)
        sc = self.scene(i)
        if hasattr(sc, "overlay") and fade > 0.5:
            img = sc.overlay(img, u)
        # 위치 표시
        if b["stamp"]:
            st0 = b["params"].get("stamp_at", 0.5)
            n = int(max(0, u - st0) / 0.06)
            if n > 0 and u < b["t1"] - b["t0"] - 0.2:
                s = stamp_img(b["stamp"], n)
                img.paste(s, (60, int(self.H * 0.205)), s)
        # 제목 띠 (끝 화면 제외). 롱폼은 앞부분에만 띄운다 — 9분 내내 떠 있으면 거슬린다.
        if self.title is not None and b["scene"] not in ("end", "photo_end"):
            hold = self.spec.get("title_hold", 11.0 if self.spec.get("format", "short") == "long" else 1e9)
            if t < hold:
                a = 1.0 if t < hold - 1.0 else max(0.0, (hold - t))
                if a >= 1.0:
                    img.paste(self.title, (0, int(self.H * 0.085)), self.title)
                else:
                    fade = self.title.copy()
                    fade.putalpha(fade.getchannel("A").point(lambda v: int(v * a)))
                    img.paste(fade, (0, int(self.H * 0.085)), fade)
        # 자막
        for s, e, toks in self.cards:
            if s <= t < e:
                if toks not in self.sub_cache:
                    self.sub_cache = {toks: subtitle_img(toks, self.W, self.sub_size)}
                sub = self.sub_cache[toks]
                y = int(self.H * self.sub_y)
                dt = t - s
                if dt < 0.12 and self.spec.get("sub_pop", False):   # 자막 팝: 살짝 크게 나타났다가 제자리로
                    k = 1 + 0.14 * (1 - fx.ease(dt / 0.12))
                    sp = sub.resize((int(sub.width * k), int(sub.height * k)), Image.BILINEAR)
                    img.paste(sp, (int((self.W - sp.width) / 2), int(y - (sp.height - sub.height) / 2)), sp)
                else:
                    img.paste(sub, (0, y), sub)
                break
        return img


def _render_range(args):
    tl_path, spec, a, b, out = args
    tl = json.loads(Path(tl_path).read_text())
    comp = Composer(tl, spec)
    fps = spec.get("fps", config.FPS)
    W, H = comp.W, comp.H
    p = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for fi in range(a, b):
        img = comp.frame(fi / fps, fi)
        p.stdin.write(img.tobytes())
    p.stdin.close()
    p.wait()
    return out


def render(spec, out_dir, workers=4, stills=None):
    from multiprocessing import Pool
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tl = build(spec)
    audio = tl.pop("audio")
    tl_path = out_dir / "timeline.json"
    tl_path.write_text(json.dumps(tl, ensure_ascii=False, indent=1))
    tl["audio"] = audio
    print(f"길이 {tl['total']:.1f}초, 장면 {len(tl['beats'])}개")
    for b in tl["beats"]:
        print(f"  {b['t0']:6.2f}~{b['t1']:6.2f}  {b['scene']:<10} ev={ {k: round(v, 2) for k, v in b['ev'].items()} }")
    if stills is not None:
        comp = Composer(json.loads(tl_path.read_text()), spec)
        paths = []
        for t in stills:
            img = comp.frame(t, int(t * spec.get("fps", config.FPS)))
            pth = out_dir / f"still_{t:05.1f}.jpg"
            img.save(pth, quality=90)
            paths.append(pth)
        return paths
    wav = out_dir / "mix.wav"
    mix(tl, spec, wav)
    fps = spec.get("fps", config.FPS)
    nfr = int(math.ceil(tl["total"] * fps))
    # 장면 경계에 맞춰 일감 나누기 (워커가 준비할 장면 수를 줄인다)
    bounds = [0]
    per = nfr / (workers * 2)
    for b in tl["beats"][1:]:
        f = int(b["t0"] * fps)
        if f - bounds[-1] >= per * 0.5:
            bounds.append(f)
    bounds.append(nfr)
    # 너무 긴 조각은 반으로
    final = [bounds[0]]
    for x in bounds[1:]:
        while x - final[-1] > per * 1.6:
            final.append(final[-1] + int(per))
        final.append(x)
    tmp = Path(tempfile.mkdtemp(prefix="render_", dir=out_dir))
    jobs = [(str(tl_path), spec, a, b, str(tmp / f"part_{k:03d}.mp4")) for k, (a, b) in enumerate(zip(final[:-1], final[1:]))]
    print(f"프레임 {nfr}, 조각 {len(jobs)}, 워커 {workers}")
    with Pool(workers) as pool:
        for k, _ in enumerate(pool.imap_unordered(_render_range, jobs)):
            print(f"  조각 {k + 1}/{len(jobs)} 완료", flush=True)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{j[4]}'\n" for j in jobs))
    out = out_dir / f"{spec['id']}.mp4"
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    # 출처 목록 (영상 설명란에 붙여 넣기)
    from .photo import credits
    used = []
    for b in tl["beats"]:
        k = b["params"].get("key")
        if k and k not in used:
            used.append(k)
    lines = ["사진 출처 (Wikimedia Commons)"]
    for k in used:
        c = credits().get(k)
        if c:
            lines.append(f"- {c['author']} / {c['license']} / {c['source']}")
    (out_dir / "사진출처.txt").write_text("\n".join(lines) + "\n")
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    return out
