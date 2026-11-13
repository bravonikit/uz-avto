"""Скачивает посты публичных Telegram каналов из tg_accounts.txt.

Берёт открытую веб версию канала (t.me/s/<канал>): без входа, без ключей и без аккаунта.
Видит только публичные каналы, у которых включён предпросмотр.

Результат для каждого канала:
  data/_tg/<канал>/posts.json        все посты; у каждого история изменений текста
  data/_tg/<канал>/images/<id>_N.jpg  первые фото поста (у видео это обложка)
  data/_tg/state.json                 что и когда скачано

Чем Telegram отличается от Instagram и что здесь учтено:
  * пост можно править: продавец дописывает «SOTILDI» или меняет цену в том же посте.
    Поэтому посты за 14 дней перечитываются каждый запуск, за 90 дней раз в неделю,
    старый текст уходит в history;
  * пост можно удалить: если пост пропал со страницы, ставим removed_at;
  * альбом из 8 фото занимает 8 номеров подряд, это один пост;
  * часть продавцов шлёт видео и текст двумя сообщениями подряд: склеиваем (media_from).

Запуск:
  python tg_download.py            все каналы из tg_accounts.txt
  python tg_download.py azaavtoo   только указанные
"""

import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from accounts import DATA_DIR, PARSER_DIR

TG_DIR = DATA_DIR / "_tg"
TG_ACCOUNTS_FILE = PARSER_DIR / "tg_accounts.txt"
STATE_FILE = TG_DIR / "state.json"

START_DATE = "2026-09-01T00:00:00Z"  # посты старше не берём
# Объявление о машине живёт долго, поэтому следим за постом 90 дней. Чтобы не листать
# каждый день три месяца назад, обход двух видов:
#   обычный, каждый запуск: посты за последние FRESH_DAYS дней;
#   глубокий, раз в DEEP_EVERY_DAYS дней и при первом запуске: посты за TRACK_DAYS дней.
TRACK_DAYS = 90  # сколько дней следим за постом: правки, «продано», удаление
FRESH_DAYS = 14  # это окно перечитываем при каждом запуске
DEEP_EVERY_DAYS = 7  # как часто перечитывать всё окно TRACK_DAYS
MAX_PAGES = 60  # потолок страниц на канал в обычном обходе (страница это около 20 постов)
MAX_PAGES_DEEP = 300  # потолок страниц на канал в глубоком обходе
# Сколько фото поста сохранять на диск. Ссылки на все фото лежат в posts.json и обновляются при
# каждом обходе, поэтому лимит можно поднять позже: недостающие файлы докачаются сами.
# Разово: TG_MAX_PHOTOS=10 python tg_download.py
MAX_PHOTOS = int(os.environ.get("TG_MAX_PHOTOS", "3"))
GLUE_SECONDS = 180  # видео без текста и текст сразу за ним считаем одним постом
PAGE_DELAY = (2, 4)  # пауза между запросами, секунд
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_channels() -> list[tuple[str, str | None]]:
    """[(канал, instagram аккаунт или None)]. С аргументами командной строки только указанные каналы."""
    pairs = []
    for line in TG_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        parts = line.split()
        channel = parts[0].rstrip("/").split("/")[-1].lstrip("@")
        if channel.lower() not in {name.lower() for name, _ in pairs}:
            pairs.append((channel, parts[1].lower() if len(parts) > 1 else None))
    # Продавец попросил убрать его объявления (status = opted_out в data/sellers/sellers.csv): канал не качаем
    try:
        from sellers import SellerIndex
        index = SellerIndex()
        pairs = [pair for pair in pairs if not index.find("telegram", pair[0], "")["opted_out"]]
    except FileNotFoundError:
        pass
    wanted = {name.lower() for name in sys.argv[1:]}
    if wanted:
        pairs = [pair for pair in pairs if pair[0].lower() in wanted]
    return pairs


def parse_views(text: str | None) -> int | None:
    """"1.16K" → 1160, "2.3M" → 2300000, "580" → 580."""
    if not text:
        return None
    match = re.fullmatch(r"([\d.]+)\s*([KM]?)", text.strip())
    if not match:
        return None
    return int(float(match.group(1)) * {"": 1, "K": 1_000, "M": 1_000_000}[match.group(2)])


