"""목소리 비교 샘플 → output/voice_samples/  (./.venv/bin/python make_voice_samples.py)"""
import sys
import wave

import numpy as np

from engine import config, render, tts

TEXT = "목격자가 사흘 뒤 직접 그린 그림입니다. 키 2미터, 등에는 거대한 날개, 그리고... 붉게 빛나는 두 눈."
B = dict(voice="ko-KR-InJoonNeural", rate="+12%", pitch="-2Hz", deepen=0.89)
C = dict(voice="ko-KR-InJoonNeural", rate="+16%", pitch="-2Hz", deepen=0.86)
LOW = dict(voice="ko-KR-InJoonNeural", rate="+22%", pitch="-2Hz", deepen=0.82)
VARS = {
    "1_인준C_효과없음": (C, "none"),
    "2_괴물_아래옥타브": (C, "monster"),
    "3_귀신_속삭임": (B, "ghost"),
    "4_악마_거친떨림": (LOW, "demon"),
    "5_괴물+귀신_추천": (C, "wraith"),
}


def main():
    for name, (kw, fxname) in VARS.items():
        a, _ = tts.say(TEXT, **kw)
        config.VOICE_FX = fxname
        v = render.process_voice(a)
        pcm = (np.clip(v, -1, 1) * 32767).astype(np.int16)
        with wave.open(f"output/voice_samples/{name}.wav", "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(config.SR)
            f.writeframes(pcm.tobytes())
        print(name, f"{len(a) / config.SR:.1f}초")


if __name__ == "__main__":
    main()
