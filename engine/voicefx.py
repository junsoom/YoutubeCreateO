"""내레이터 목소리 효과 (괴물·귀신 같은 인위적인 목소리). 2026-10-30.

원래 목소리(dry)는 또렷하게 두고 그 위에 효과를 겹친다. 대사가 안 들리면 안 되기 때문.
  sub      한 옥타브 아래 목소리를 겹친다 → 거대한 괴물 같은 무게
  whisper  같은 말을 속삭임으로 겹친다 (위상 무작위화) → 귀신 같은 숨소리
  ring     목소리를 낮은 주파수로 떨리게 → 기계·악마 같은 거친 질감
  grit     살짝 찌그러뜨림
  verb     어두운 공간 울림 (초) 과 섞는 양
"""
import os
import subprocess
import tempfile
import wave

import numpy as np

from . import sound
from .config import SR
from .tts import FFMPEG

PRESETS = {
    "none":    dict(),
    # 괴물: 한 옥타브 아래 목소리가 깔린다
    "monster": dict(sub=0.45, grit=0.25, verb=(0.9, 0.12)),
    # 귀신: 속삭임이 겹치고 긴 울림
    "ghost":   dict(whisper=0.55, verb=(1.6, 0.22), flutter=0.004),
    # 악마: 아래 옥타브 + 떨림 + 찌그러짐
    "demon":   dict(sub=0.55, ring=0.30, grit=0.45, verb=(1.0, 0.14)),
    # 괴물+귀신: 아래 옥타브 조금 + 속삭임 조금 (가장 무난)
    "wraith":  dict(sub=0.30, whisper=0.35, grit=0.15, verb=(1.3, 0.16)),
}


def _ff(x, af):
    """ffmpeg 필터로 모노 float 신호 처리."""
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.wav"), os.path.join(d, "b.wav")
        pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
        with wave.open(a, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", a, "-af", af, "-ar", str(SR), "-ac", "1", b], check=True)
        with wave.open(b) as w:
            y = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    out = np.zeros_like(x)
    n = min(len(x), len(y))
    out[:n] = y[:n]
    return out


def octave_down(x):
    # 음높이만 한 옥타브 내리고 길이는 그대로
    return _ff(x, f"asetrate={SR // 2},aresample={SR},atempo=2.0")


def whisper(x, n_fft=1024, hop=256):
    """STFT 크기는 그대로, 위상만 무작위 → 같은 말을 속삭이는 소리."""
    rng = np.random.default_rng(3)
    win = np.hanning(n_fft).astype(np.float32)
    pad = np.concatenate([np.zeros(n_fft), x, np.zeros(n_fft)]).astype(np.float32)
    out = np.zeros_like(pad)
    norm = np.zeros_like(pad)
    for i in range(0, len(pad) - n_fft, hop):
        fr = pad[i:i + n_fft] * win
        mag = np.abs(np.fft.rfft(fr))
        ph = rng.uniform(0, 2 * np.pi, len(mag))
        y = np.fft.irfft(mag * np.exp(1j * ph), n_fft).astype(np.float32) * win
        out[i:i + n_fft] += y
        norm[i:i + n_fft] += win ** 2
    out = out / np.maximum(norm, 1e-3)
    out = out[n_fft:n_fft + len(x)]
    return sound.band(out, 900, 9000)


def reverb(x, decay, seed=11):
    L = int(decay * 2.2 * SR)
    rng = np.random.default_rng(seed)
    ir = rng.standard_normal(L).astype(np.float32) * np.exp(-np.arange(L) / SR / (decay / 3))
    ir = sound.band(ir, 150, 4000)
    ir[: int(0.03 * SR)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    n = len(x)
    m = 1 << int(np.ceil(np.log2(n + L)))
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:n].astype(np.float32)


def apply(v, preset):
    p = PRESETS.get(preset, {}) if isinstance(preset, str) else preset
    if not p:
        return v
    v = v / (np.abs(v).max() or 1)
    t = np.arange(len(v)) / SR
    out = v.copy()
    if p.get("flutter"):   # 아주 미세한 음높이 흔들림 (낡은 테이프)
        k = p["flutter"] * SR
        idx = np.arange(len(v)) + k * np.sin(2 * np.pi * 0.9 * t) + 0.5 * k * np.sin(2 * np.pi * 5.3 * t)
        out = np.interp(np.clip(idx, 0, len(v) - 1), np.arange(len(v)), v).astype(np.float32)
    if p.get("sub"):
        lo = octave_down(v)
        lo = sound.band(lo, 40, 1800)
        out = out + lo / (np.abs(lo).max() or 1) * p["sub"]
    if p.get("whisper"):
        w = whisper(v)
        out = out + w / (np.abs(w).max() or 1) * p["whisper"] * 0.6
    if p.get("ring"):
        out = out * (1 - p["ring"] + p["ring"] * np.sin(2 * np.pi * 38 * t)).astype(np.float32)
    if p.get("grit"):
        g = p["grit"]
        out = (1 - g) * out + g * np.tanh(out * 4) / np.tanh(4)
    if p.get("verb"):
        dec, mix = p["verb"]
        out = out + reverb(out, dec) * mix * 2.5
    return (out / (np.abs(out).max() or 1)).astype(np.float32)