def style_url(tag) -> str | None:
    """Адрес картинки из style="background-image:url('...')"."""
    match = re.search(r"url\('([^']+)'\)", (tag.get("style") or "")) if tag else None
    return match.group(1) if match else None


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def parse_page(html: str, channel: str) -> list[dict]:
    """Посты одной страницы t.me/s/<канал>, от старых к новым."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    for message in soup.select("div.tgme_widget_message[data-post]"):
        post_id = int(message["data-post"].split("/")[-1])
        time_tag = message.select_one(".tgme_widget_message_date time[datetime]")
        if not time_tag:
            continue  # служебное сообщение без даты
        date = datetime.fromisoformat(time_tag["datetime"]).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        text_tag = message.select_one(".tgme_widget_message_text")
        text = ""
        if text_tag:
            for br in text_tag.find_all("br"):
                br.replace_with("\n")
            text = text_tag.get_text().strip()

        photos = [url for url in (style_url(tag) for tag in message.select(".tgme_widget_message_photo_wrap")) if url]
        video_tags = message.select(".tgme_widget_message_video_player, .tgme_widget_message_roundvideo_player")
        durations = [tag.get_text().strip() for tag in message.select(".message_video_duration, .tgme_widget_message_roundvideo_duration")]
        thumbs = [url for url in (style_url(tag) for tag in message.select(".tgme_widget_message_video_thumb, .tgme_widget_message_roundvideo_thumb")) if url]
        video_file = message.select_one("video[src]")  # есть только у небольших видео

        if video_tags and photos:
            kind = "album"
        elif video_tags:
            kind = "video"
        elif len(photos) > 1:
            kind = "album"
        elif photos:
            kind = "photo"
        else:
            kind = "text"

        forwarded = message.select_one(".tgme_widget_message_forwarded_from_name")
        meta = message.select_one(".tgme_widget_message_meta")
        views = message.select_one(".tgme_widget_message_views")
        posts.append({
            "channel": channel,
            "id": post_id,
            "url": f"https://t.me/{channel}/{post_id}",
            "date": date,
            "type": kind,
            "text": text,
            "photos": photos,
            "video_thumbs": thumbs,
            "video_durations": durations,
            "video_url": video_file["src"] if video_file else None,
            "views": parse_views(views.get_text() if views else None),
            "edited": bool(meta and "edited" in meta.get_text()),
            "forwarded_from": forwarded.get_text().strip() if forwarded else None,
        })
    return sorted(posts, key=lambda post: post["id"])


def glue_media(posts: dict[str, dict]) -> None:
    """Видео или фото без текста и текст без картинок сразу за ним: это один пост.

    Текстовому посту ставим media_from (номер поста с картинкой), посту с картинкой text_in.
    """
    ordered = sorted(posts.values(), key=lambda post: post["id"])
    for before, after in zip(ordered, ordered[1:]):
        if before.get("removed_at") or after.get("removed_at"):
            continue
        if before["text"] or before["type"] == "text" or after["type"] != "text" or not after["text"]:
            continue
        gap = (datetime.fromisoformat(after["date"].replace("Z", "+00:00"))
               - datetime.fromisoformat(before["date"].replace("Z", "+00:00"))).total_seconds()
        if 0 <= gap <= GLUE_SECONDS:
            after["media_from"] = before["id"]
            before["text_in"] = after["id"]


def merge_posts(known: dict[str, dict], fetched: list[dict], seen_at: str, full_from_id: int | None) -> dict:
    """Вливает свежие посты в сохранённые. Возвращает счётчики: новых, изменённых, удалённых.

    full_from_id: с какого номера страницы прочитаны подряд без дыр. Сохранённый пост с номером
    не меньше этого, которого нет в свежих, удалён продавцом.
    """
    counts = {"new": 0, "changed": 0, "removed": 0}
    fetched_ids = set()
    for post in fetched:
        key = str(post["id"])
        fetched_ids.add(key)
        old = known.get(key)
        if old is None:
            post.update(first_seen=seen_at, last_seen=seen_at, text_hash=text_hash(post["text"]), history=[])
            known[key] = post
            counts["new"] += 1
            continue
        if text_hash(post["text"]) != old["text_hash"]:
            old["history"].append({"until": seen_at, "text": old["text"]})
            old["text"] = post["text"]
            old["text_hash"] = text_hash(post["text"])
            old["changed_at"] = seen_at
            counts["changed"] += 1
        # Ссылки на картинки у Telegram временные, держим свежие. Скачанные файлы (images) не трогаем
        for field in ("photos", "video_thumbs", "video_durations", "video_url", "views", "edited", "type"):
            old[field] = post[field]
        old["last_seen"] = seen_at
        old.pop("removed_at", None)
    if full_from_id is not None:
        for key, old in known.items():
            if int(key) >= full_from_id and key not in fetched_ids and not old.get("removed_at"):
                old["removed_at"] = seen_at
                counts["removed"] += 1
    return counts


def days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_deep_due(known: dict, last_deep: str | None) -> bool:
    """Глубокий обход нужен при первом запуске и раз в DEEP_EVERY_DAYS дней."""
    return not known or not last_deep or last_deep < days_ago(DEEP_EVERY_DAYS)


def fetch_channel(channel: str, deep: bool) -> tuple[list[dict], int | None, str]:
    """Листает канал назад. Возвращает (посты, с какого номера прочитано подряд, статус)."""
    stop_date = max(START_DATE, days_ago(TRACK_DAYS if deep else FRESH_DAYS))
    max_pages = MAX_PAGES_DEEP if deep else MAX_PAGES
    fetched: dict[int, dict] = {}
    before = None
    for page in range(max_pages):
        url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as error:
            return list(fetched.values()), None, f"ошибка: {type(error).__name__}"
        if response.status_code != 200:
            return list(fetched.values()), None, f"ошибка: ответ {response.status_code}"
        posts = parse_page(response.text, channel)
        if not posts:
            if page == 0:
                return [], None, "нет постов: канал закрыт, без предпросмотра или имя неверное"
            break
        for post in posts:
            fetched[post["id"]] = post
        before = posts[0]["id"]
        if posts[0]["date"] < stop_date or before <= 1:
            break
        time.sleep(random.uniform(*PAGE_DELAY))
    ordered = sorted(fetched.values(), key=lambda post: post["id"])
    ordered = [post for post in ordered if post["date"] >= START_DATE]
    return ordered, (ordered[0]["id"] if ordered else None), "ok"


def download_images(channel_dir: Path, posts: dict[str, dict]) -> int:
    """Скачивает первые MAX_PHOTOS картинок постов, у которых их ещё нет. Возвращает, сколько файлов скачано.

    Если лимит подняли, докачивает недостающие картинки старых постов (пока пост в окне обхода
    и его ссылки свежие).
    """
    images_dir = channel_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for post in posts.values():
        if post.get("removed_at"):
            continue
        urls = (post["photos"] + post["video_thumbs"])[:MAX_PHOTOS]
        files = list(post.get("images") or [])
        if post.get("images") is not None and len(files) >= len(urls):
            continue
        for number, url in enumerate(urls, start=1):
            path = images_dir / f"{post['id']}_{number}.jpg"
            name = str(path.relative_to(PARSER_DIR))
            if name in files:
                continue
            if path.exists():
                files.append(name)
                continue
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                if response.status_code == 200 and response.content:
                    path.write_bytes(response.content)
                    files.append(name)
                    saved += 1
            except requests.RequestException:
                pass
            time.sleep(random.uniform(0.3, 0.8))
        post["images"] = sorted(files)
    return saved


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    channels = load_channels()
    if not channels:
        print("В tg_accounts.txt нет каналов")
        return
    state = load_json(STATE_FILE, {})
    totals = {"new": 0, "changed": 0, "removed": 0}
    for number, (channel, instagram) in enumerate(channels):
        channel_dir = TG_DIR / channel
        posts_file = channel_dir / "posts.json"
        known = load_json(posts_file, {})
        seen_at = now_iso()
        last_deep = state.get(channel, {}).get("last_deep")
        deep = is_deep_due(known, last_deep)
        fetched, full_from_id, status = fetch_channel(channel, deep)
        counts = {"new": 0, "changed": 0, "removed": 0}
        if status == "ok":
            counts = merge_posts(known, fetched, seen_at, full_from_id)
            glue_media(known)
            save_json(posts_file, known)  # посты сохраняем до картинок: если прогон прервут, текст не пропадёт
            images = download_images(channel_dir, known)
            save_json(posts_file, known)
            if deep:
                last_deep = seen_at
            print(f"{channel}{' (глубокий обход)' if deep else ''}: постов {len(known)}, новых {counts['new']}, изменён текст {counts['changed']}, "
                  f"удалено {counts['removed']}, картинок скачано {images}")
        else:
            print(f"{channel}: {status}")
        for key in totals:
            totals[key] += counts[key]
        state[channel] = {"instagram": instagram, "last_run": seen_at, "last_deep": last_deep, "status": status,
                          "posts_total": len(known), **{f"{key}_last_run": value for key, value in counts.items()}}
        save_json(STATE_FILE, state)
        if number < len(channels) - 1:
            time.sleep(random.uniform(*PAGE_DELAY))
    print(f"Telegram готово: каналов {len(channels)}, новых постов {totals['new']}, "
          f"изменённых {totals['changed']}, удалённых {totals['removed']}")


if __name__ == "__main__":
    main()
