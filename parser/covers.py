"""Обложки через Gemini (веб, по подписке): главное фото 3/4, вид сбоку, салон.

Скрипт открывает Gem «Мастер обложек uz-avto» в отдельном окне Chrome, загружает все фото поста,
просит «АНАЛИЗ» (какие слоты закрыты настоящими фото), потом «СДЕЛАЙ main / side / interior»
для недостающих и скачивает картинки в папку поста на Google Диске.

Первый раз (один раз):
  .venv/bin/pip install playwright
  .venv/bin/python covers.py login        — откроется Chrome, войти в nikita.express24, закрыть окно

Прогон:
  .venv/bin/python covers.py run --model tracker --limit 5
  .venv/bin/python covers.py run --ids tg-aslauto-3842 tg-azaavtoo-120
  .venv/bin/python covers.py status --model tracker
  .venv/bin/python covers.py run --model tracker --gemini Argon --level Высокий

Сравнить модели на одном посте (рисует только main, кладёт в <COVERS_DIR>/_compare/<id>/):
  .venv/bin/python covers.py compare --ids tg-autovitauz-2221 --configs "Flash-Lite:Низкий" "Argon:Высокий"

Результат: <COVERS_DIR>/<id>/ main.jpg, side.jpg, interior.jpg (только сгенерированные), slots.json.
Пост с готовым slots.json второй раз не трогается (кроме --force).
"""

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

PARSER_DIR = Path(__file__).parent
DATA_DIR = PARSER_DIR / "data"
TG_LISTINGS = DATA_DIR / "_tg" / "listings.json"
PROFILE_DIR = DATA_DIR / ".gemini_profile"
LOG_FILE = DATA_DIR / "logs" / "covers.log"
DRIVE_ROOT = Path.home() / "Library/CloudStorage/GoogleDrive-nikita.express24@gmail.com/Мой диск/uz-avto-archive"
COVERS_DIR = DRIVE_ROOT / "covers" if DRIVE_ROOT.exists() else DATA_DIR / "covers"
COMPARE_DIR = COVERS_DIR / "_compare"

GEM_URL = "https://gemini.google.com/gem/504a89406d6e"
SLOTS = ("main", "side", "interior")
ANSWER_TIMEOUT_S = 240
PAUSE_BETWEEN_POSTS_S = (25, 50)
LIMIT_WORDS = ("лимит", "limit", "quota", "попробуйте позже", "try again later", "больше не можете")


def log(message: str) -> None:
    line = f"{datetime.now():%d.%m %H:%M:%S} {message}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


# ---------- какие посты брать ----------

def load_posts(model: str | None, ids: list[str] | None) -> list[dict]:
    items = json.loads(TG_LISTINGS.read_text(encoding="utf-8"))
    result = []
    for item in items:
        if ids and item["id"] not in ids:
            continue
        if not ids:
            name = f"{item.get('brand') or ''} {item.get('model') or ''} {item.get('title') or ''}".lower()
            if item.get("is_sold") or item.get("kind") != "listing" or (model and model.lower() not in name):
                continue
        files = [PARSER_DIR / image for image in item.get("images") or []]
        files = [path.resolve() for path in files if path.exists()]
        if files:
            result.append({**item, "files": files})
    result.sort(key=lambda item: item.get("date") or "", reverse=True)
    return result


def done(post_id: str) -> bool:
    return (COVERS_DIR / post_id / "slots.json").exists()


# ---------- работа со страницей Gemini ----------

def responses(page):
    return page.locator("model-response")


def wait_answer(page, count_before: int) -> None:
    """Ждём новый ответ и его окончание (появились кнопки оценки ответа)."""
    deadline = time.time() + ANSWER_TIMEOUT_S
    while responses(page).count() <= count_before:
        if time.time() > deadline:
            raise TimeoutError("Gemini не начал отвечать")
        time.sleep(1)
    last = responses(page).last
    while last.locator('button[aria-label="Хороший ответ"]').count() == 0:
        if time.time() > deadline:
            raise TimeoutError("Gemini не закончил ответ")
        time.sleep(2)
    time.sleep(1.5)


