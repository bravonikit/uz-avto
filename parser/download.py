"""Скачивает новые посты Instagram-аккаунтов из accounts.txt через gallery-dl.

Результат для каждого аккаунта:
  data/<аккаунт>/raw_posts.json          — все скачанные посты (новые добавляются к старым)
  data/<аккаунт>/images/<shortcode>.jpg  — первая картинка поста (у рилса — превью)
  data/state.json                        — что и когда скачано по каждому аккаунту

Запуск:
  python download.py                    — до MAX_ACCOUNTS_PER_RUN аккаунтов, давно не качавшиеся первыми
  python download.py auto_sale_abdulloh — только указанные
  python status.py                      — посмотреть, что скачано

Вход в Instagram берётся из Safari: просто будьте залогинены там.
"""

import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import ig_api
from accounts import PARSER_DIR, account_dir, load_accounts
from state import load_state, save_state

# Паузы случайные, чтобы запросы не шли ровным «ботовым» ритмом
REQUEST_DELAY = "4-6"  # пауза между запросами к Instagram, секунд (gallery-dl берёт случайное число)
IMAGE_DELAY = (1, 3)  # пауза между скачиванием картинок, секунд
ACCOUNT_DELAY = (60, 120)  # пауза между аккаунтами, секунд

POSTS_LIMIT = 10  # сколько последних постов смотреть у аккаунта за раз
MAX_ACCOUNTS_PER_RUN = 30  # сколько аккаунтов за один запуск, остальные в следующий раз
START_DATE = "2026-09-01T00:00:00Z"  # посты старше этой даты не берём

# Номера сообщений в выводе gallery-dl -j
MSG_ERROR = -1
MSG_URL = 3  # один файл поста (у карусели их несколько)

# Instagram не принял вход (куки устарели или не прочитались). Дальше качать бессмысленно:
# все аккаунты упадут так же, а лишние запросы без входа только привлекают внимание.
AUTH_ERROR_WORDS = ("401", "unauthorized", "login", "checkpoint", "challenge")
AUTH_STATUS = "нет входа в Instagram"
MAX_AUTH_ERRORS = 3  # столько аккаунтов подряд без входа, и прогон останавливается
EXIT_NO_LOGIN = 2

# Если в .env есть токен (python ig_api.py setup), посты берём через официальный API,
# иначе по-старому через gallery-dl и вход из Safari
USE_API = ig_api.is_configured()
if USE_API:
    ACCOUNT_DELAY = (1, 2)  # официальному API длинные паузы не нужны
    MAX_ACCOUNTS_PER_RUN = 150  # лимит API 200 запросов в час, один аккаунт = один запрос
    AUTH_STATUS = "API не отвечает (токен или лимит)"
    MAX_AUTH_ERRORS = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_metadata(account: str) -> tuple[list | None, str]:
    """Запускает gallery-dl и возвращает (JSON, текст ошибки). Сам gallery-dl ничего не скачивает (-j)."""
    command = [
        sys.executable, "-m", "gallery_dl",
        "--cookies-from-browser", "safari",
        # --post-range считает посты; --range считал бы файлы,
        # и карусель из 5 фото заняла бы 5 мест
        "--post-range", f"1-{POSTS_LIMIT}",
        "--sleep-request", REQUEST_DELAY,
        "-j",
        f"https://www.instagram.com/{account}/posts/",
    ]
    print(f"  Смотрю {POSTS_LIMIT} последних постов (пауза {REQUEST_DELAY} с между запросами)...")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(result.stdout), ""
    except json.JSONDecodeError:
        error = result.stderr.strip() or "gallery-dl не вернул данные"
        print(f"  gallery-dl не вернул данные. Его сообщение:\n  {error}")
        return None, error.splitlines()[-1][:200]


def fetch_posts(account: str) -> tuple[list[dict], str, bool]:
    """Посты аккаунта из API или gallery-dl: (посты, текст ошибки, это проблема входа?)."""
    if USE_API:
        print(f"  Запрашиваю {POSTS_LIMIT} последних постов через API...")
        return ig_api.fetch_posts(account, POSTS_LIMIT)
    messages, error = fetch_metadata(account)
    posts = collect_posts(messages, account) if messages is not None else []
    return posts, error, not posts and is_auth_error(messages, error)


