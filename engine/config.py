"""채널 설정. 채널명이 정해지면 여기만 바꾸면 모든 영상에 반영된다."""

CHANNEL_NAME = "File404"      # 2026-10-30 사용자 결정 (영문 표기). 미스터리 전반을 다루는 채널
CHANNEL_HANDLE = ""     # 미정 (예: @file404_kr). 유튜브에서 사용 가능 여부 확인 필요

# 내레이터 목소리 (edge-tts). 2026-10-30 사용자 피드백: 더 저음, 덜 기계적, 문장 연결 매끄럽게.
# TTS 음높이는 거의 그대로 두고 (크게 내리면 기계음), 녹음본을 VOICE_DEEPEN 비율로 느리게 재생해 낮춘다.
VOICE = "ko-KR-InJoonNeural"   # 2026-10-30 사용자: 인준 B·C 가 좋다
VOICE_RATE = "+46%"        # 2026-11-01 사용자: 6% 더 빠르게 (예전 +38%). deepen 0.86 과 합쳐 실제 속도 약 1.26배
VOICE_MAX_GAP = 0.45       # 2026-11-01 문장 끝 쉼 상한(초). 예전엔 TTS 그대로 약 0.8초 (engine/tts._squeeze_gaps)
VOICE_PITCH = "-2Hz"
VOICE_DEEPEN = 0.86        # 1.0 = 원래 목소리. 낮을수록 굵고 느리다 (0.86~0.92 권장)
VOICE_LOW_BOOST = 1.35     # 180Hz 아래 배율
VOICE_REVERB = 0.07        # 울림 섞는 양 (많으면 안내 방송처럼 들린다)
VOICE_ROOM = 0.0025        # 아주 작은 방 소음 (실제 녹음 느낌)
# 괴물·귀신 같은 인위적인 목소리 효과 (engine/voicefx.py): none | monster | ghost | demon | wraith
VOICE_FX = "none"   # 2026-10-30 사용자: 1번(효과 없음) 선택

FPS = 30
SHORT_SIZE = (1080, 1920)
LONG_SIZE = (1920, 1080)
SR = 44100

# 화면 속 사진 출처 표시 (2026-10-30 사용자: 화면은 깔끔하게. 출처가 꼭 필요한 CC BY·BY-SA 는 설명란에 적는다)
SHOW_CREDIT = False
