# 프로젝트: 성인 대상 미스터리 괴물(UMA·크립티드) 채널 자동 제작

어릴 때 보던 '세계의 미스터리 괴물' 감성을 어른용 공포 다큐 톤으로 만든다. 쇼츠로 사람을 모으고 롱폼으로 붙잡는다.
2026-10-29 시작. 첫 샘플은 모스맨 쇼츠 (episodes/001_mothman_short.json). 사용자 피드백으로 틀을 맞춰 가는 중이다.
사용자에게는 한국어로 답한다.

## 결정 기록
- 2026-10-29 사용자 피드백: 코드로 그린 그림은 '키즈 만화 같다' → **실제 사진 중심, 리얼하고 공포스러운 톤**으로 간다.
  사진마다 화면 오른쪽 아래에 출처(작가·라이선스)를 표기한다.
- 2026-10-30 채널명 **파일404** 확정 (engine/config.py). 괴물만이 아니라 미스터리 전반을 다룬다 (괴물은 소재가 한정적).
  영상 제목 띠는 "파일404 · #001 모스맨", 끝 화면은 글리치 "404 / FILE NOT FOUND" → 채널명 → 다음 파일 예고.
- 2026-10-30 더빙: 더 저음·덜 기계적으로. ko-KR-HyunsuMultilingualNeural, TTS pitch 는 -2Hz 만 내리고
  녹음본을 0.86 배속으로 재생해 음높이와 울림을 같이 낮춘다 (VOICE_DEEPEN). 장면 대사는 한 번에 녹음해 문장이 이어지게 한다.
  리버브는 아주 조금(0.07), 작은 방 소음을 깐다. 목소리 비교 샘플: make_voice_samples.py → output/voice_samples/.
- 2026-10-30 자막은 아래쪽 (세로 72%, 크기 76) — 사진을 가리지 않고, 쇼츠 하단 UI(약 85% 아래)에도 안 가린다.
- 2026-10-29 롱폼은 보류. 쇼츠 한 편으로 스타일을 먼저 맞춘다. 쇼츠는 60초 안팎, 첫 1초 안에 훅(붉은 눈 등).

## 사진 장면 (engine/photo.py, scene "photo" / "photo_end")
- 사진 받기: fetch_photos.py 의 PHOTOS 에 위키미디어 파일명을 넣고 실행. 원본 직접 받기는 429 로 막히니 표준 썸네일(960/1280/1920px) 주소로 받는다.
- params: key, mode(fill|fit), crop, focus, zoom, grade(cold|bw|sepia|color), exposure(흰 종이·낮 사진 0.55~0.6),
  eyes [[x,y,r]] (events.eyes 에 켜짐), label, counter, stamp_word(events.stamp), glitch ["word:..."], shake.
- 렌더하면 output/<id>/사진출처.txt 가 생긴다 → 영상 설명란에 그대로 붙인다 (CC BY/BY-SA 조건).
- 쇼츠 화면 오른쪽 아래 끝은 유튜브 버튼에 가려지므로 출처는 사진 바로 아래(세로 약 62%) 오른쪽에 둔다.
- 사진 내용은 직접 볼 수 없으니 정지 화면(--stills)을 밝기 통계·아스키로 확인하고, 사용자에게 눈으로 확인을 부탁한다.

## 절대 규칙
- 사진은 **재사용이 허락된 것만** 쓴다: 퍼블릭 도메인, CC0, CC BY, CC BY-SA (위키미디어 공용, Openverse, 미국 정부 기록물 등).
  출처 표기만으로 아무 사진이나 쓸 수 있는 게 아니다. 라이선스가 불분명하거나 NC(비상업)·ND(변경 금지)인 사진은 쓰지 않는다.
  받은 사진의 출처·라이선스·원본 주소는 assets/photos/credits.json 에 기록하고, 영상 설명란에도 모두 적는다.
- 효과음·배경음은 engine/sound.py 로 합성한다. 글꼴은 assets/fonts 의 OFL/Apache 무료 글꼴만.
- 사실과 전설을 구분한다. 확인된 사실(날짜, 사망자 수, 목격자 이름)은 출처로 확인하고,
  전설·주장은 "~라고 합니다", "~했다고 주장했죠" 처럼 말한다. 다시 만든 화면(신문 등)은 '재현'이다.
- 영상마다 대본·장면·연출이 달라야 한다 (유튜브 '진정성 없는 콘텐츠' 정책).
- 내레이션은 edge-tts 자동 녹음 (engine/tts.py, 목소리는 engine/config.py). 같은 문장은 cache/tts 에 저장돼 다시 받지 않는다.
- 업로드·계정·결제는 사용자가 직접 한다.
- 메모리 8GB 맥이다. 렌더 워커 4개. 렌더 코드는 .py 파일로 실행한다 (heredoc 으로 넘기면 multiprocessing 이 멈춘다).

## 명령
- 렌더: `./.venv/bin/python make_video.py episodes/<스펙>.json` → `output/<번호>_<id>/<번호>_<id>.mp4` (번호는 제목 띠 `#0NN`, engine/paths.py)
- 제작 규칙 전체: docs/제작규칙_초안.md (번호 = 주제 번호, 롱폼 20~25분 먼저 → 쇼츠 파생, 롱폼 주 1 + 쇼츠 주 3, 롱폼 띠 `· FULL FILE`)
- 정지 화면만: `... --stills 2 10 30` (초)
- 오래 걸리면 `caffeinate -i -s` 로 감싼다.
- 업로드 안내문: `make_upload_kit.py episodes/<스펙>.json` → `output/<id>/업로드_안내.md` (설명란 = `description()`)
- 예약 업로드: `upload.py list | auth | <번호…> --at "YYYY-MM-DD HH:MM" [--every 일] [--yes]`, 폰에서는 `bot.py` (텔레그램).
  설정은 docs/유튜브_자동업로드.md. `--yes`·[올리기] 버튼은 사용자만 누른다. 비밀은 `.secrets/`·`.env` (git 제외).

## 스펙 (episodes/*.json)
- `beats`: 장면 하나 = 대사 묶음 하나. `scene` 은 engine/scenes.py 의 SCENES 키.
- 대사 안의 `[단어]` 는 자막에서 노란색 강조, 읽을 때는 괄호를 뺀다. `|` 는 자막 강제 줄바꿈.
- `events`: {"이름": "단어"} → 그 단어가 들리는 순간에 장면 동작.
- `sfx`: name = boom whoosh riser screech collapse splash metal heartbeat typewriter pulse,
  `at` = 초 또는 "word:단어", `end_at` 은 그 시각에 끝나게.
- `stamp`: 타자기 위치 표시 줄들, `flash`: 하얀 번쩍임 시각, `params.music`: 장면 음악 세기.

## 구조
engine/config.py 채널명·목소리 / tts.py 자동 녹음 / sound.py 효과음 / art.py·creatures.py 그림(보조용) /
scenes.py 장면 / render.py 타임라인·자막·믹스·렌더 / fonts.py / assets/photos 사진과 credits.json
