"""텔레그램 봇: 폰에서 유튜브 예약 업로드. 설정은 docs/유튜브_자동업로드.md 의 '텔레그램 봇'.

  caffeinate -i -s ./.venv/bin/python bot.py      # 맥에서 켜 두기 (잠자기 방지)

명령 (내 채팅방 = .env 의 TELEGRAM_CHAT_ID 에서만 받는다):
  /list  (목록)                       올릴 수 있는 영상과 올린 기록
  /up 번호… 2026-11-06 19:00 [간격일]  (올리기)  미리보기 → [올리기] 버튼을 눌러야 실제로 올라간다
  /log   (기록)                       올린 기록
  /id                                 이 채팅방 번호 (처음 설정할 때)
업로드 자체는 upload.py 의 함수를 그대로 쓴다 (제목·설명·기록이 명령줄과 같다).
"""
import re
import secrets
import threading
import time
import traceback
from datetime import datetime, timedelta

import requests

import upload as up

TOKEN = up.env("TELEGRAM_TOKEN")
CHAT = str(up.env("TELEGRAM_CHAT_ID") or "").strip()
API = f"https://api.telegram.org/bot{TOKEN}/"
PENDING_TTL = 600                       # 미리보기 후 10분 안에 [올리기] 를 눌러야 한다
HELP = ("/list — 올릴 수 있는 영상 (목록)\n"
        "/up 번호… 2026-11-06 19:00 [간격일] — 미리보기 후 [올리기] 버튼 (올리기)\n"
        "   예: /up dyatlov_short rosie_short 2026-11-06 19:00 1\n"
        "   날짜를 빼면 비공개로만 올린다\n"
        "/log — 올린 기록 (기록)\n"
        "/id — 이 채팅방 번호")

pending = {}                            # 확인 대기: 키 → (계획, 만든 시각)
busy = threading.Lock()                 # 업로드는 한 번에 하나


# ---------------------------------------------------------------- 텔레그램

def tg(method, **params):
    r = requests.post(API + method, json=params, timeout=70)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"텔레그램 {method}: {data.get('description')}")
    return data["result"]


def send(chat, text, **kw):
    """4096자 제한 → 나눠 보낸다. 마지막 메시지를 돌려준다."""
    msg = None
    while text:
        cut = text if len(text) <= 4000 else text[:text.rfind("\n", 0, 4000) + 1 or 4000]
        text = text[len(cut):]
        msg = tg("sendMessage", chat_id=chat, text=cut, disable_web_page_preview=True,
                 **(kw if not text else {}))     # 버튼은 마지막 조각에만
    return msg


def edit(chat, msg_id, text):
    try:
        tg("editMessageText", chat_id=chat, message_id=msg_id, text=text[:4000], disable_web_page_preview=True)
    except RuntimeError as e:                    # 같은 글로 수정하면 거절된다 → 무시
        if "not modified" not in str(e):
            raise


# ---------------------------------------------------------------- 명령

CMD = {"list": "list", "목록": "list", "up": "up", "올리기": "up", "log": "log", "기록": "log",
       "id": "id", "help": "help", "start": "help", "도움말": "help"}


def parse_up(args):
    """'번호… [YYYY-MM-DD HH:MM] [간격일]' → (번호들, 시각, 간격)."""
    s = " ".join(args)
    m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})(?:\s+(\d+(?:\.\d+)?))?\s*$", s)
    when, every = None, 1.0
    if m:
        y, mo, d = m.group(1).split("-")
        when = up.parse_at(f"{int(y):04d}-{int(mo):02d}-{int(d):02d} {m.group(2).zfill(5)}")
        every = float(m.group(3)) if m.group(3) else 1.0
        s = s[:m.start()]
    return s.split(), when, every


def cmd_up(chat, args):
    ids, when, every = parse_up(args)
    if not ids:
        return send(chat, "번호를 적어 주세요. 예: /up dyatlov_short 2026-11-06 19:00")
    vids, log = up.videos(), up.load_log()
    bad = [i for i in ids if i not in vids]
    if bad:
        return send(chat, f"없는 번호이거나 렌더가 끝나지 않았습니다: {', '.join(bad)}  (/list)")
    if when and when < datetime.now(up.KST) + timedelta(minutes=30):
        return send(chat, "공개 시각은 지금부터 30분 뒤 이후로 주세요.")
    text, plan = up.make_plan(ids, when, every, vids, log)
    if not plan:
        return send(chat, text + "\n\n올릴 영상이 없습니다.")
    key = secrets.token_hex(4)
    pending[key] = (plan, time.time())
    send(chat, f"{text}\n\n{len(plan)}편을 올릴까요? (10분 안에)",
         reply_markup={"inline_keyboard": [[{"text": f"올리기 ({len(plan)}편)", "callback_data": f"go:{key}"},
                                            {"text": "취소", "callback_data": f"no:{key}"}]]})


def cmd_log(chat):
    log = up.load_log()
    if not log:
        return send(chat, "아직 올린 영상이 없습니다.")
    send(chat, "\n".join(f"{i}  {r['url']}\n  공개 {r['publish']} · 올림 {r['uploaded']}" for i, r in log.items()))


