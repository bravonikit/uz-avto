"""Разбор постов языковой моделью (Claude): очередь и приём результата.

Модель сама этот файл не запускает "внутри себя": она читает очередь, пишет ответ строками,
а этот скрипт проверяет ответ и сохраняет его в data/llm_parsed.json.

  python llm_parse.py todo            — показать посты, которые ещё не разобраны
  python llm_parse.py catalog         — марки и модели, которые уже используются
  python llm_parse.py apply FILE      — проверить и сохранить разбор из файла

Формат строки в FILE (разделитель ;), пустое поле = в тексте этого нет:
  shortcode;марка;модель;год;пробег_км;статус;заметка
  статус: 0 = в продаже, 1 = продано, X = пост не объявление
"""

import json
import re
import sys

from accounts import PARSER_DIR, account_dir, load_accounts

LLM_PARSED_FILE = PARSER_DIR / "data" / "llm_parsed.json"
OLDEST_YEAR, NEWEST_YEAR, MAX_MILEAGE_KM = 1990, 2027, 1_000_000


def load_parsed() -> dict:
    if LLM_PARSED_FILE.exists():
        return json.loads(LLM_PARSED_FILE.read_text(encoding="utf-8"))
    return {}


def posts_with_price() -> dict[str, dict]:
    """Все посты с ценой (те, что попадают на сайт): {shortcode: пост}."""
    result = {}
    for account in load_accounts_from_file():
        raw_file = account_dir(account) / "raw_posts.json"
        prices_file = account_dir(account) / "prices.json"
        if not raw_file.exists() or not prices_file.exists():
            continue
        prices = {item["url"]: item for item in json.loads(prices_file.read_text(encoding="utf-8"))}
        for post in json.loads(raw_file.read_text(encoding="utf-8")):
            price = prices.get(post["url"])
            if price and not price["is_announcement"] and price["price"] is not None:
                result.setdefault(post["shortcode"], post)
    return result


def load_accounts_from_file() -> list[str]:
    """Список из accounts.txt (аргументы командной строки здесь заняты командой)."""
    argv, sys.argv = sys.argv, sys.argv[:1]
    try:
        return load_accounts()
    finally:
        sys.argv = argv


def todo() -> None:
    parsed = load_parsed()
    posts = {code: post for code, post in posts_with_price().items() if code not in parsed}
    print(f"Не разобрано постов: {len(posts)}")
    for code, post in posts.items():
        text = re.sub(r"#\S+", "", post["description"])
        text = re.sub(r"\s*\n\s*", " | ", text.strip())[:600]
        print(f"{code} @{post['account']} :: {text}")


def catalog() -> None:
    """Марки и модели, которые уже есть в разборе: новые посты называем так же."""
    names: dict[str, set[str]] = {}
    for item in load_parsed().values():
        if item["brand"] and item["model"]:
            names.setdefault(item["brand"], set()).add(item["model"])
    for brand in sorted(names):
        print(f"{brand}: {', '.join(sorted(names[brand]))}")


def check(code: str, text: str, year: int | None, mileage: int | None) -> list[str]:
    """Защита от выдумок: цифры должны быть в тексте поста и в разумных границах."""
    problems = []
    joined = re.sub(r"(?<=\d)[\s.,](?=\d)", "", text)  # "37 000" → "37000"
    if year is not None:
        short = str(year)[2:]
        if not OLDEST_YEAR <= year <= NEWEST_YEAR:
            problems.append(f"{code}: год {year} вне границ")
        elif str(year) not in text and not re.search(rf"(?<!\d){short}(?!\d)", text):
            problems.append(f"{code}: года {year} нет в тексте")
    if mileage:
        core = str(mileage).rstrip("0")
        if not 0 < mileage <= MAX_MILEAGE_KM:
            problems.append(f"{code}: пробег {mileage} вне границ")
        elif core not in joined and core not in text:
            problems.append(f"{code}: пробега {mileage} нет в тексте")
    return problems


def apply(file_name: str) -> None:
    posts = posts_with_price()
    parsed = load_parsed()
    saved, problems = 0, []
    for line in open(file_name, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(";", 6)
        if len(parts) != 7:
            problems.append(f"не 7 полей: {line[:60]}")
            continue
        code, brand, model, year, mileage, status, note = (part.strip() for part in parts)
        if code not in posts:
            problems.append(f"{code}: такого поста нет")
            continue
        if status not in ("0", "1", "X") or not re.fullmatch(r"\d*", year) or not re.fullmatch(r"\d*", mileage):
            problems.append(f"{code}: неверный статус, год или пробег")
            continue
        year_value = int(year) if year else None
        mileage_value = int(mileage) if mileage else None
        found = check(code, posts[code]["description"], year_value, mileage_value)
        if found:
            # Сомнительное поле не сохраняем, остальное берём
            problems.extend(found)
            if any("год" in p for p in found):
                year_value = None
            if any("пробег" in p for p in found):
                mileage_value = None
        parsed[code] = {
            "is_listing": status != "X",
            "brand": brand or None,
            "model": model or None,
            "year": year_value,
            "mileage_km": mileage_value,
            "is_sold": status == "1",
            "note": note or None,
        }
        saved += 1
    LLM_PARSED_FILE.write_text(json.dumps(parsed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Сохранено: {saved}, всего разобрано: {len(parsed)}")
    for problem in problems:
        print("  ! " + problem)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "todo":
        todo()
    elif len(sys.argv) == 2 and sys.argv[1] == "catalog":
        catalog()
    elif len(sys.argv) == 3 and sys.argv[1] == "apply":
        apply(sys.argv[2])
    else:
        print(__doc__)
