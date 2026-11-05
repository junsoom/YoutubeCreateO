"""유튜브 예약 업로드 (YouTube Data API v3). 설정은 docs/유튜브_자동업로드.md.

  ./.venv/bin/python upload.py auth                                 # 처음 한 번: 구글 로그인 → 연결된 채널 이름 확인
  ./.venv/bin/python upload.py list                                 # 올릴 수 있는 영상 번호와 올린 기록
  ./.venv/bin/python upload.py dyatlov_short --at "2026-11-06 19:00"        # 미리보기만 (안 올림)
  ./.venv/bin/python upload.py dyatlov_short --at "2026-11-06 19:00" --yes  # 올림 → 그 시각에 공개 예약

영상은 바로 올라가고 '비공개 + 예약'으로 걸린다. 공개는 유튜브가 그 시각에 한다 (맥이 꺼져 있어도 된다).
제목은 스펙 upload.titles 의 첫 번째(추천), 설명은 make_upload_kit.description() 과 같다 (업로드_안내.md 와 같은 문구).
올린 기록은 업로드_기록.json 에 남고, 같은 번호는 두 번 올리지 않는다. 텔레그램 봇(bot.py)도 이 파일의 함수를 쓴다.
"""
import argparse
import json
import os
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")   # 파이썬 3.9·LibreSSL 경고 (동작에는 문제없음)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from engine import paths  # noqa: E402
SECRETS = ROOT / ".secrets"
CLIENT = SECRETS / "client_secret.json"
TOKEN = SECRETS / "youtube_token.json"
LOG = ROOT / "업로드_기록.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
KST = timezone(timedelta(hours=9))
ENTERTAINMENT = "24"


def env(key, default=None):
    if key in os.environ:
        return os.environ[key]
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip("'\"")
    return default


# ---------------------------------------------------------------- 올릴 수 있는 영상

def videos():
    """렌더가 끝난 영상: 번호(스펙 id) → 스펙·파일. 렌더 중(2분 안에 바뀐 파일)인 것은 뺀다."""
    out = {}
    for f in sorted((ROOT / "episodes").glob("*.json")):
        try:
            spec = json.loads(f.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(spec, dict) or "upload" not in spec or "id" not in spec:
            continue
        folder = paths.out_dir(spec)
        mp4 = paths.video_path(spec)
        if not mp4.exists() or time.time() - mp4.stat().st_mtime < 120:
            continue
        out[spec["id"]] = dict(spec=spec, spec_file=f, video=mp4, folder=folder, long=spec.get("format") == "long")
    return out


def meta(v, title_index=0):
    """제목·설명·태그·썸네일. 업로드_안내.md 와 같은 문구."""
    os.chdir(ROOT)                                       # make_upload_kit 가 상대 경로(assets/…)를 쓴다
    from make_upload_kit import description
    up = v["spec"]["upload"]
    thumbs = sorted(v["folder"].glob("썸네일_*.jpg"))    # 업로드_안내.md 의 '만들어 둔 파일'과 같은 것
    thumb = v["folder"] / up["thumbnail"] if up.get("thumbnail") else (thumbs[0] if thumbs else None)
    return dict(title=up["titles"][title_index], description=description(v["spec"]), tags=up.get("tags", []),
                synthetic=bool(up.get("synthetic")), pinned=up.get("pinned", ""),
                thumb=thumb if v["long"] else None)       # 쇼츠는 API 썸네일이 적용되지 않는다 (앱에서 장면 고르기)


def check(m):
    """유튜브가 거절하는 것을 올리기 전에 막는다."""
    errs = []
    if not m["title"].strip() or len(m["title"]) > 100:
        errs.append(f"제목은 1~100자 ({len(m['title'])}자)")
    if any(c in m["title"] + m["description"] for c in "<>"):
        errs.append("제목·설명에 < > 를 쓸 수 없다")
    if len(m["description"]) > 5000:
        errs.append(f"설명이 5000자를 넘는다 ({len(m['description'])}자)")
    tag_len = sum(len(t) + (2 if " " in t else 0) for t in m["tags"]) + max(len(m["tags"]) - 1, 0)
    if tag_len > 500 or any("," in t for t in m["tags"]):
        errs.append(f"태그가 500자를 넘거나 태그 안에 쉼표가 있다 ({tag_len}자)")
    return errs


def body(m, publish_at):
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "embeddable": True,
              "license": "youtube", "containsSyntheticMedia": m["synthetic"]}
    if publish_at:
        status["publishAt"] = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"snippet": {"title": m["title"], "description": m["description"], "tags": m["tags"],
                        "categoryId": ENTERTAINMENT, "defaultLanguage": "ko", "defaultAudioLanguage": "ko"},
            "status": status}


