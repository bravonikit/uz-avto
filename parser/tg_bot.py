"""Telegram бот проекта: уведомления Нику по каждому этапу прогона и воронка дня.

Настройка (один раз):
  1. В Telegram у @BotFather: /newbot, токен в parser/.env строкой TG_BOT_TOKEN=...
  2. Напишите боту /start. Если канал уже создан: добавьте бота админом канала с правом публикации
     и опубликуйте в канале любое сообщение (потом его можно удалить).
  3. python tg_bot.py setup  → находит ваш чат и канал, дописывает в .env TG_ALERT_CHAT_ID и TG_CHANNEL

Что приходит:
  * ежедневный прогон (run_daily.sh): сообщение после каждого этапа (скачка, разбор, видео, сайт,
    архив, карточки) и в конце итог: воронка за вчера (полный день) и за сегодня
  * часовой прогон: воронка «сегодня пока», только если за час были новые посты, без звука
  * видеопрогон: одна строка итога, без звука
  * мало места: срочно, не чаще раза в 6 часов
  Выключить часовые: TG_HOURLY=0 в .env, видео: TG_VIDEO=0.

Команды:
  python tg_bot.py setup | test
  python tg_bot.py stage ИМЯ --log ЛОГ        сообщение об этапе (raw, parse, video, site, archive, cards)
  python tg_bot.py report ЛОГ                 итог прогона с воронкой
  python tg_bot.py funnel [--day 2026-11-18]  воронка за день (--print: только показать)
  python tg_bot.py hourly ЛОГ | videorun ЛОГ
  python tg_bot.py alert "текст" --key space

Без токена все команды молча ничего не делают: прогон парсера от бота не зависит.
Постинг картинок дня в канал делает сайт: кнопка «Опубликовать в канал» в /admin/daily.
Сеть через requests (как весь парсер); без него стандартный urllib.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PARSER_DIR = Path(__file__).resolve().parent
ENV_FILE = PARSER_DIR / ".env"
DATA_DIR = PARSER_DIR / "data"
TG_DIR = DATA_DIR / "_tg"
CARDS_DIR = DATA_DIR / "_cards"
LOG_DIR = DATA_DIR / "logs"
SITE_FILE = PARSER_DIR.parent / "src" / "data" / "instagram-listings.json"
ALERTS_FILE = DATA_DIR / ".tg_alerts.json"
MESSAGE_LIMIT = 4096
TASHKENT = timezone(timedelta(hours=5))


# ---------- настройки и отправка ----------

def settings() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", line)
            if match:
                values[match[1]] = match[2].strip("'\"")
    return values


def set_env(key: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [line for line in lines if not re.match(rf"^\s*{key}\s*=", line)] + [f"{key}={value}"]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def call(token: str, method: str, **payload):
    """Запрос к Telegram. Через requests, как весь парсер: у него свои сертификаты (certifi).
    Python с python.org на Маке системных сертификатов не видит, и голый urllib падает на SSL.
    Нет requests: urllib с сертификатами certifi, если он есть."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        import requests
    except ImportError:
        requests = None
    if requests is not None:
        data = requests.post(url, json=payload, timeout=30).json()
    else:
        import ssl
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as error:
            data = json.loads(error.read() or b"{}")
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or "Telegram не ответил")
    return data["result"]


def send(text: str, silent: bool = False) -> bool:
    """Сообщение Нику. False, если бот не настроен или Telegram не ответил (прогон из за этого не падает)."""
    env = settings()
    token, chat = env.get("TG_BOT_TOKEN"), env.get("TG_ALERT_CHAT_ID")
    if not token or not chat or not text.strip():
        return False
    try:
        call(token, "sendMessage", chat_id=chat, text=text[:MESSAGE_LIMIT], disable_notification=silent,
             link_preview_options={"is_disabled": True})
        return True
    except Exception as error:  # сеть, неверный токен: пишем в лог и идём дальше
        print(f"Telegram бот: не отправилось ({error})")
        return False


