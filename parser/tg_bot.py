"""Telegram бот проекта: служебные уведомления Нику и данные для постов в открытый канал.

Настройка (один раз):
  1. В Telegram у @BotFather: /newbot, токен в parser/.env строкой TG_BOT_TOKEN=...
  2. Напишите боту /start. Если канал уже создан: добавьте бота админом канала с правом публикации
     и опубликуйте в канале любое сообщение (потом его можно удалить).
  3. python tg_bot.py setup  → находит ваш чат и канал, дописывает в .env TG_ALERT_CHAT_ID и TG_CHANNEL

Команды:
  python tg_bot.py setup                         найти чат и канал, записать в .env
  python tg_bot.py test                          проверочное сообщение себе
  python tg_bot.py report data/logs/ДЕНЬ.log     итог прогона (вызывает run_daily.sh в конце)
  python tg_bot.py alert "текст" --key space     срочное уведомление, одно и то же не чаще раза в 6 часов

Без токена все команды молча ничего не делают: прогон парсера от бота не зависит.
Постинг картинок дня в канал делает сайт: кнопка «Опубликовать в канал» в /admin/daily.
"""

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values, set_key

PARSER_DIR = Path(__file__).resolve().parent
ENV_FILE = PARSER_DIR / ".env"
LOG_DIR = PARSER_DIR / "data" / "logs"
ALERTS_FILE = PARSER_DIR / "data" / ".tg_alerts.json"
API = "https://api.telegram.org/bot{token}/{method}"
MESSAGE_LIMIT = 4096


def settings() -> dict:
    return {key: (value or "").strip() for key, value in dotenv_values(ENV_FILE).items()} if ENV_FILE.exists() else {}


def call(token: str, method: str, **payload):
    response = requests.post(API.format(token=token, method=method), json=payload, timeout=30)
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or f"Telegram ответил {response.status_code}")
    return data["result"]


def send(text: str) -> bool:
    """Сообщение Нику. False, если бот не настроен или Telegram не ответил (прогон из за этого не падает)."""
    env = settings()
    token, chat = env.get("TG_BOT_TOKEN"), env.get("TG_ALERT_CHAT_ID")
    if not token or not chat:
        return False
    try:
        call(token, "sendMessage", chat_id=chat, text=text[:MESSAGE_LIMIT], link_preview_options={"is_disabled": True})
        return True
    except Exception as error:  # сеть, неверный токен: пишем в лог и идём дальше
        print(f"Telegram бот: не отправилось ({error})")
        return False


def setup() -> None:
    env = settings()
    token = env.get("TG_BOT_TOKEN")
    if not token:
        sys.exit("В parser/.env нет TG_BOT_TOKEN. Создайте бота у @BotFather и добавьте строку TG_BOT_TOKEN=...")
    me = call(token, "getMe")
    print(f"Бот: @{me['username']}")
    updates = call(token, "getUpdates", allowed_updates=["message", "channel_post", "my_chat_member"])
    private = channel = None
    for update in updates:
        for kind in ("message", "channel_post", "my_chat_member"):
            chat = (update.get(kind) or {}).get("chat")
            if not chat:
                continue
            if chat["type"] == "private":
                private = chat
            elif chat["type"] == "channel":
                channel = chat
    if private:
        set_key(str(ENV_FILE), "TG_ALERT_CHAT_ID", str(private["id"]), quote_mode="never")
        print(f"Уведомления: чат с {private.get('first_name', '')} ({private['id']}) записан в .env")
    elif not env.get("TG_ALERT_CHAT_ID"):
        print(f"Личный чат не найден: напишите боту @{me['username']} /start и запустите setup ещё раз")
    if channel:
        value = f"@{channel['username']}" if channel.get("username") else str(channel["id"])
        set_key(str(ENV_FILE), "TG_CHANNEL", value, quote_mode="never")
        print(f"Канал: {channel.get('title', '')} ({value}) записан в .env")
    elif not env.get("TG_CHANNEL"):
        print("Канал не найден: добавьте бота админом канала, опубликуйте там любое сообщение и запустите setup ещё раз.\n"
              "Или впишите в .env строку TG_CHANNEL=@имя_канала руками")
    if send("Бот uz-avto подключён. Сюда будут приходить итоги прогона и срочные уведомления."):
        print("Проверочное сообщение отправлено")


