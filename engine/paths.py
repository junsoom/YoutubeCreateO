"""출력 폴더 이름: output/<파일번호>_<id>/<파일번호>_<id>.mp4

파일번호는 화면 제목 띠("File404 · #002 네스호의 괴물 · FULL FILE")에서 읽는다.
같은 주제의 쇼츠·롱폼은 같은 번호라서 폴더가 나란히 정렬된다 (002_loch_ness_short, 002_nessie_long).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def file_no(spec):
    """제목 띠의 '#002' → '002'. 없으면 '000'."""
    m = re.search(r"#(\d{3})", (spec.get("title") or [""])[0])
    return m.group(1) if m else "000"


def out_name(spec):
    return f"{file_no(spec)}_{spec['id']}"


def out_dir(spec):
    """output/<번호>_<id> (프로젝트 루트 기준 절대 경로)."""
    return ROOT / "output" / out_name(spec)


def video_path(spec):
    return out_dir(spec) / f"{out_name(spec)}.mp4"
