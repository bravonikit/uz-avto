"""Сторож: проверяет, что конвейер живой, и пишет в Telegram бот, если что-то сломалось.

Запускается сам каждый час (install_schedule.sh, задание watchdog), отдельно от прогонов: если сломался
сам часовой прогон, сторож это заметит. Одинаковая тревога не чаще раза в 6 часов.

  .venv/bin/python watchdog.py            проверить и отправить тревоги
  .venv/bin/python watchdog.py --print    только показать, что не так, ничего не отправлять
  .venv/bin/python watchdog.py --morning  утренняя сводка «как прошли сутки» (одно сообщение)

Что проверяет:
  * часовой прогон заканчивался не позже 3 часов назад, ночной полный не позже 30 часов назад;
  * новые посты Telegram приходят (днём больше 6 часов без новых: сломалось скачивание или вход);
  * свободное место на Маке, Google Диск подключён и принимает запись;
  * Gemini не отвечает ошибками баланса и ключа; пакеты не висят в очереди больше 12 часов;
  * сайт отвечает на http://localhost:3000 (если включён SITE_URL в .env).
Мёртвый Мак сторож заметить не может. Для этого HEALTHCHECK_URL в .env: адрес проверки на healthchecks.io
(бесплатно). Сторож дёргает его каждый час, а если Мак выключен или спит, healthchecks.io сам пришлёт письмо
или сообщение в Telegram.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

PARSER_DIR = Path(__file__).resolve().parent
DATA = PARSER_DIR / "data"
LOGS = DATA / "logs"
TASHKENT = timezone(timedelta(hours=5))
HOURLY_MAX_H, DAILY_MAX_H, NO_POSTS_MAX_H, QUEUE_MAX_H = 3, 30, 6, 12
FREE_MIN_GB = 8
GEMINI_ERRORS = ("RESOURCE_EXHAUSTED", "prepayment credits are depleted", "PERMISSION_DENIED", "API key not valid",
                 "API_KEY_INVALID", "Нет GEMINI_API_KEY")


def hours_since(moment: datetime) -> float:
    return (datetime.now(timezone.utc) - moment).total_seconds() / 3600


def newest(pattern: str) -> Path | None:
    files = sorted(LOGS.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def last_finish(pattern: str, marker: str) -> datetime | None:
    """Когда в логах этого вида последний раз была строка конца прогона."""
    for log in sorted(LOGS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
        lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
        if any(marker in line for line in lines):
            return datetime.fromtimestamp(log.stat().st_mtime, timezone.utc)
    return None


def check() -> list[tuple[str, str]]:
    """Список проблем: (ключ тревоги, текст)."""
    load_dotenv(PARSER_DIR / ".env")
    problems: list[tuple[str, str]] = []
    now_local = datetime.now(TASHKENT)

    hourly = last_finish("hourly-*.log", "конец")
    daily_running = (DATA / ".daily.lock").exists()
    if hourly is None or (hours_since(hourly) > HOURLY_MAX_H and not daily_running):
        ago = f"{hours_since(hourly):.0f} ч" if hourly else "давно"
        problems.append(("hourly", f"Часовой прогон не заканчивался {ago}. Проверьте Мак и лог data/logs/hourly-*.log"))
    daily = last_finish("20*.log", "конец")
    if daily is None or hours_since(daily) > DAILY_MAX_H:
        problems.append(("daily", "Ночной полный прогон не проходил больше суток (data/logs/ГГГГ-ММ-ДД.log)"))

    listings = DATA / "_tg" / "listings.json"
    if listings.exists() and 10 <= now_local.hour <= 23:
        try:
            items = json.loads(listings.read_text(encoding="utf-8"))
            fresh = max(datetime.fromisoformat(i["date"].replace("Z", "+00:00")) for i in items if i.get("date"))
            if hours_since(fresh) > NO_POSTS_MAX_H:
                problems.append(("noposts", f"Новых постов Telegram нет {hours_since(fresh):.0f} ч: сломалось скачивание "
                                            "или вход в Telegram (tg_download.py)"))
        except (ValueError, KeyError):
            pass

    free = shutil.disk_usage(PARSER_DIR).free / 1024 ** 3
    if free < FREE_MIN_GB:
        problems.append(("space", f"На Маке свободно {free:.1f} ГБ, прогоны скоро встанут"))

    archive = os.environ.get("ARCHIVE_DIR", "").strip()
    if archive:
        root = Path(archive).expanduser()
        if not root.parent.is_dir():
            problems.append(("drive", "Google Диск не подключён: фото и ролики копятся на Маке. Откройте приложение Google Диск"))
        else:
            probe = root / ".watchdog"
            try:
                probe.write_text(datetime.now().isoformat(), encoding="utf-8")
            except OSError as error:
                problems.append(("drive_write", f"Google Диск не принимает запись ({error.strerror or error})"))

    log = newest("hourly-*.log")
    if log:
        tail = log.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
        bad = [line for line in tail if any(word in line for word in GEMINI_ERRORS) and "Traceback" not in line]
        if bad:
            problems.append(("gemini", "Gemini отвечает ошибкой (баланс или ключ?): " + bad[-1][:200]
                             + ". Пополнить: aistudio.google.com → Billing"))

    for state_file in (DATA / "_cards").glob("*/state.json"):
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for name, job in (state.get("jobs") or {}).items():
            if job.get("collected") or not job.get("sent"):
                continue
            sent = datetime.fromisoformat(job["sent"]).replace(tzinfo=TASHKENT)
            if hours_since(sent) > QUEUE_MAX_H:
                problems.append(("queue", f"Пакет карточек {state_file.parent.name}/{name} в очереди Google больше "
                                          f"{QUEUE_MAX_H} ч"))
                break

    site = os.environ.get("SITE_URL", "").strip()
    if site:
        try:
            urllib.request.urlopen(site, timeout=20)
        except Exception as error:  # noqa: BLE001
            problems.append(("site", f"Сайт {site} не отвечает ({str(error)[:80]})"))
    return problems


def heartbeat(ok: bool) -> None:
    url = os.environ.get("HEALTHCHECK_URL", "").strip()
    if not url:
        return
    try:
        urllib.request.urlopen(url if ok else url.rstrip("/") + "/fail", timeout=15)
    except Exception:  # noqa: BLE001
        pass  # нет сети: healthchecks.io сам поднимет тревогу, что пингов нет


def morning(problems: list[tuple[str, str]]) -> str:
    """Короткая сводка за сутки для утреннего сообщения."""
    spend = json.loads((DATA / "_cards" / "spend.json").read_text(encoding="utf-8")) if (DATA / "_cards" / "spend.json").exists() else {}
    yesterday = (datetime.now(TASHKENT) - timedelta(days=1)).strftime("%Y-%m-%d")
    overlay_file = PARSER_DIR.parent / "src" / "data" / "cards-overlay.json"
    cards = len(json.loads(overlay_file.read_text(encoding="utf-8")).get("listings") or {}) if overlay_file.exists() else 0
    free = shutil.disk_usage(PARSER_DIR).free / 1024 ** 3
    lines = [f"☀️ Сводка machinabashina за {yesterday}",
             f"Карточек на сайте с обработкой: {cards}, потрачено на Gemini вчера около ${spend.get(yesterday, 0):.2f}",
             f"Свободно на Маке: {free:.0f} ГБ"]
    lines.append("Всё работает" if not problems else "Проблемы:\n" + "\n".join(f"• {text}" for _, text in problems))
    return "\n".join(lines)


def main() -> None:
    problems = check()
    if "--print" in sys.argv:
        print("\n".join(text for _, text in problems) or "Всё в порядке")
        return
    heartbeat(not problems)
    import tg_bot  # бот проекта: токен и чат в .env (python tg_bot.py setup)
    if "--morning" in sys.argv:
        tg_bot.send(morning(problems), silent=True)
        return
    for key, text in problems:
        tg_bot.alert(text, f"watchdog_{key}", 6)


if __name__ == "__main__":
    main()