def send(page, text: str) -> None:
    """Пишем одной строкой: перенос строки в поле Gemini отправляет сообщение."""
    box = page.locator("rich-textarea .ql-editor")
    box.click()
    page.keyboard.insert_text(" ".join(text.split()))
    time.sleep(0.5)
    count_before = responses(page).count()
    page.keyboard.press("Enter")
    wait_answer(page, count_before)


def accept_dialogs(page) -> None:
    """Разовые окна Gemini о загрузке фото: соглашаемся, если всплыли."""
    for label in ("Принять", "Согласен", "Agree", "Понятно", "Got it", "OK"):
        button = page.get_by_role("button", name=label, exact=True)
        if button.count() and button.first.is_visible():
            button.first.click()
            time.sleep(1)


def attach(page, files: list[Path]) -> None:
    page.locator('button[aria-label="Загрузка и инструменты"]').click()
    time.sleep(1)
    with page.expect_file_chooser(timeout=15000) as chooser:
        page.locator('[data-test-id="local-images-files-uploader-button"]').click()
    chooser.value.set_files([str(path) for path in files])
    accept_dialogs(page)
    # Ждём, пока превью загрузятся: даём по 3 с на фото, но не меньше 6 с
    time.sleep(max(6, 3 * len(files)))
    accept_dialogs(page)


MODE_BUTTONS = ('[data-test-id="bard-mode-menu-button"]', 'bard-mode-switcher button',
                'button:has-text("Gemini")')


def mode_button(page):
    for selector in MODE_BUTTONS:
        button = page.locator(selector)
        if button.count() and button.first.is_visible():
            return button.first
    raise RuntimeError("не нашёл кнопку выбора модели Gemini")


def choose_model(page, model: str | None, level: str | None) -> str:
    """Выбираем модель (часть подписи: Argon, Flash-Lite, Hydrogen, 3.1 Pro) и уровень рассуждений.
    Возвращаем подпись кнопки после выбора, она пишется в лог и slots.json."""
    if not model and not level:
        return mode_button(page).inner_text().replace("\n", " ").strip()
    if model:
        mode_button(page).click()
        time.sleep(1)
        page.get_by_text(model, exact=False).last.click()
        time.sleep(1.5)
    if level:
        mode_button(page).click()
        time.sleep(1)
        header = page.get_by_text("Уровень рассуждений", exact=False)
        option = page.get_by_text(level, exact=True)
        if not option.count() or not option.last.is_visible():
            if header.count():
                header.last.click()
                time.sleep(1)
        page.get_by_text(level, exact=True).last.click()
        time.sleep(1.5)
    page.keyboard.press("Escape")
    time.sleep(0.5)
    label = mode_button(page).inner_text().replace("\n", " ").strip()
    if model and model.lower() not in label.lower():
        raise RuntimeError(f"модель не переключилась: на кнопке {label!r}, хотели {model!r}")
    return label


def image_tool(page) -> None:
    """Включаем инструмент «Создать изображение», чтобы Gemini не выбрал видео (Flash-Lite так сделал 15.11)."""
    try:
        page.locator('button[aria-label="Загрузка и инструменты"]').click()
        time.sleep(1)
        option = page.get_by_text(re.compile(r"(Создать|Создание) изображени|Create image", re.I))
        if option.count() and option.first.is_visible():
            option.first.click()
        else:
            page.keyboard.press("Escape")
        time.sleep(1)
    except Exception:  # noqa: BLE001  меню могли переделать, тогда полагаемся на текст запроса
        page.keyboard.press("Escape")


def last_text(page) -> str:
    return responses(page).last.inner_text()


