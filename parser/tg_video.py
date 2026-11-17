"""Видео и кружки из постов Telegram. Два шага, их можно запускать отдельно.

1. Скачка (сырой слой). Каждый ролик сохраняется целиком и больше не трогается:
   <ARCHIVE_DIR>/data/_tg/<канал>/videos/<id поста>.mp4  (рядом с фото канала)
   Лёгкие видео и кружки: прямая ссылка со страницы t.me/s (поле video_url в posts.json).
   Ссылка живёт недолго, поэтому скачка идёт сразу после tg_download.py (в run_daily.sh).
   Тяжёлые видео (ссылки нет, только обложка): через аккаунт Telegram (Telethon).
   Для этого один раз нужен вход: TG_API_ID и TG_API_HASH в .env и python tg_login.py.
   Нет входа: тяжёлые ждут, лёгкие качаются как обычно.

2. Раскадровка. Из скачанного ролика: FRAMES кадров равномерно по ролику (jpg до 1280 px) и звук
   (продавцы часто говорят цену голосом):
   <ARCHIVE_DIR>/videos/<канал>/tg-<канал>-<id>/frame_01.jpg ..., audio.m4a, meta.json
   Сам ролик остаётся в сыром слое, поэтому раскадровку можно переделать: --redo.

Если Диск не подключён, всё пишется в parser/data/_tg/<канал>/...

  python tg_video.py                         оба шага, посты за FRESH_DAYS дней
  python tg_video.py --only download         только скачать
  python tg_video.py --only cut              только раскадровка уже скачанного
  python tg_video.py --only download --light-only   только лёгкие, пока ссылки свежие (в run_daily.sh)
  python tg_video.py aslauto                 один канал
  python tg_video.py --days 90 --heavy-limit 1000   догнать старые видео (разово, вручную)
  python tg_video.py --only cut --redo       переделать раскадровку всех скачанных

Нужен ffmpeg: системный (brew install ffmpeg) или imageio-ffmpeg из requirements.txt.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from accounts import DATA_DIR

TG_DIR = DATA_DIR / "_tg"
FRESH_DAYS = 14
FRAMES = 8
MAX_SECONDS = 180  # раскадровка только по первым трём минутам
MAX_MB = 400  # больше не качаем: это уже не обзор машины, а фильм
HEAVY_LIMIT = 150  # тяжёлых за обычный ежедневный прогон, чтобы Telegram не начал притормаживать аккаунт
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def find_ffmpeg() -> str | None:
    for candidate in (shutil.which("ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if candidate and Path(candidate).exists():
            return candidate
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


def archive_root() -> Path | None:
    try:
        from archive import archive_dir_from_env
        return archive_dir_from_env()
    except Exception:  # noqa: BLE001  нет dotenv или .env: просто пишем локально
        return None


class Places:
    """Где лежат сырые ролики и раскадровка: на Диске, а без Диска локально."""

    def __init__(self) -> None:
        archive = archive_root()
        self.raw_root = archive / "data" / "_tg" if archive else TG_DIR
        self.cut_root = archive / "videos" if archive else None

    def raw(self, channel: str, post_id) -> Path:
        return self.raw_root / channel / "videos" / f"{post_id}.mp4"

    def cut(self, channel: str, post_id) -> Path:
        name = f"tg-{channel}-{post_id}"
        if self.cut_root:
            return self.cut_root / channel / name
        return TG_DIR / channel / "videos" / name


def video_posts(channel: str, days: int) -> list[dict]:
    """Видеопосты канала за days дней: и лёгкие (есть video_url), и тяжёлые (есть только обложка)."""
    posts = json.loads((TG_DIR / channel / "posts.json").read_text(encoding="utf-8"))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [post for post in posts.values()
            if (post.get("video_url") or post.get("video_thumbs"))
            and not post.get("removed_at") and (post.get("date") or "") >= since]


class Telegram:
    """Подключение к аккаунту открываем, только когда дошли до первого тяжёлого видео."""

    def __init__(self) -> None:
        self.client = None
        self.tried = False

    def get(self):
        if not self.tried:
            self.tried = True
            from tg_client import connected_client
            self.client = connected_client()
        return self.client

    def close(self) -> None:
        if self.client:
            self.client.disconnect()


def download_light(post: dict, target: Path) -> bool:
    response = requests.get(post["video_url"], headers=HEADERS, timeout=180)
    if response.status_code != 200 or not response.content:
        return False
    target.write_bytes(response.content)
    return True


def download_heavy(client, channel: str, post: dict, target: Path) -> str | None:
    """Качает ролик через аккаунт. None, если вышло, иначе причина."""
    message = client.get_messages(channel, ids=int(post["id"]))
    if not message or not (message.video or message.video_note or message.gif):
        return "в сообщении нет видео"
    size_mb = (message.file.size or 0) / 1024 / 1024
    if size_mb > MAX_MB:
        return f"слишком большое ({size_mb:.0f} МБ)"
    message.download_media(file=str(target))
    return None if target.exists() and target.stat().st_size else "не скачалось через аккаунт"


def download(channel: str, post: dict, places: Places, telegram: Telegram, heavy_ok: bool) -> str:
    """Шаг 1: ролик целиком в сырой слой."""
    target = places.raw(channel, post["id"])
    if target.exists() and target.stat().st_size:
        return "уже"
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(".part")  # недокачанный файл не должен выглядеть готовым
    part.unlink(missing_ok=True)
    source = "page"
    # Ссылка со страницы могла протухнуть: тогда тоже идём через аккаунт
    if not (post.get("video_url") and download_light(post, part)):
        if not heavy_ok:
            return "тяжёлое, лимит"
        client = telegram.get()
        if client is None:
            return "тяжёлое, нет входа"
        problem = download_heavy(client, channel, post, part)
        if problem:
            part.unlink(missing_ok=True)
            return problem
        source = "account"
    part.rename(target)
    return f"скачано {target.stat().st_size / 1024 / 1024:.1f} МБ ({'страница' if source == 'page' else 'аккаунт'})"


def run(ffmpeg: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True)


def cut(ffmpeg: str, channel: str, post: dict, places: Places, redo: bool) -> str:
    """Шаг 2: кадры и звук из уже скачанного ролика."""
    video = places.raw(channel, post["id"])
    folder = places.cut(channel, post["id"])
    if not video.exists():
        return "нет ролика"
    if (folder / "meta.json").exists() and not redo:
        return "уже"
    with tempfile.TemporaryDirectory() as tmp:
        result = run(ffmpeg, "-i", str(video), "-t", str(MAX_SECONDS),
                     "-vf", "fps=1,scale='min(1280,iw)':-2", "-q:v", "3", str(Path(tmp) / "f_%03d.jpg"))
        frames = sorted(Path(tmp).glob("f_*.jpg"))
        if not frames:
            raise RuntimeError(f"ffmpeg не дал кадров: {result.stderr[:200]}")
        if len(frames) > FRAMES:
            step = len(frames) / FRAMES
            frames = [frames[int(step * i + step / 2)] for i in range(FRAMES)]
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        for number, frame in enumerate(frames, 1):
            shutil.copyfile(frame, folder / f"frame_{number:02d}.jpg")
    audio = folder / "audio.m4a"
    has_audio = run(ffmpeg, "-i", str(video), "-vn", "-acodec", "copy", str(audio)).returncode == 0 and audio.exists()
    if not has_audio and audio.exists():
        audio.unlink()
    meta = {"post": post["id"], "channel": channel, "date": post.get("date"), "video": str(video.name),
            "mb": round(video.stat().st_size / 1024 / 1024, 1), "durations": post.get("video_durations"),
            "processed": datetime.now().isoformat(timespec="seconds"), "frames": len(frames), "audio": has_audio}
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"кадров {len(frames)}, звук {'есть' if has_audio else 'нет'}"


def download_step(channels: list[str], places: Places, args) -> None:
    done = failed = skipped = waiting = heavy = megabytes = 0
    telegram = Telegram()
    try:
        for channel in channels:
            for post in video_posts(channel, args.days):
                if done + failed >= args.limit:
                    break
                is_heavy = not post.get("video_url")
                if args.light_only and is_heavy:
                    continue  # тяжёлые качает отдельный видеопрогон (run_video.sh)
                heavy_ok = not args.light_only and heavy < args.heavy_limit
                try:
                    status = download(channel, post, places, telegram, heavy_ok)
                except Exception as error:  # noqa: BLE001  один ролик не должен ронять весь прогон
                    status = f"ошибка {type(error).__name__}: {str(error)[:120]}"
                if status == "уже":
                    skipped += 1
                    continue
                if status.startswith("тяжёлое"):
                    waiting += 1  # не ошибка: догонится, когда будет вход или в следующий прогон
                    continue
                if "аккаунт" in status:
                    heavy += 1  # через аккаунт, в том числе лёгкие с протухшей ссылкой: всё идёт в лимит
                print(f"  {channel} {post['id']}: {status}")
                if status.startswith("скачано"):
                    done += 1
                    megabytes += places.raw(channel, post["id"]).stat().st_size / 1024 / 1024
                else:
                    failed += 1
                time.sleep(random.uniform(1.0, 2.5) if is_heavy else random.uniform(0.5, 1.5))
    finally:
        telegram.close()
    print(f"Видео, скачка: новых {done} ({megabytes:.0f} МБ, через аккаунт {heavy}), не вышло {failed}, "
          f"уже были {skipped}, тяжёлых ждут {waiting}. Папка: {places.raw_root}/<канал>/videos")


def cut_step(channels: list[str], places: Places, args) -> None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("Видео, раскадровка: нет ffmpeg. Поставьте: .venv/bin/pip install -r requirements.txt")
        return
    done = failed = skipped = 0
    for channel in channels:
        for post in video_posts(channel, args.days):
            try:
                status = cut(ffmpeg, channel, post, places, args.redo)
            except Exception as error:  # noqa: BLE001
                status = f"ошибка {type(error).__name__}: {str(error)[:120]}"
            if status in ("уже", "нет ролика"):
                skipped += 1
                continue
            if status.startswith("кадров"):
                done += 1
            else:
                failed += 1
                print(f"  {channel} {post['id']}: {status}")
    print(f"Видео, раскадровка: сделано {done}, не вышло {failed}, пропущено {skipped}. "
          f"Папка: {places.cut_root or TG_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("channels", nargs="*")
    parser.add_argument("--only", choices=["download", "cut"], help="только один шаг")
    parser.add_argument("--limit", type=int, default=2000, help="роликов за запуск (скачка)")
    parser.add_argument("--days", type=int, default=FRESH_DAYS, help="за сколько дней брать посты")
    parser.add_argument("--heavy-limit", type=int, default=HEAVY_LIMIT, help="тяжёлых видео за запуск")
    parser.add_argument("--light-only", action="store_true",
                        help="только лёгкие видео по свежей ссылке со страницы, без аккаунта (сразу после tg_download.py)")
    parser.add_argument("--redo", action="store_true", help="переделать раскадровку, даже если она уже есть")
    args = parser.parse_args()
    places = Places()
    wanted = {name.lower() for name in args.channels}
    channels = [name for name in sorted(folder.name for folder in TG_DIR.iterdir() if (folder / "posts.json").exists())
                if not wanted or name.lower() in wanted]
    if args.only != "cut":
        download_step(channels, places, args)
    if args.only != "download":
        cut_step(channels, places, args)


if __name__ == "__main__":
    main()
