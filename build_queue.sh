#!/bin/bash
# 밤샘 제작 큐: 사진 받기 → 스펙 검사 → 렌더 → 업로드 키트 → 인스타 키트
# 사용: bash build_queue.sh 008_gevaudan_short 009_thylacine_short ...
cd /Users/junhyunglee/Desktop/Ai/YoutubeCreateO || exit 1
PY=./.venv/bin/python

echo "=== $(date '+%H:%M:%S') 사진 받기 시작"
$PY fetch_photos.py > output/fetch_queue.log 2>&1
echo "=== $(date '+%H:%M:%S') 사진 받기 끝 ($(grep -c '받음' output/fetch_queue.log)장)"

for name in "$@"; do
  spec="episodes/${name}.json"
  id=$($PY -c "import json,sys;print(json.load(open(sys.argv[1]))['id'])" "$spec")
  echo "=== $(date '+%H:%M:%S') $id 검사"
  $PY - "$spec" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
c = json.load(open("assets/photos/credits.json"))
miss = [k for k in {b["params"]["key"] for b in s["beats"]} if k not in c]
bad = []
for i, b in enumerate(s["beats"]):
    refs = [x.get(k) for x in b.get("sfx", []) for k in ("at", "end_at")] + b.get("impact", []) + b.get("flash", []) + list(b.get("events", {}).values()) + b.get("params", {}).get("glitch", [])
    words = [str(r).split("word:")[1] for r in refs if isinstance(r, str) and r.startswith("word:")]
    t = " ".join(b.get("lines", [])).replace("[", "").replace("]", "")
    bad += [(i, w) for w in words if w not in t]
if miss:
    print("  !! 없는 사진:", miss)
if bad:
    print("  !! 없는 단어:", bad)
sys.exit(1 if (miss or bad) else 0)
PY
  if [ $? -ne 0 ]; then echo "=== $id 건너뜀 (검사 실패)"; continue; fi
  mkdir -p "output/$id"
  echo "=== $(date '+%H:%M:%S') $id 렌더"
  caffeinate -i -s $PY make_video.py "$spec" --workers 4 > "output/$id/render.log" 2>&1
  tail -1 "output/$id/render.log"
  $PY make_upload_kit.py "$spec" > /dev/null 2>&1
  $PY make_instagram_kit.py "$spec" > /dev/null 2>&1
  rm -rf "output/$id"/render_* 2>/dev/null || true
  echo "=== $(date '+%H:%M:%S') $id 완료"
done
echo "=== 큐 종료 $(date '+%H:%M:%S')"