# ---------------------------------------------------------------- 기록

def load_log():
    return json.loads(LOG.read_text()) if LOG.exists() else {}


def record(vid_id, video_id, publish_at, title):
    log = load_log()
    log[vid_id] = dict(video=video_id, url=f"https://youtu.be/{video_id}", title=title,
                       uploaded=f"{datetime.now(KST):%Y-%m-%d %H:%M}",
                       publish=f"{publish_at:%Y-%m-%d %H:%M}" if publish_at else "비공개")
    tmp = LOG.with_suffix(".tmp")
    tmp.write_text(json.dumps(log, ensure_ascii=False, indent=1))
    tmp.replace(LOG)


# ---------------------------------------------------------------- 유튜브

def credentials(login=False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and not creds.has_scopes(SCOPES):
        creds = None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:                                # noqa: BLE001 — 만료·취소되면 다시 로그인
            creds = None
    if not creds or not creds.valid:
        if not login:
            raise RuntimeError("유튜브 연결이 없거나 만료됐습니다. 맥에서 `./.venv/bin/python upload.py auth` 를 실행하세요.")
        if not CLIENT.exists():
            raise RuntimeError(f"{CLIENT} 가 없습니다. docs/유튜브_자동업로드.md 의 1~4단계를 먼저 해 주세요.")
        creds = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES).run_local_server(port=0)
    SECRETS.mkdir(exist_ok=True)
    TOKEN.write_text(creds.to_json())
    TOKEN.chmod(0o600)
    return creds


def service(login=False):
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=credentials(login), cache_discovery=False)


def channel_name(yt):
    r = yt.channels().list(part="snippet", mine=True).execute()
    return ", ".join(c["snippet"]["title"] for c in r.get("items", [])) or "(채널 없음)"


class QuotaError(RuntimeError):
    pass


