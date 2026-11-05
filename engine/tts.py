"""내레이션 자동 녹음 (edge-tts).

문장 하나 = 파일 하나. 결과는 cache/tts/ 에 문장 해시로 저장해서 같은 문장은 다시 받지 않는다.
단어별 시작·끝 시간(WordBoundary)도 같이 저장해서 자막 타이밍에 쓴다.
"""
import asyncio
import hashlib
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import edge_tts
import imageio_ffmpeg

from . import config

CACHE = Path(__file__).resolve().parent.parent / "cache" / "tts"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def clean(text):
    """화면 강조 표시 [ ] 와 줄바꿈 표시 | 를 지운 읽을 문장."""
    return text.replace("[", "").replace("]", "").replace("|", " ").replace("  ", " ").strip()


async def _fetch(text, voice, rate, pitch, mp3):
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"t0": ch["offset"] / 1e7, "t1": (ch["offset"] + ch["duration"]) / 1e7,
                              "text": ch["text"]})
    return words


def say(text, voice=None, rate=None, pitch=None, deepen=None):
    """문장을 녹음해 (모노 float32 numpy, 단어 타이밍 리스트) 를 돌려준다.

    deepen < 1 이면 녹음본을 그 비율로 느리게 재생해 음높이와 목소리 울림(포먼트)을 같이 낮춘다.
    TTS 의 pitch 를 크게 내리는 것보다 기계음이 덜하다 (2026-10-30).
    """
    deepen = deepen or getattr(config, "VOICE_DEEPEN", 1.0)
    voice = voice or config.VOICE
    rate = rate or config.VOICE_RATE
    pitch = pitch or config.VOICE_PITCH
    spoken = clean(text)
    key = hashlib.sha1(f"{voice}|{rate}|{pitch}|{spoken}".encode()).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    wav, meta = CACHE / f"{key}.wav", CACHE / f"{key}.json"
    if not (wav.exists() and meta.exists()):
        mp3 = CACHE / f"{key}.mp3"
        for attempt in range(3):
            try:
                words = asyncio.run(_fetch(spoken, voice, rate, pitch, mp3))
                break
            except Exception:
                if attempt == 2:
                    raise
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1",
                        "-ar", str(config.SR), str(wav)], check=True)
        mp3.unlink()
        meta.write_text(json.dumps({"text": spoken, "words": words}, ensure_ascii=False))
    if deepen != 1.0:
        deep = CACHE / f"{key}_d{deepen:.3f}.wav"
        if not deep.exists():
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(wav), "-af",
                            f"asetrate={int(config.SR * deepen)},aresample={config.SR}", str(deep)], check=True)
        src_wav = deep
    else:
        src_wav = wav
    with wave.open(str(src_wav)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    words = json.loads(meta.read_text())["words"]
    if deepen != 1.0:
        words = [{**w, "t0": w["t0"] / deepen, "t1": w["t1"] / deepen} for w in words]
    # 앞뒤 무음 정리: 첫 단어 0.05초 전부터, 끝 단어 0.25초 뒤까지
    if words:
        s0 = max(0, int((words[0]["t0"] - 0.05) * config.SR))
        s1 = min(len(a), int((words[-1]["t1"] + 0.15) * config.SR))
        a = a[s0:s1]
        off = s0 / config.SR
        words = [{**w, "t0": w["t0"] - off, "t1": w["t1"] - off} for w in words]
    max_gap = getattr(config, "VOICE_MAX_GAP", None)
    if max_gap and len(words) > 1:
        a, words = _squeeze_gaps(a, words, max_gap)
    return a, words


def _squeeze_gaps(a, words, max_gap, fade=0.015):
    """단어 사이 쉼(주로 문장 끝)이 max_gap 초보다 길면 가운데 무음을 잘라 max_gap 으로 줄인다.
    앞 단어 끝 쪽 55%, 다음 단어 앞 쪽 45%를 남기고, 이음매는 짧게 겹쳐(crossfade) 딸깍 소리를 막는다.
    2026-11-01 벤치마크: 목소리 빠르기는 경쟁 채널과 같고, 느리게 들리는 건 문장 끝 쉼(0.8초) 때문이었다."""
    sr = config.SR
    nf = int(fade * sr)
    out, cur, shift = [], 0, 0.0
    new_words = [dict(words[0])]
    for w0, w1 in zip(words[:-1], words[1:]):
        gap = w1["t0"] - w0["t1"]
        if gap > max_gap:
            cut0 = int((w0["t1"] + max_gap * 0.55) * sr)
            cut1 = int((w1["t0"] - max_gap * 0.45) * sr)
            if cut1 - cut0 > 2 * nf:
                seg = a[cur:cut0 + nf].copy()
                tail = a[cut1:cut1 + nf]
                ramp = np.linspace(0, 1, nf, dtype=np.float32)
                seg[-nf:] = seg[-nf:] * (1 - ramp) + tail * ramp
                out.append(seg)
                cur = cut1 + nf
                shift += (cut1 - cut0) / sr
        new_words.append({**w1, "t0": w1["t0"] - shift, "t1": w1["t1"] - shift})
    out.append(a[cur:])
    return np.concatenate(out), new_words