def setup() -> None:
    env = settings()
    token = env.get("TG_BOT_TOKEN")
    if not token:
        raise SystemExit("В parser/.env нет TG_BOT_TOKEN. Создайте бота у @BotFather и добавьте строку TG_BOT_TOKEN=...")
    me = call(token, "getMe")
    print(f"Бот: @{me['username']}")
    updates = call(token, "getUpdates", allowed_updates=["message", "channel_post", "my_chat_member"])
    private = channel = None
    for update in updates:
        for kind in ("message", "channel_post", "my_chat_member"):
            chat = (update.get(kind) or {}).get("chat")
            if chat and chat["type"] == "private":
                private = chat
            elif chat and chat["type"] == "channel":
                channel = chat
    if private:
        set_env("TG_ALERT_CHAT_ID", str(private["id"]))
        print(f"Уведомления: чат с {private.get('first_name', '')} ({private['id']}) записан в .env")
    elif not env.get("TG_ALERT_CHAT_ID"):
        print(f"Личный чат не найден: напишите боту @{me['username']} /start и запустите setup ещё раз")
    if channel:
        value = f"@{channel['username']}" if channel.get("username") else str(channel["id"])
        set_env("TG_CHANNEL", value)
        print(f"Канал: {channel.get('title', '')} ({value}) записан в .env")
    elif not env.get("TG_CHANNEL"):
        print("Канал не найден: добавьте бота админом канала, опубликуйте там любое сообщение и запустите setup ещё раз.\n"
              "Или впишите в .env строку TG_CHANNEL=@имя_канала руками")
    if send("Бот uz-avto подключён. Сюда будут приходить этапы прогона, воронка дня и срочные уведомления."):
        print("Проверочное сообщение отправлено")


# ---------- лог прогона ----------

