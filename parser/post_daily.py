"""Автопостинг «Аналитики дня» в открытый Telegram канал, без участия человека.

Три поста в день, по одному за запуск, по порядку: 1) «Ниже рынка», 2) «Самые красивые», 3) «Подборка дня».
Каждый запуск публикует следующий ещё не вышедший пост последнего полного дня. Расписание: run_posts.sh
через install_schedule.sh (по умолчанию 10:05, 14:05 и 19:05). Если Мак спал, macOS запустит пропущенное
после пробуждения, и посты догонят по одному.

Картинки рисует сама админка (/admin/daily) в браузере, поэтому скрипт:
  1. поднимает свой экземпляр сайта (npm run dev на порту POSTS_PORT, папка сборки .next-posts),
     чтобы не мешать сайту, который открыт руками;
  2. открывает /admin/daily в невидимом Chrome через Playwright, ждёт, пока картинка дорисуется;
  3. нажимает «Опубликовать в канал» и «Да»: дальше всё как при ручной публикации
     (подпись без заглушек, учёт в .data/tg-posts.json, повторно один и тот же пост не уйдёт);
  4. сообщает Нику в бот, что ушло, со ссылкой. Не вышло: тоже сообщает.

Не публикует, если данные старые (последний полный день раньше позавчера): значит, прогон не работал.
Выключить автопостинг: touch data/posts.off. Включить обратно: rm data/posts.off

  python post_daily.py            следующий пост
  python post_daily.py --all      все невышедшие посты дня сразу
  python post_daily.py --dry      всё, кроме нажатия «Да» (проверка)
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import tg_bot

PARSER_DIR = Path(__file__).resolve().parent
SITE_DIR = PARSER_DIR.parent
PORT = int(os.environ.get("POSTS_PORT", "3002"))
BASE = f"http://localhost:{PORT}"
OFF_FILE = PARSER_DIR / "data" / "posts.off"
NAMES = {"nizhe-rynka": "Ниже рынка", "samye-krasivye": "Самые красивые", "podborka": "Подборка дня"}
MAX_AGE_DAYS = 2  # последний полный день не старше позавчера


def title_of(key: str) -> str:
    return next((name for prefix, name in NAMES.items() if key.startswith(prefix)), key)


def site_up() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/admin/daily", timeout=5):
            return True
    except Exception:
        return False


def start_site() -> subprocess.Popen | None:
    if site_up():
        return None
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("не найден npm (Node.js): для launchd допишите путь к node в run_posts.sh")
    env = {**os.environ, "NEXT_DIST_DIR": ".next-posts", "PORT": str(PORT)}
    env.pop("NEXT_PUBLIC_PREVIEW", None)
    log = open(PARSER_DIR / "data" / "logs" / "posts-site.log", "a")
    process = subprocess.Popen([npm, "run", "dev", "--", "-p", str(PORT)], cwd=SITE_DIR, env=env,
                               stdout=log, stderr=log, start_new_session=True)
    for _ in range(90):
        if site_up():
            return process
        if process.poll() is not None:
            raise RuntimeError("сайт не запустился, см. data/logs/posts-site.log")
        time.sleep(2)
    raise RuntimeError("сайт не ответил за 3 минуты, см. data/logs/posts-site.log")


def stop_site(process: subprocess.Popen | None) -> None:
    if process and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)


def open_browser(playwright):
    try:
        return playwright.chromium.launch(channel="chrome", headless=True)
    except Exception:
        return playwright.chromium.launch(headless=True)  # нет Chrome: встроенный Chromium Playwright


def publish(take_all: bool, dry: bool) -> list[str]:
    """Публикует и возвращает строки отчёта."""
    from playwright.sync_api import sync_playwright

    report: list[str] = []
    with sync_playwright() as playwright:
        browser = open_browser(playwright)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(f"{BASE}/admin/daily", wait_until="load", timeout=180_000)
        page.wait_for_selector("[data-day]", timeout=180_000)
        day = page.get_attribute("[data-day]", "data-day")
        if date.fromisoformat(day) < date.today() - timedelta(days=MAX_AGE_DAYS):
            raise RuntimeError(f"данные старые: последний полный день {day}, прогон парсера не работал")

        sections = page.locator("section[data-post]")
        pending = []
        for i in range(sections.count()):
            section = sections.nth(i)
            if section.get_attribute("data-sent") or section.locator("canvas").count() == 0:
                continue  # уже в канале или в этот день машин для поста нет
            pending.append(section)
        if not pending:
            report.append(f"Все посты за {day} уже в канале")
            return report

        for section in pending if take_all else pending[:1]:
            key = section.get_attribute("data-post")
            section.locator("canvas[data-ready]").wait_for(timeout=120_000)
            button = section.get_by_role("button", name="Опубликовать в канал")
            if button.count() == 0:
                raise RuntimeError("нет кнопки «Опубликовать в канал»: канал не настроен (TG_CHANNEL в parser/.env)")
            button.click()
            if dry:
                report.append(f"Проверка: {title_of(key)} за {day} готов к публикации")
                section.get_by_role("button", name="Нет").click()
                continue
            section.get_by_role("button", name="Да", exact=True).click()
            result = section.locator("text=/^(Опубликовано|Не опубликовано)/").first
            result.wait_for(timeout=120_000)
            text = result.inner_text()
            if text.startswith("Не опубликовано"):
                raise RuntimeError(f"{title_of(key)}: {text}")
            link = section.locator("a", has_text="открыть пост")
            url = link.get_attribute("href") if link.count() else ""
            report.append(f"📣 В канал ушёл пост «{title_of(key)}» за {day}" + (f"\n{url}" if url else ""))
        browser.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Автопостинг аналитики дня в Telegram канал")
    parser.add_argument("--all", action="store_true", help="все невышедшие посты дня сразу")
    parser.add_argument("--dry", action="store_true", help="не нажимать «Да»")
    args = parser.parse_args()

    if OFF_FILE.exists():
        print("Автопостинг выключен (data/posts.off)")
        return
    if not tg_bot.settings().get("TG_CHANNEL"):
        print("Канал не настроен: нет TG_CHANNEL в .env (python tg_bot.py setup)")
        return

    process = None
    try:
        process = start_site()
        lines = publish(args.all, args.dry)
        print("\n".join(lines))
        for line in lines:
            if line.startswith("📣"):
                tg_bot.send(line, silent=True)
    except Exception as error:
        message = f"Автопостинг: пост не вышел ({error})"
        print(message)
        tg_bot.alert(message, key="posts", every_hours=3)
        sys.exit(1)
    finally:
        stop_site(process)


if __name__ == "__main__":
    main()