def last_block(path: Path, start: str = "старт") -> list[str]:
    """Строки последнего прогона в логе дня: от последней строки «===== ... старт» до конца файла."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("=====") and start in line]
    return lines[starts[-1]:] if starts else lines


def first(lines: list[str], pattern: str) -> str | None:
    for line in reversed(lines):
        if re.search(pattern, line):
            return line.strip()
    return None


def free_gb() -> float:
    return shutil.disk_usage(PARSER_DIR).free / 1024 ** 3


def errors(lines: list[str]) -> list[str]:
    """Последние строки ошибок Python (строка после Traceback с типом ошибки)."""
    found = []
    for i, line in enumerate(lines):
        if line.startswith("Traceback"):
            tail = next((x for x in lines[i + 1:i + 60] if re.match(r"^[A-Za-z_.]+(Error|Exception)\b", x)), "ошибка без текста")
            found.append(tail.strip()[:200])
    return found


def report(log: Path, how: str = "", started: str = "") -> str:
    lines = last_block(log)
    finished = any(line.startswith("=====") and "конец" in line for line in lines)
    stopped = first(lines, r"Прогон остановлен|Прогон карточек остановлен")
    problems = errors(lines)
    status = "✅" if finished and not stopped and not problems else "⚠️"
    title = f"{status} Прогон {started or log.stem}{f' ({how})' if how else ''}"
    parts = [title]
    if not finished:
        parts.append(f"Прогон не дошёл до конца, лог {log.relative_to(PARSER_DIR)}")
    if stopped:
        parts.append(stopped)
    for pattern, label in [
        (r"^Telegram( \(часовой\))? готово:", None),
        (r"^Выгружено объявлений:", None),
        (r"перенесено в архив:", "Архив фото"),
    ]:
        line = first(lines, pattern)
        if line:
            line = line.split(" → ")[0]
            parts.append(f"{label}: {line.replace('перенесено в архив: ', 'перенесено ')}" if label else line)
    cards = [line.strip() for line in lines if "$" in line and re.search(r"оценка расходов|потрачено|Карточки за", line)]
    if cards:
        parts.append("Карточки: " + " | ".join(cards[-2:]))
    video = first(last_block(LOG_DIR / f"video-{log.stem}.log"), r"^Видео")
    if video:
        parts.append(video)
    space = free_gb()
    parts.append(f"{'⚠️ ' if space < 10 else ''}Свободно на Маке: {space:.0f} ГБ")
    if problems:
        parts.append(f"Ошибок: {len(problems)}, последняя: {problems[-1]}")
    return "\n".join(parts)


def alert(text: str, key: str, every_hours: float) -> None:
    """Срочное уведомление. Одинаковый key не чаще раза в every_hours, чтобы часовой прогон не заспамил."""
    try:
        sent = json.loads(ALERTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sent = {}
    if key and time.time() - sent.get(key, 0) < every_hours * 3600:
        return
    if send(f"⚠️ {text}") and key:
        sent[key] = time.time()
        ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ALERTS_FILE.write_text(json.dumps(sent), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram бот uz-avto")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup")
    commands.add_parser("test")
    rep = commands.add_parser("report")
    rep.add_argument("log", type=Path)
    rep.add_argument("--how", default="")
    rep.add_argument("--started", default="")
    rep.add_argument("--print", action="store_true", help="только показать текст, не отправлять")
    al = commands.add_parser("alert")
    al.add_argument("text")
    al.add_argument("--key", default="")
    al.add_argument("--every", type=float, default=6, help="часов между одинаковыми уведомлениями")
    args = parser.parse_args()

    if args.command == "setup":
        setup()
    elif args.command == "test":
        print("Отправлено" if send("Проверка: бот uz-avto на связи") else "Не отправилось: нет TG_BOT_TOKEN или TG_ALERT_CHAT_ID (python tg_bot.py setup)")
    elif args.command == "report":
        text = report(args.log if args.log.is_absolute() else PARSER_DIR / args.log, args.how, args.started)
        print(text) if args.print else send(text)
    elif args.command == "alert":
        alert(args.text, args.key, args.every)


if __name__ == "__main__":
    main()