def on_message(msg):
    chat = str(msg["chat"]["id"])
    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return
    head, *args = text.split()
    name = CMD.get(head[1:].split("@")[0].lower())
    if name == "id":
        return send(chat, f"이 채팅방 번호: {chat}\n.env 에 TELEGRAM_CHAT_ID={chat} 를 넣고 봇을 다시 켜세요.")
    if chat != CHAT:                             # 내 채팅방이 아니면 아무 것도 하지 않는다
        return
    if name == "list":
        send(chat, "\n".join(up.list_lines(up.videos(), up.load_log())) or "렌더가 끝난 영상이 없습니다.")
    elif name == "up":
        cmd_up(chat, args)
    elif name == "log":
        cmd_log(chat)
    else:
        send(chat, HELP)


def on_button(cb):
    msg = cb.get("message") or {}
    chat = str(msg.get("chat", {}).get("id", ""))
    if chat != CHAT:
        return tg("answerCallbackQuery", callback_query_id=cb["id"])
    action, _, key = cb.get("data", "").partition(":")
    item = pending.pop(key, None)
    if not item or time.time() - item[1] > PENDING_TTL:
        tg("answerCallbackQuery", callback_query_id=cb["id"], text="만료됐습니다. /up 을 다시 보내 주세요.")
        return
    tg("editMessageReplyMarkup", chat_id=chat, message_id=msg["message_id"], reply_markup={"inline_keyboard": []})
    if action != "go":
        tg("answerCallbackQuery", callback_query_id=cb["id"], text="취소했습니다.")
        return send(chat, "취소했습니다.")
    if not busy.acquire(blocking=False):
        tg("answerCallbackQuery", callback_query_id=cb["id"], text="다른 업로드가 진행 중입니다.")
        return send(chat, "다른 업로드가 진행 중입니다. 끝난 뒤 /up 을 다시 보내 주세요.")
    tg("answerCallbackQuery", callback_query_id=cb["id"], text="올리기 시작")
    threading.Thread(target=run_upload, args=(chat, item[0]), daemon=True).start()


# ---------------------------------------------------------------- 업로드 (따로 도는 스레드)

def run_upload(chat, plan):
    try:
        yt = up.service()
        send(chat, f"채널: {up.channel_name(yt)}")
        vids = up.videos()
        for vid_id, m, at in plan:
            if vid_id in up.load_log():          # 그 사이 명령줄로 올렸으면 건너뛴다
                send(chat, f"{vid_id}: 이미 올림 → 건너뜀")
                continue
            msg_id = send(chat, f"올리는 중: {vid_id}  0%")["message_id"]
            last = [0]

            def progress(p, vid_id=vid_id, msg_id=msg_id):
                step = int(p * 10)
                if step > last[0]:
                    last[0] = step
                    edit(chat, msg_id, f"올리는 중: {vid_id}  {step * 10}%")

            video_id, note = up.upload(yt, vids[vid_id], m, at, progress=progress)
            up.record(vid_id, video_id, at, m["title"])
            when = f"{at:%Y-%m-%d %H:%M} 공개 예약" if at else "비공개"
            edit(chat, msg_id, f"✅ {vid_id}\nhttps://youtu.be/{video_id}\n{when}  {note}".rstrip())
        send(chat, "끝났습니다. /log")
    except (RuntimeError, up.QuotaError) as e:
        send(chat, f"❌ {e}")
    except Exception as e:                       # noqa: BLE001 — 봇은 꺼지지 않고 알려만 준다
        traceback.print_exc()
        send(chat, f"❌ 업로드 중 오류: {type(e).__name__}: {e}")
    finally:
        busy.release()


# ---------------------------------------------------------------- 돌리기

def main():
    if not TOKEN:
        raise SystemExit(".env 에 TELEGRAM_TOKEN 이 없습니다 (docs/유튜브_자동업로드.md 의 '텔레그램 봇').")
    me = tg("getMe")
    print(f"봇 @{me['username']} 켜짐. " + (f"채팅방 {CHAT} 의 명령만 받습니다." if CHAT
                                         else "TELEGRAM_CHAT_ID 가 없습니다 → 봇에 /id 를 보내 번호를 받으세요."))
    tg("setMyCommands", commands=[{"command": "list", "description": "올릴 수 있는 영상"},
                                  {"command": "up", "description": "번호 날짜 시각 → 예약 업로드"},
                                  {"command": "log", "description": "올린 기록"},
                                  {"command": "help", "description": "도움말"}])
    offset = None
    while True:
        try:
            updates = tg("getUpdates", timeout=50, offset=offset, allowed_updates=["message", "callback_query"])
        except (requests.RequestException, ValueError, RuntimeError) as e:
            print(f"연결 문제, 10초 뒤 다시: {e}")
            time.sleep(10)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            try:
                if "message" in u:
                    on_message(u["message"])
                elif "callback_query" in u:
                    on_button(u["callback_query"])
            except Exception:                    # noqa: BLE001 — 한 메시지 오류로 봇이 꺼지지 않게
                traceback.print_exc()
        for k in [k for k, (_, t) in pending.items() if time.time() - t > PENDING_TTL]:
            pending.pop(k, None)


if __name__ == "__main__":
    main()