def post_type(file: dict) -> str:
    if file.get("type") == "reel":
        return "reel"
    if file.get("count", 1) > 1:
        return "carousel"
    return "photo"


def to_iso(date: str) -> str:
    # gallery-dl отдаёт время UTC в виде "2026-11-09 11:00:37"
    return datetime.fromisoformat(date).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_auth_error(messages: list | None, error: str) -> bool:
    """Похоже ли, что Instagram отказал из-за входа, а не из-за самого аккаунта."""
    texts = [error]
    for message in messages or []:
        if message[0] == MSG_ERROR:
            texts.append(str(message[1].get("message", "")))
    return any(word in text.lower() for text in texts for word in AUTH_ERROR_WORDS)


def collect_posts(messages: list, account: str) -> list[dict]:
    """Собирает по одной записи на пост, даже если в посте несколько файлов."""
    posts: dict[str, dict] = {}  # shortcode → пост; порядок как в профиле (от новых к старым)
    for message in messages:
        if message[0] == MSG_ERROR:
            print(f"  Ошибка gallery-dl: {message[1].get('message')}")
            continue
        if message[0] != MSG_URL:
            continue

        file = message[2]
        shortcode = file["post_shortcode"]
        if shortcode in posts:
            continue  # второй, третий... файл карусели — пост уже записан

        posts[shortcode] = {
            "account": account,
            "shortcode": shortcode,
            "url": file["post_url"],
            "date": to_iso(file["post_date"]),
            "downloaded_at": now_iso(),
            "type": post_type(file),
            "description": file.get("description") or "",
            # display_url — всегда картинка: у видео это превью
            "image_url": file["display_url"],
            "image": f"data/{account}/images/{shortcode}.jpg",
        }
    return list(posts.values())


def download_image(url: str, path: Path) -> bool:
    """Скачивает картинку. True — если реально качали (а не взяли готовую)."""
    if path.exists():
        return False  # уже скачано в прошлый раз
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    path.write_bytes(response.content)
    return True


def save_posts(output_file: Path, posts: list[dict]) -> tuple[list[dict], int]:
    """Добавляет посты к уже скачанным раньше, а не затирает их.

    Свежая версия поста заменяет старую (описание могли поправить),
    но дата первой скачки сохраняется.
    Возвращает (новые посты, сколько всего в файле).
    """
    saved: dict[str, dict] = {}
    if output_file.exists():
        for post in json.loads(output_file.read_text(encoding="utf-8")):
            saved[post["shortcode"]] = post
    new_posts = [post for post in posts if post["shortcode"] not in saved]
    for post in posts:
        old = saved.get(post["shortcode"])
        if old and old.get("downloaded_at"):
            post["downloaded_at"] = old["downloaded_at"]
        saved[post["shortcode"]] = post
    merged = sorted(saved.values(), key=lambda post: post["date"], reverse=True)
    output_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return new_posts, len(merged)