def upload(yt, v, m, publish_at, progress=None):
    """올리고 (video_id, 썸네일 메모) 를 돌려준다. progress(0~1) 는 진행률을 받는 함수."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(v["video"]), mimetype="video/mp4", chunksize=16 * 1024 * 1024, resumable=True)
    b = body(m, publish_at)
    req = yt.videos().insert(part=",".join(b), body=b, media_body=media)
    resp, tries = None, 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            tries = 0
            if status and progress:
                progress(status.progress())
        except HttpError as e:
            if "quotaExceeded" in str(e) or "uploadLimitExceeded" in str(e):
                raise QuotaError("오늘 유튜브 업로드 한도에 걸렸습니다. 내일 다시 하면 됩니다.") from e
            if e.resp.status in (500, 502, 503, 504) and tries < 8:
                tries += 1
                time.sleep(2 ** tries)
                continue
            raise
        except (OSError, TimeoutError):                   # 인터넷이 잠깐 끊김 → 이어서 올린다
            if tries >= 8:
                raise
            tries += 1
            time.sleep(2 ** tries)
    vid = resp["id"]
    note = ""
    if m["thumb"] and m["thumb"].exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(m["thumb"]), mimetype="image/jpeg")).execute()
            note = f"썸네일 {m['thumb'].name}"
        except HttpError as e:
            note = f"썸네일 실패({e.resp.status}) → Studio 에서 직접: {m['thumb'].name} (채널 전화번호 인증이 필요할 수 있음)"
    return vid, note


# ---------------------------------------------------------------- 명령

def parse_at(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=KST)


NOT_AUDITED = "⚠️  유튜브 API 심사 전입니다. 지금 올리면 영상이 '비공개'로 잠겨서 예약 공개가 되지 않습니다 (docs/유튜브_자동업로드.md)."


def make_plan(ids, when, every, vids, log):
    """미리보기 글과 실제로 올릴 목록 [(번호, meta, 공개 시각)]. 이미 올린 것·확인 실패는 뺀다. 봇도 쓴다."""
    lines, plan = [], []
    for k, vid_id in enumerate(ids):
        at = when + timedelta(days=every * k) if when else None
        m = meta(vids[vid_id])
        errs = check(m)
        flag = "이미 올림 → 건너뜀" if vid_id in log else ("; ".join(errs) if errs else "OK")
        lines.append(f"{vid_id}\n  {vids[vid_id]['video']}\n  공개: {f'{at:%Y-%m-%d %H:%M} KST' if at else '비공개'}"
                     f" · 아동용 아님 · 합성 콘텐츠 {'예' if m['synthetic'] else '아니요'}\n  제목: {m['title']}\n  확인: {flag}")
        if vid_id not in log and not errs:
            plan.append((vid_id, m, at))
    if env("YT_AUDITED") != "1":
        lines.append("\n" + NOT_AUDITED)
    return "\n".join(lines), plan


def list_lines(vids, log):
    return [f"{'✅ ' + log[i]['url'] + ' (' + log[i]['publish'] + ')' if i in log else '⬜'}  {i:22s} "
            f"{'롱폼' if v['long'] else '쇼츠'}  {v['spec']['upload']['titles'][0][:50]}" for i, v in vids.items()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+", help="auth | list | 영상 번호(들)")
    ap.add_argument("--at", help='공개 예약 (한국 시간) "2026-11-06 19:00". 없으면 비공개로만 올린다')
    ap.add_argument("--every", type=float, default=1, help="여러 편일 때 간격 (일)")
    ap.add_argument("--yes", action="store_true", help="실제로 올린다 (없으면 미리보기만)")
    a = ap.parse_args()

    if a.ids == ["auth"]:
        print(f"연결된 채널: {channel_name(service(login=True))}")
        print("채널이 맞지 않으면 .secrets/youtube_token.json 을 지우고 다시 auth 하면서 File404 채널을 고르세요.")
        return

    vids, log = videos(), load_log()
    if a.ids == ["list"]:
        print("\n".join(list_lines(vids, log)))
        return

    bad = [i for i in a.ids if i not in vids]
    if bad:
        sys.exit(f"없는 번호이거나 렌더가 끝나지 않았습니다: {', '.join(bad)}  (upload.py list)")
    when = parse_at(a.at) if a.at else None
    if when and when < datetime.now(KST) + timedelta(minutes=30):
        sys.exit("--at 은 지금부터 30분 뒤 이후로 주세요.")

    text, plan = make_plan(a.ids, when, a.every, vids, log)
    print(text)
    if not a.yes:
        print(f"\n미리보기만 했습니다. 올리려면 같은 명령 끝에 --yes 를 붙이세요. ({len(plan)}편)")
        return

    try:
        yt = service()
        print(f"\n채널: {channel_name(yt)}")
        for vid_id, m, at in plan:
            print(f"올리는 중: {vid_id}")
            video_id, note = upload(yt, vids[vid_id], m, at,
                                    progress=lambda p: print(f"\r  {p * 100:5.1f}%", end="", flush=True))
            record(vid_id, video_id, at, m["title"])
            print(f"\r  → https://youtu.be/{video_id}  {note}")
    except (RuntimeError, QuotaError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