def parse_analysis(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"в ответе нет JSON: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def download_image(page, target: Path) -> bool:
    last = responses(page).last
    if last.locator("generated-image img, single-image img").count() == 0:
        return False
    button = last.locator('button[aria-label="Скачать изображение в полном размере"]').first
    last.locator("generated-image, single-image").first.hover()
    with page.expect_download(timeout=90000) as download:
        button.click(force=True)
    download.value.save_as(str(target))
    return True


def hit_limit(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in LIMIT_WORDS)


# ---------- один пост ----------

def process(page, post: dict, folder: Path, gemini: str | None = None, level: str | None = None,
            only_main: bool = False) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    record = {"id": post["id"], "title": post.get("title"), "files": [p.name for p in post["files"]],
              "started": datetime.now().isoformat(timespec="seconds"), "generated": {}, "errors": []}
    page.goto(GEM_URL)
    page.locator("rich-textarea .ql-editor").wait_for(timeout=30000)
    time.sleep(2)
    record["gemini_mode"] = choose_model(page, gemini, level)
    record["gemini_level"] = level
    log(f"  модель: {record['gemini_mode']}" + (f", уровень {level}" if level else ""))
    attach(page, post["files"])
    text = (post.get("description") or "")[:700]
    send(page, f"АНАЛИЗ. Фото {len(post['files'])} шт. Текст поста: {text}")
    answer = last_text(page)
    if hit_limit(answer) and "{" not in answer:
        raise RuntimeError(f"лимит Gemini: {answer[:150]}")
    analysis = parse_analysis(answer)
    record["analysis"] = analysis
    record["chat_url"] = page.url
    for slot in SLOTS:
        decision = (analysis.get("slots", {}).get(slot) or {}).get("use", "skip")
        if only_main:
            if slot != "main":
                continue
            decision = "generate"
        if decision != "generate":
            record["generated"][slot] = decision
            continue
        image_tool(page)
        send(page, f"СДЕЛАЙ {slot}. Ответ строго одна картинка (изображение), не видео и не анимация.")
        target = folder / f"{slot}.jpg"
        if download_image(page, target):
            record["generated"][slot] = target.name
            log(f"  {slot}: сгенерировано")
        else:
            reply = last_text(page)[:200]
            record["generated"][slot] = "no_image"
            record["errors"].append(f"{slot}: нет картинки, ответ: {reply!r}")
            if "видео" in reply.lower() or "video" in reply.lower():
                record["generated"][slot] = "video_instead"
                log(f"  {slot}: Gemini сделал видео вместо картинки, слот пропущен")
            else:
                log(f"  {slot}: картинки нет ({reply[:80]!r})")
            if hit_limit(reply):
                raise RuntimeError(f"лимит Gemini: {reply[:150]}")
        time.sleep(random.uniform(4, 9))
    record["finished"] = datetime.now().isoformat(timespec="seconds")
    return record


# ---------- команды ----------

def open_browser(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    context = playwright.chromium.launch_persistent_context(
        str(PROFILE_DIR), channel="chrome", headless=False, accept_downloads=True,
        viewport={"width": 1280, "height": 900}, args=["--disable-blink-features=AutomationControlled"])
    return context, (context.pages[0] if context.pages else context.new_page())


def cmd_login() -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        context, page = open_browser(playwright)
        page.goto(GEM_URL)
        input("Войдите в Google (nikita.express24) в открывшемся окне, откройте Gem и нажмите Enter здесь... ")
        context.close()


def cmd_run(args) -> None:
    from playwright.sync_api import sync_playwright
    posts = load_posts(args.model, args.ids)
    todo = [post for post in posts if args.force or not done(post["id"])][: args.limit]
    log(f"Обложки: постов подходит {len(posts)}, в работу {len(todo)}, папка {COVERS_DIR}")
    ok = failed = 0
    with sync_playwright() as playwright:
        context, page = open_browser(playwright)
        for number, post in enumerate(todo, 1):
            folder = COVERS_DIR / post["id"]
            log(f"[{number}/{len(todo)}] {post['id']} {post.get('title')} фото {len(post['files'])}")
            try:
                record = process(page, post, folder, args.gemini, args.level)
                (folder / "slots.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
                log("  итог: " + ", ".join(f"{s}={record['generated'].get(s)}" for s in SLOTS))
                ok += 1
            except Exception as error:  # noqa: BLE001  любой сбой одного поста не должен ронять прогон
                failed += 1
                folder.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(path=str(folder / "error.png"), full_page=True)
                except Exception:  # noqa: BLE001
                    pass
                (folder / "error.txt").write_text(f"{type(error).__name__}: {error}\n{page.url}\n", encoding="utf-8")
                log(f"  ОШИБКА {type(error).__name__}: {str(error)[:200]}")
                if "лимит" in str(error):
                    log("Упёрлись в лимит Gemini, остановка")
                    break
            if number < len(todo):
                time.sleep(random.uniform(*PAUSE_BETWEEN_POSTS_S))
        context.close()
    log(f"Готово: обработано {ok}, ошибок {failed}")


def safe_name(text: str) -> str:
    return re.sub(r"[^\w.-]+", "_", text).strip("_")


def cmd_compare(args) -> None:
    """Один и тот же пост в нескольких настройках Gemini, только главное фото, для сравнения глазами."""
    from playwright.sync_api import sync_playwright
    posts = load_posts(None, args.ids)
    if not posts:
        sys.exit("пост не найден: укажите --ids")
    configs = [(c.split(":", 1) + [None])[:2] for c in args.configs]
    with sync_playwright() as playwright:
        context, page = open_browser(playwright)
        for post in posts:
            base = COMPARE_DIR / post["id"]
            for model, level in configs:
                tag = safe_name(f"{model}_{level or 'default'}")
                folder = base / tag
                log(f"[compare] {post['id']} {post.get('title')} → {model} / {level}")
                try:
                    record = process(page, post, folder, model, level, only_main=True)
                    (folder / "slots.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
                    if (folder / "main.jpg").exists():
                        (base / f"main_{tag}.jpg").write_bytes((folder / "main.jpg").read_bytes())
                    plan = (record["analysis"].get("slots", {}).get("main") or {}).get("use")
                    line = f"{tag}: анализ main={plan}, модель {record['gemini_mode']}, итог {record['generated'].get('main')}"
                    log("  " + line)
                    with (base / "summary.txt").open("a", encoding="utf-8") as file:
                        file.write(line + "\n")
                except Exception as error:  # noqa: BLE001
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / "error.txt").write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
                    log(f"  ОШИБКА {type(error).__name__}: {str(error)[:200]}")
                time.sleep(random.uniform(*PAUSE_BETWEEN_POSTS_S))
            for index, path in enumerate(post["files"], 1):
                (base / f"orig_{index}{path.suffix}").write_bytes(path.read_bytes())
            log(f"  сравнение лежит в {base}")
        context.close()


def cmd_status(args) -> None:
    posts = load_posts(args.model, args.ids)
    counts = {"done": 0, "error": 0, "todo": 0}
    generated = {slot: 0 for slot in SLOTS}
    for post in posts:
        folder = COVERS_DIR / post["id"]
        if (folder / "slots.json").exists():
            counts["done"] += 1
            record = json.loads((folder / "slots.json").read_text(encoding="utf-8"))
            for slot in SLOTS:
                generated[slot] += str(record["generated"].get(slot, "")).endswith(".jpg")
        elif (folder / "error.txt").exists():
            counts["error"] += 1
        else:
            counts["todo"] += 1
    print(f"Постов {len(posts)}: готово {counts['done']}, с ошибкой {counts['error']}, не трогали {counts['todo']}")
    print("Сгенерировано: " + ", ".join(f"{slot} {n}" for slot, n in generated.items()))
    print(f"Папка: {COVERS_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["login", "run", "status", "compare"])
    parser.add_argument("--model", help="часть названия модели, например tracker")
    parser.add_argument("--ids", nargs="*", help="конкретные id постов")
    parser.add_argument("--limit", type=int, default=5, help="сколько постов за прогон (по умолчанию 5)")
    parser.add_argument("--force", action="store_true", help="переделать посты, где уже есть slots.json")
    parser.add_argument("--gemini", help="модель в меню Gemini: Argon, Flash-Lite, Hydrogen, Carbon, \"3.1 Pro\"")
    parser.add_argument("--level", help="уровень рассуждений: Низкий, Средний, Высокий")
    parser.add_argument("--configs", nargs="*", default=["Flash-Lite:Низкий", "Argon:Высокий"],
                        help="для compare: модель:уровень через пробел")
    args = parser.parse_args()
    if args.command == "login":
        cmd_login()
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "compare":
        cmd_compare(args)
    else:
        cmd_status(args)


if __name__ == "__main__":
    sys.exit(main())