def download_account(account: str, state: dict) -> None:
    """Скачивает один аккаунт и записывает итог в state."""
    folder = account_dir(account)
    images_dir = folder / "images"
    output_file = folder / "raw_posts.json"
    record = state.setdefault(account, {})
    previous_run = record.get("last_run")
    record["last_run"] = now_iso()

    posts, error, auth_error = fetch_posts(account)
    if auth_error:
        # Аккаунт не виноват: возвращаем ему прежнее место в очереди
        record["status"] = AUTH_STATUS
        record["new_last_run"] = 0
        if previous_run:
            record["last_run"] = previous_run
        else:
            del record["last_run"]
        print(f"  {AUTH_STATUS}" + (f": {error}" if USE_API else ""))
        return
    if not posts:
        record["status"] = f"ошибка: {error}" if error else "постов не найдено"
        record["new_last_run"] = 0
        print(f"  {record['status']}")
        return

    # Закреплённые посты бывают старыми: отрезаем всё, что раньше START_DATE
    fresh = [post for post in posts if post["date"] >= START_DATE]
    skipped_old = len(posts) - len(fresh)

    images_dir.mkdir(parents=True, exist_ok=True)
    for post in fresh:
        if not post["image"]:
            # API не отдал картинку (рилс с закрытым скачиванием). Если она скачана раньше, оставляем её
            old_image = f"data/{account}/images/{post['shortcode']}.jpg"
            if (PARSER_DIR / old_image).exists():
                post["image"] = old_image
            continue
        try:
            if download_image(post["image_url"], PARSER_DIR / post["image"]):
                time.sleep(random.uniform(*IMAGE_DELAY))
        except requests.RequestException as error:
            print(f"  {post['shortcode']}: не удалось скачать картинку ({error})")
            post["image"] = None

    new_posts, total = save_posts(output_file, fresh)

    record["status"] = "ok"
    record["last_success"] = record["last_run"]
    record["new_last_run"] = len(new_posts)
    record["posts_total"] = total
    if fresh:
        record["newest_post"] = max(record.get("newest_post", ""), max(p["date"] for p in fresh))
    # Все POSTS_LIMIT постов оказались новыми — между запусками могли выйти ещё, и мы их не увидели
    record["maybe_missed"] = bool(record.get("posts_total_before")) and len(new_posts) >= POSTS_LIMIT
    record["posts_total_before"] = total

    print(f"  Новых постов: {len(new_posts)}, всего у аккаунта: {total}"
          + (f", старше {START_DATE[:10]} пропущено: {skipped_old}" if skipped_old else ""))
    if record["maybe_missed"]:
        print(f"  Внимание: все {POSTS_LIMIT} постов новые, часть могла не поместиться. Увеличьте POSTS_LIMIT.")


def pick_accounts(accounts: list[str], state: dict, explicit: bool) -> list[str]:
    """Без явного списка: сначала ни разу не качавшиеся, потом самые давние."""
    if explicit:
        return accounts
    order = sorted(accounts, key=lambda a: state.get(a, {}).get("last_run", ""))
    return order[:MAX_ACCOUNTS_PER_RUN]


def main() -> None:
    accounts = load_accounts()
    if not accounts:
        sys.exit("Список аккаунтов пуст: впишите их в accounts.txt")
    if USE_API:
        ig_api.refresh_if_needed()
    state = load_state()
    todo = pick_accounts(accounts, state, explicit=len(sys.argv) > 1)
    print(f"Аккаунтов в списке: {len(accounts)}, в этом запуске: {len(todo)}, "
          f"источник: {'официальный API' if USE_API else 'gallery-dl'}\n")

    done, auth_errors = [], 0
    for n, account in enumerate(todo, start=1):
        if n > 1:
            pause = random.uniform(*ACCOUNT_DELAY)
            print(f"\nПауза {pause:.0f} с перед следующим аккаунтом...")
            time.sleep(pause)
        print(f"[{n}/{len(todo)}] {account}")
        download_account(account, state)
        save_state(state)  # после каждого аккаунта, чтобы не потерять при Ctrl+C
        done.append(account)
        auth_errors = auth_errors + 1 if state[account]["status"] == AUTH_STATUS else 0
        if auth_errors >= MAX_AUTH_ERRORS:
            print(f"\nПрогон остановлен: {AUTH_STATUS} у {MAX_AUTH_ERRORS} аккаунтов подряд.")
            if USE_API:
                print("Проверьте токен: python ig_api.py status, при необходимости python ig_api.py setup")
            else:
                print("Откройте instagram.com в Safari, проверьте вход и запустите ./run_daily.sh ещё раз.")
            sys.exit(EXIT_NO_LOGIN)

    failed = [a for a in done if state[a]["status"] != "ok"]
    new_total = sum(state[a].get("new_last_run", 0) for a in done)
    print(f"\nГотово: {len(done) - len(failed)} из {len(todo)} аккаунтов, новых постов: {new_total}")
    if failed:
        print("Не получилось: " + ", ".join(failed))
    left = len(accounts) - len(todo)
    if left > 0:
        print(f"Остальные {left} аккаунтов скачаются в следующих запусках.")
    print("Подробности: python status.py")


if __name__ == "__main__":
    main()
