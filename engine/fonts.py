"""글꼴. assets/fonts 의 무료(OFL/Apache) 글꼴만 쓴다."""
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FILES = {
    "title": "BlackHanSans-Regular.ttf",       # 굵은 제목·자막
    "serif": "NanumMyeongjo-ExtraBold.ttf",    # 다큐 느낌 문구
    "gothic": "NanumGothic-ExtraBold.ttf",     # 작은 설명
    "type": "SpecialElite-Regular.ttf",        # 타자기(영문·숫자)
    "logo": "Anton-Regular.ttf",               # 채널 로고 File404 (영문)
    "mono": "SpaceMono-Bold.ttf",              # 코드·오류 화면 느낌 (영문)
}


@lru_cache(maxsize=128)
def font(kind, size):
    return ImageFont.truetype(str(ROOT / FILES[kind]), int(size))