def last_block(path: Path, start: str = "старт") -> list[str]:
    """Строки последнего прогона в логе: от последней строки «===== ... старт» до конца файла."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("=====") and start in line]
    return lines[starts[-1]:] if starts else lines


def last(lines: list[str], pattern: str) -> str | None:
    for line in reversed(lines):
        if re.search(pattern, line):
            return line.strip()
    return None


def errors(lines: list[str]) -> list[str]:
    found = []
    for i, line in enumerate(lines):
        if line.startswith("Traceback"):
            tail = next((x for x in lines[i + 1:i + 60] if re.match(r"^[A-Za-z0-9_.]+(Error|Exception)\b", x)), "ошибка без текста")
            found.append(tail.strip()[:200])
    return found


def free_gb() -> float:
    return shutil.disk_usage(PARSER_DIR).free / 1024 ** 3


# ---------- воронка дня по данным ----------

def local_day(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        moment = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(TASHKENT).date().isoformat()


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def video_places():
    """Places из tg_video.py: где лежат ролики и раскадровка. Не загрузилось (нет Диска, пакетов): None."""
    try:
        from tg_video import Places
        return Places()
    except Exception:
        return None


def funnel(day: str) -> dict:
    """Все этапы за день: сколько постов вышло у продавцов, сколько скачано, разобрано, на сайте, обработано, потрачено."""
    raw = Counter()
    channels = set()
    video_posts = []
    for posts_file in TG_DIR.glob("*/posts.json"):
        posts = load_json(posts_file, {})
        for post in (posts.values() if isinstance(posts, dict) else posts):
            if local_day(post.get("date")) != day:
                continue
            raw["posts"] += 1
            channels.add(post.get("channel") or posts_file.parent.name)
            if post.get("images"):
                raw["with_photos"] += 1
                raw["photos"] += len(post["images"])
            if post.get("video_url") or post.get("video_thumbs") or post.get("type") == "video":
                raw["videos"] += 1
                raw["heavy"] += 0 if post.get("video_url") else 1
                video_posts.append((post.get("channel") or posts_file.parent.name, post.get("id")))
            if post.get("removed_at"):
                raw["removed"] += 1
            if post.get("history"):
                raw["edited"] += 1
    raw["channels"] = len(channels)

    places = video_places()
    if places is not None and places.archive is not None:
        for channel, post_id in video_posts:
            try:
                if places.raw(channel, post_id).exists():
                    raw["videos_got"] += 1
                if (places.cut(channel, post_id) / "meta.json").exists():
                    raw["videos_cut"] += 1
            except Exception:
                pass
    raw["video_known"] = places is not None and places.archive is not None

    parsed = Counter()
    for item in load_json(TG_DIR / "listings.json", []):
        if local_day(item.get("first_posted") or item.get("date")) != day:
            continue
        parsed[item.get("kind") or "?"] += 1
        if item.get("kind") == "listing":
            parsed["priced"] += 1 if item.get("price") else 0
            parsed["sold"] += 1 if item.get("is_sold") else 0

    site = Counter()
    for item in load_json(SITE_FILE, []):
        if local_day(item.get("first_posted") or item.get("date")) != day:
            continue
        site["total"] += 1
        site["priced"] += 1 if item.get("price") else 0
        site["below"] += 1 if item.get("price_label") == "below" else 0
        site["sold"] += 1 if item.get("is_sold") else 0

    cards = None
    state = load_json(CARDS_DIR / day / "state.json", None)
    if state:
        jobs = state.get("jobs") or {}
        photo = state.get("photo") or []
        cards = {
            "listings": state.get("listings") or 0,
            "photo": len(photo),
            "video": len(state.get("video") or []),
            "ready_cover": sum(1 for row in photo if row.get("verdict") == "готово"),
            "outpaint": (jobs.get("outpaint") or {}).get("got", 0),
            "video_done": (jobs.get("video") or {}).get("got", 0),
            "grids": (jobs.get("grid") or {}).get("got", 0),
            "texts": (jobs.get("text") or {}).get("got", 0),
            "cost": sum((info or {}).get("cost") or 0 for info in jobs.values()),
            "waiting": [name for name, info in jobs.items() if info and not info.get("collected", info.get("got") is not None)],
            "published": bool(state.get("published")),
        }
    return {"day": day, "raw": raw, "parsed": parsed, "site": site, "cards": cards}


def spent_total(month: str | None = None) -> float:
    total = 0.0
    for path in CARDS_DIR.glob("*/state.json"):
        if month and not path.parent.name.startswith(month):
            continue
        jobs = (load_json(path, {}) or {}).get("jobs") or {}
        total += sum((info or {}).get("cost") or 0 for info in jobs.values())
    return total


def pct(part: int, whole: int) -> str:
    return f" ({round(100 * part / whole)}%)" if whole else ""


def human_day(day: str) -> str:
    return datetime.fromisoformat(day).strftime("%d.%m")


def funnel_text(data: dict, title: str) -> str:
    raw, parsed, site, cards = data["raw"], data["parsed"], data["site"], data["cards"]
    lines = [f"📊 {title} ({human_day(data['day'])})"]
    lines.append(f"1. Сырые: постов {raw['posts']} из {raw['channels']} каналов, с фото {raw['with_photos']} "
                 f"(фото {raw['photos']}), с видео {raw['videos']}"
                 + (f", правок {raw['edited']}" if raw["edited"] else "") + (f", удалено {raw['removed']}" if raw["removed"] else ""))
    if raw["videos"]:
        if raw["video_known"]:
            lines.append(f"2. Видео: скачано {raw['videos_got']} из {raw['videos']}{pct(raw['videos_got'], raw['videos'])}"
                         f" (тяжёлых {raw['heavy']}), раскадровано {raw['videos_cut']}")
        else:
            lines.append(f"2. Видео: роликов {raw['videos']}, тяжёлых {raw['heavy']} (Диск не виден, скачанное не посчитать)")
    else:
        lines.append("2. Видео: роликов нет")
    lines.append(f"3. Разбор: объявлений {parsed['listing']}{pct(parsed['listing'], raw['posts'])}, под заказ {parsed['catalog']}, "
                 f"с ценой {parsed['priced']}, уже продано {parsed['sold']}")
    lines.append(f"4. На сайте: {site['total']}, с ценой {site['priced']}, ниже рынка {site['below']}, продано {site['sold']}")
    if cards:
        state = "выложено на сайт" if cards["published"] else ("ждём Google: " + ", ".join(cards["waiting"]) if cards["waiting"] else "в работе")
        lines.append(f"5. Карточки: в обработку {cards['photo']} с фото и {cards['video']} с видео; обложек обрезкой {cards['ready_cover']}, "
                     f"дорисовано {cards['outpaint']}, из видео {cards['video_done']}, сеток {cards['grids']}, описаний {cards['texts']}; {state}")
        lines.append(f"💸 Потрачено за день: ${cards['cost']:.2f}")
    else:
        lines.append("5. Карточки: ещё не запускались (обработка идёт на следующий день)")
    month = data["day"][:7]
    lines.append(f"💰 Карточки за месяц: ${spent_total(month):.2f}, всего: ${spent_total():.2f}")
    return "\n".join(lines)


def today() -> str:
    return datetime.now(TASHKENT).date().isoformat()


def yesterday() -> str:
    return (datetime.now(TASHKENT).date() - timedelta(days=1)).isoformat()


# ---------- сообщения по этапам ----------

STAGES = {
    # имя: (заголовок, шаблоны строк лога, которые показываем)
    "raw": ("⬇️ Скачка", [r"^Готово: \d+ из \d+ аккаунтов", r"^Telegram( \(часовой\))? готово:", r"не подключился", r"Прогон остановлен"]),
    "parse": ("🧩 Разбор", [r"^После склейки дублей", r"^\s+у машин:", r"^\s+проданы \d+", r"^Объявлений: \d+"]),
    "video": ("🎬 Видео", [r"^Видео"]),
    "site": ("🌐 Сайт", [r"^Выгружено объявлений", r"оценка цены:", r"одна машина у разных продавцов", r"подозрительных цен"]),
    "archive": ("🗂 Архив", [r"перенесено в архив", r"резервная копия", r"Диск не принимает", r"Архив не настроен"]),
    "cards": ("🖼 Карточки", [r"в обработку с фото", r"Карточки за", r"Прогон карточек остановлен", r"Ответы пришли не все", r"Обрабатывать нечего"]),
}


def stage(name: str, log: Path) -> str:
    title, patterns = STAGES[name]
    lines = last_block(log)
    shown = []
    for pattern in patterns:
        line = last(lines, pattern)
        if line and line not in shown:
            line = line.split(" → ")[0].split(". Папка:")[0]
            # Instagram на паузе: его строки подписываем, чтобы не путать с Telegram
            line = re.sub(r"^Готово: (\d+ из \d+ аккаунтов)", r"Instagram: \1", line)
            line = re.sub(r"^Объявлений: (\d+)\. Заполнено", r"Instagram объявлений: \1. Заполнено", line)
            shown.append(line)
    data = funnel(today())
    raw, parsed, site = data["raw"], data["parsed"], data["site"]
    day_line = {
        "raw": f"За сегодня: постов {raw['posts']} из {raw['channels']} каналов, фото {raw['photos']}, видео {raw['videos']}",
        "parse": f"За сегодня: объявлений {parsed['listing']}, под заказ {parsed['catalog']}, с ценой {parsed['priced']}",
        "video": (f"За сегодня: скачано {raw['videos_got']} из {raw['videos']}, раскадровано {raw['videos_cut']}"
                  if raw["video_known"] else f"За сегодня роликов {raw['videos']}"),
        "site": f"За сегодня на сайте: {site['total']}, ниже рынка {site['below']}",
        "archive": f"Свободно на Маке: {free_gb():.0f} ГБ",
        "cards": "",
    }[name]
    if name == "cards":
        y = funnel(yesterday())["cards"]
        day_line = (f"За {human_day(yesterday())}: потрачено ${y['cost']:.2f}" if y else "")
    body = shown or ["нет строк итога в логе (этап пропущен или упал)"]
    return "\n".join([title, *body, day_line]).strip()


def report(log: Path, how: str = "", started: str = "") -> str:
    lines = last_block(log)
    finished = any(line.startswith("=====") and "конец" in line for line in lines)
    stopped = last(lines, r"Прогон остановлен|Прогон карточек остановлен")
    problems = errors(lines)
    status = "✅" if finished and not stopped and not problems else "⚠️"
    head = [f"{status} Прогон {started or log.stem}{f' ({how})' if how else ''} закончен"]
    if not finished:
        head.append(f"Прогон не дошёл до конца, лог {log.relative_to(PARSER_DIR)}")
    if stopped:
        head.append(stopped)
    if problems:
        head.append(f"Ошибок: {len(problems)}, последняя: {problems[-1]}")
    space = free_gb()
    head.append(f"{'⚠️ ' if space < 10 else ''}Свободно на Маке: {space:.0f} ГБ")
    return "\n\n".join([
        "\n".join(head),
        funnel_text(funnel(yesterday()), "Воронка за вчера"),
        funnel_text(funnel(today()), "Сегодня пока"),
    ])


def hourly(log: Path) -> str | None:
    """Воронка «сегодня пока», если с прошлого часового прибавились посты. Счётчик дня в data/.tg_alerts.json."""
    data = funnel(today())
    posts = data["raw"]["posts"]
    sent = load_json(ALERTS_FILE, {})
    before = sent.get("hourly_posts", {}).get(today(), 0)
    if posts <= before:
        return None
    sent["hourly_posts"] = {today(): posts}
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALERTS_FILE.write_text(json.dumps(sent), encoding="utf-8")
    problems = errors(last_block(log, "часовой"))
    return "\n".join([f"⏱ Часовой: +{posts - before} постов", funnel_text(data, "Сегодня пока"),
                      *([f"Ошибок: {len(problems)}, последняя: {problems[-1]}"] if problems else [])])


def videorun(log: Path) -> str | None:
    lines = last_block(log, "видео: старт")
    shown = [line.strip().split(". Папка:")[0] for line in lines if line.startswith("Видео")]
    problems = errors(lines)
    if not shown and not problems:
        return None
    return "\n".join(["🎬 Видеопрогон", *shown[-3:], *([f"Ошибок: {len(problems)}, последняя: {problems[-1]}"] if problems else [])])


def alert(text: str, key: str, every_hours: float) -> None:
    """Срочное уведомление. Одинаковый key не чаще раза в every_hours, чтобы часовой прогон не заспамил."""
    sent = load_json(ALERTS_FILE, {})
    if key and time.time() - sent.get(key, 0) < every_hours * 3600:
        return
    if send(f"⚠️ {text}") and key:
        sent[key] = time.time()
        ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ALERTS_FILE.write_text(json.dumps(sent), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram бот uz-avto")
    parser.add_argument("--print", action="store_true", help="только показать текст, не отправлять")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup")
    commands.add_parser("test")
    st = commands.add_parser("stage")
    st.add_argument("name", choices=list(STAGES))
    st.add_argument("--log", type=Path, required=True)
    rep = commands.add_parser("report")
    rep.add_argument("log", type=Path)
    rep.add_argument("--how", default="")
    rep.add_argument("--started", default="")
    fu = commands.add_parser("funnel")
    fu.add_argument("--day", default=None, help="ГГГГ-ММ-ДД, по умолчанию вчера")
    for name in ("hourly", "videorun"):
        commands.add_parser(name).add_argument("log", type=Path)
    al = commands.add_parser("alert")
    al.add_argument("text")
    al.add_argument("--key", default="")
    al.add_argument("--every", type=float, default=6, help="часов между одинаковыми уведомлениями")
    args = parser.parse_args()

    def path(value: Path) -> Path:
        return value if value.is_absolute() else PARSER_DIR / value

    def out(text: str | None, silent: bool = False) -> None:
        if text:
            print(text) if args.print else send(text, silent=silent)

    env = settings()
    if args.command == "setup":
        setup()
    elif args.command == "test":
        print("Отправлено" if send("Проверка: бот uz-avto на связи") else "Не отправилось: нет TG_BOT_TOKEN или TG_ALERT_CHAT_ID (python tg_bot.py setup)")
    elif args.command == "stage":
        out(stage(args.name, path(args.log)), silent=True)
    elif args.command == "report":
        out(report(path(args.log), args.how, args.started))
    elif args.command == "funnel":
        day = args.day or yesterday()
        out(funnel_text(funnel(day), "Воронка"))
    elif args.command == "hourly" and env.get("TG_HOURLY", "1") != "0":
        out(hourly(path(args.log)), silent=True)
    elif args.command == "videorun" and env.get("TG_VIDEO", "1") != "0":
        out(videorun(path(args.log)), silent=True)
    elif args.command == "alert":
        alert(args.text, args.key, args.every)


if __name__ == "__main__":
    main()
