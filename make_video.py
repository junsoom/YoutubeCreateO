"""쇼츠/롱폼 만들기.

./.venv/bin/python make_video.py episodes/001_mothman_short.json            # 렌더
./.venv/bin/python make_video.py episodes/001_mothman_short.json --stills 1 5 9   # 그 시각 정지 화면만
"""
import argparse
import json
import time
from pathlib import Path

from engine import render


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    out = Path(a.out or f"output/{spec['id']}")
    t = time.time()
    res = render.render(spec, out, workers=a.workers, stills=a.stills)
    print("결과:", res, f"({time.time() - t:.0f}초)")


if __name__ == "__main__":
    main()
