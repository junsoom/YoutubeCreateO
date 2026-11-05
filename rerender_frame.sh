#!/bin/bash
# 틀 통일 재렌더: 006 로지 → 004 디아틀로프 → 005 모스맨 롱폼
cd /Users/junhyunglee/Desktop/Ai/YoutubeCreateO || exit 1
for spec in episodes/006_rosie_short.json episodes/004_dyatlov_short.json episodes/005_mothman_long.json; do
  id=$(./.venv/bin/python -c "import json,sys;from engine import paths;print(paths.out_name(json.load(open(sys.argv[1]))))" "$spec")
  echo "=== $(date '+%H:%M:%S') $id 렌더 시작"
  caffeinate -i -s ./.venv/bin/python make_video.py "$spec" --workers 4 > "output/$id/render.log" 2>&1
  echo "=== $(date '+%H:%M:%S') $id 종료 코드 $?"
  tail -1 "output/$id/render.log"
  ./.venv/bin/python make_upload_kit.py "$spec" > /dev/null 2>&1
  rm -rf "output/$id"/render_*
done
echo "=== 전부 끝: $(date '+%H:%M:%S')"
