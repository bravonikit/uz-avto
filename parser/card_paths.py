"""Папка поста (карточки) на Google Диске: всё по одному посту лежит вместе.

<архив>/cards/<канал>/<день>_<номер поста>/        например cards/aslauto/2026-11-17_3920/
    photo_01.jpg, photo_02.jpg ...   фото поста, как их выложил продавец
    video.mp4                        ролик целиком
    frames/                          раскадровка ролика: frame_NN.jpg, audio.m4a, meta.json, picks/, picks_gemini/
    post.txt                         текст поста
    (позже сюда же: обложка, дорисованные и сгенерированные фото, учёт шагов card.json)

День берётся по Ташкенту из даты поста. Раскладка введена 19.11.2026, до неё фото лежали в
<архив>/data/_tg/<канал>/images/, ролики в <архив>/data/_tg/<канал>/videos/, раскадровка
в <архив>/videos/<канал>/tg-<канал>-<id>/. Старое переносит migrate_cards.py.

На Маке пути не меняются: data/_tg/<канал>/images/<id>_N.jpg остаётся ярлыком на файл в папке поста.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from accounts import DATA_DIR

TG_DIR = DATA_DIR / "_tg"
CARDS = "cards"
VIDEO_NAME = "video.mp4"
FRAMES_NAME = "frames"
TEXT_NAME = "post.txt"
LOCAL_PHOTO = re.compile(r"data/_tg/([^/]+)/images/(\d+)_(\d+)\.jpg$")


def tashkent_day(date_iso: str | None) -> str:
    """Дата поста по Ташкенту (UTC+5): '2026-11-17'. Нет даты: 'unknown'."""
    try:
        moment = datetime.fromisoformat((date_iso or "").replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    return (moment + timedelta(hours=5)).strftime("%Y-%m-%d")


class CardIndex:
    """Имя папки поста по каналу и номеру. Посты канала читаются один раз и только когда понадобились."""

    def __init__(self, tg_dir: Path = TG_DIR) -> None:
        self.tg_dir = tg_dir
        self.posts: dict[str, dict[str, dict]] = {}

    def channel_posts(self, channel: str) -> dict[str, dict]:
        if channel not in self.posts:
            file = self.tg_dir / channel / "posts.json"
            self.posts[channel] = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
        return self.posts[channel]

    def name(self, channel: str, post_id) -> str:
        post = self.channel_posts(channel).get(str(post_id)) or {}
        return f"{tashkent_day(post.get('date'))}_{post_id}"

    def card_dir(self, archive: Path, channel: str, post_id) -> Path:
        return archive / CARDS / channel / self.name(channel, post_id)

    def photo_target(self, archive: Path, local_name: str) -> Path | None:
        """Куда в архиве ложится фото 'data/_tg/<канал>/images/<id>_<N>.jpg'. None, если имя не такого вида."""
        match = LOCAL_PHOTO.search(local_name.replace("\\", "/"))
        if not match:
            return None
        channel, post_id, number = match.group(1), match.group(2), int(match.group(3))
        return self.card_dir(archive, channel, post_id) / f"photo_{number:02d}.jpg"

    def text(self, channel: str, post_id) -> str:
        """Текст поста. У видео или фото без подписи берём текст сообщения сразу за ним (text_in)."""
        posts = self.channel_posts(channel)
        post = posts.get(str(post_id)) or {}
        if not post.get("text") and post.get("text_in"):
            post = posts.get(str(post["text_in"])) or post
        return post.get("text") or ""


def write_text(card: Path, text: str) -> bool:
    """Кладёт текст поста в папку. True, если файл записан сейчас."""
    target = card / TEXT_NAME
    if not text or target.exists():
        return False
    card.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return True
