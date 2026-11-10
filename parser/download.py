"""Скачивает последние посты Instagram-профиля через gallery-dl.

Результат:
  data/raw_posts.json             — ссылка, дата, текст, тип и картинка каждого поста
  data/images/<shortcode>.jpg     — первая картинка поста (у рилса — превью)

Вход в Instagram берётся из Safari: просто будьте залогинены там.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

DELAY_SEC = 3  # пауза между запросами к Instagram, секунд
PROFILE = "auto_sale_abdulloh"
POSTS_LIMIT = 50

PARSER_DIR = Path(__file__).parent
DATA_DIR = PARSER_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
OUTPUT_FILE = DATA_DIR / "raw_posts.json"

# Номера сообщений в выводе gallery-dl -j
MSG_ERROR = -1
MSG_URL = 3  # один файл поста (у карусели их несколько)


def fetch_metadata() -> list:
    """Запускает gallery-dl и возвращает его JSON. Сам gallery-dl ничего не скачивает (-j)."""
    command = [
        sys.executable, "-m", "gallery_dl",
        "--cookies-from-browser", "safari",
        # --post-range считает посты; --range считал бы файлы,
        # и карусель из 5 фото заняла бы 5 мест из 50
        "--post-range", f"1-{POSTS_LIMIT}",
        "--sleep-request", str(DELAY_SEC),
        "-j",
        f"https://www.instagram.com/{PROFILE}/posts/",
    ]
    print(f"Получаю {POSTS_LIMIT} последних постов {PROFILE} (пауза {DELAY_SEC} с между запросами)...")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(f"gallery-dl не вернул данные. Его сообщение:\n{result.stderr.strip()}")


def post_type(file: dict) -> str:
    if file.get("type") == "reel":
        return "reel"
    if file.get("count", 1) > 1:
        return "carousel"
    return "photo"


def to_iso(date: str) -> str:
    # gallery-dl отдаёт время UTC в виде "2026-11-09 11:00:37"
    return datetime.fromisoformat(date).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_posts(messages: list) -> list[dict]:
    """Собирает по одной записи на пост, даже если в посте несколько файлов."""
    posts: dict[str, dict] = {}  # shortcode → пост; порядок как в профиле (от новых к старым)
    for message in messages:
        if message[0] == MSG_ERROR:
            print(f"Ошибка gallery-dl: {message[1].get('message')}")
            continue
        if message[0] != MSG_URL:
            continue

        file = message[2]
        shortcode = file["post_shortcode"]
        if shortcode in posts:
            continue  # второй, третий... файл карусели — пост уже записан

        posts[shortcode] = {
            "shortcode": shortcode,
            "url": file["post_url"],
            "date": to_iso(file["post_date"]),
            "type": post_type(file),
            "description": file.get("description") or "",
            # display_url — всегда картинка: у видео это превью
            "image_url": file["display_url"],
            "image": f"data/images/{shortcode}.jpg",
        }
    return list(posts.values())


def download_image(url: str, path: Path) -> None:
    if path.exists():
        return  # уже скачано в прошлый раз
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    path.write_bytes(response.content)


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    posts = collect_posts(fetch_metadata())

    for i, post in enumerate(posts, start=1):
        try:
            download_image(post["image_url"], PARSER_DIR / post["image"])
        except requests.RequestException as error:
            print(f"  [{i}/{len(posts)}] {post['shortcode']}: не удалось скачать картинку ({error})")
            post["image"] = None

    OUTPUT_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

    with_text = sum(1 for post in posts if post["description"].strip())
    print(f"\nСохранено постов: {len(posts)} → {OUTPUT_FILE.relative_to(PARSER_DIR)}")
    print(f"С непустым описанием: {with_text}")
    for i, post in enumerate(posts[:3], start=1):
        print(f"\n--- Пост {i}: {post['url']} ({post['date']}, {post['type']})")
        print(post["description"] or "(без описания)")


if __name__ == "__main__":
    main()
