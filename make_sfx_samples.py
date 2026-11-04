"""임팩트 소리 들어 보기: output/sfx_samples/임팩트_모음.wav
같은 소리를 세 번 반복해 '반복돼도 지겹지 않은지'도 같이 들어 본다.
"""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, "/Users/junhyunglee/Desktop/Ai/YoutubeCreateO")
from engine import sound  # noqa: E402

SR = sound.SR
ORDER = [("boom 쿵 (큰 것 한 번만)", sound.boom),
         ("thud 툭 (증거·사실)", sound.thud),
         ("sub 저음 하강 (무거운 사실)", sound.sub_drop),
         ("stab 현악 스탭 (반전)", sound.stab),
         ("knock 노크 (가까운 소리)", sound.knock),
         ("rumble 땅울림 (전조)", sound.rumble),
         ("metal 금속 (다리·쇠)", sound.hit_metal),
         ("typewriter 타자기 (채널 고유)", lambda: sound.typewriter(16))]

out = []
for name, fn in ORDER:
    print(name)
    for k in range(3):
        x = fn()
        if k and name.startswith(("thud", "stab", "knock", "sub")):
            x = sound.vary(x, seed=k * 37 + len(name))
        pad = np.zeros(int(SR * max(0.35, 1.3 - len(x) / SR)), np.float32)
        out.append(np.concatenate([x * 0.8, pad]))
    out.append(np.zeros(int(SR * 0.9), np.float32))

y = np.concatenate(out)
y = y / max(np.abs(y).max(), 1e-6) * 0.85
p = Path("/Users/junhyunglee/Desktop/Ai/YoutubeCreateO/output/sfx_samples")
p.mkdir(parents=True, exist_ok=True)
f = p / "임팩트_모음.wav"
with wave.open(str(f), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
print("완료:", f, f"{len(y)/SR:.1f}초")
