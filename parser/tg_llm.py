"""Разбор постов Telegram языковой моделью (Claude): очередь и приём результата.

То же, что llm_parse.py для Instagram, только для каналов Telegram. Модель читает очередь,
пишет ответ строками в файл, а этот скрипт проверяет ответ и сохраняет его в data/_tg/llm_parsed.json.
Потом tg_parse.py подмешивает разбор к объявлениям, а export_to_site.py выгружает их на сайт.

  python3 tg_llm.py todo            — посты, которые правила разобрали не до конца (нет марки, цены или года)
  python3 tg_llm.py catalog         — марки и модели, которые уже используются
  python3 tg_llm.py apply FILE      — проверить и сохранить разбор из файла

Формат строки в FILE (разделитель ;), пустое поле = в тексте этого нет:
  id;марка;модель;год;пробег_км;цена_usd;статус;заметка
  id как в очереди, например tg-aslauto-3837
  статус: 0 = в продаже, 1 = продано, X = пост не объявление

Нужен только стандартный Python: запускается и системным python3.
"""

import json
import re
import sys

from accounts import DATA_DIR
from llm_parse import check

TG_DIR = DATA_DIR / "_tg"
LLM_PARSED_FILE = TG_DIR / "llm_parsed.json"
MAX_PRICE_USD = 2_000_000


def load_parsed() -> dict:
    if LLM_PARSED_FILE.exists():
        return json.loads(LLM_PARSED_FILE.read_text(encoding="utf-8"))
    return {}


def all_items() -> dict[str, dict]:
    """Все разобранные правилами посты каналов (data/_tg/<канал>/parsed.json): {id: пост}."""
    result = {}
    for parsed_file in sorted(TG_DIR.glob("*/parsed.json")):
        for item in json.loads(parsed_file.read_text(encoding="utf-8")):
            result[item["id"]] = item
    return result


def needs_llm(item: dict) -> bool:
    """Объявление, у которого правила не нашли марку, цену или год."""
    return item.get("kind") == "listing" and any(item.get(key) in (None, "") for key in ("brand", "price", "year"))


def todo() -> None:
    parsed = load_parsed()
    items = [item for item in all_items().values() if item["id"] not in parsed and needs_llm(item)]
    items.sort(key=lambda item: item.get("date") or "", reverse=True)
    print(f"Не разобрано постов: {len(items)}")
    for item in items:
        text = re.sub(r"\s*\n\s*", " | ", (item.get("description") or "").strip())[:600]
        print(f"{item['id']} :: {text}")


def catalog() -> None:
    """Марки и модели из разбора ЛЛМ Telegram и Instagram: новые посты называем так же."""
    names: dict[str, set[str]] = {}
    sources = [load_parsed()]
    instagram = DATA_DIR / "llm_parsed.json"
    if instagram.exists():
        sources.append(json.loads(instagram.read_text(encoding="utf-8")))
    for source in sources:
        for item in source.values():
            if item.get("brand") and item.get("model"):
                names.setdefault(item["brand"], set()).add(item["model"])
    for brand in sorted(names):
        print(f"{brand}: {', '.join(sorted(names[brand]))}")


def price_in_text(price: int, text: str) -> bool:
    """Цена должна читаться в тексте: «27.900», «27 900», «27900$» или «27.9»."""
    joined = re.sub(r"(?<=\d)[\s.,](?=\d)", "", text)
    core = str(price).rstrip("0")
    return str(price) in joined or (len(core) >= 2 and core in joined)


def apply(file_name: str) -> None:
    items = all_items()
    parsed = load_parsed()
    saved, problems = 0, []
    for line in open(file_name, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(";", 7)
        if len(parts) != 8:
            problems.append(f"не 8 полей: {line[:60]}")
            continue
        code, brand, model, year, mileage, price, status, note = (part.strip() for part in parts)
        if code not in items:
            problems.append(f"{code}: такого поста нет")
            continue
        if status not in ("0", "1", "X") or not all(re.fullmatch(r"\d*", value) for value in (year, mileage, price)):
            problems.append(f"{code}: неверный статус, год, пробег или цена")
            continue
        # Цифры эмодзи «2️⃣7️⃣.9️⃣0️⃣0️⃣» превращаем в обычные «27.900»
        text = (items[code].get("description") or "").replace("️", "").replace("⃣", "")
        year_value = int(year) if year else None
        mileage_value = int(mileage) if mileage else None
        price_value = int(price) if price else None
        found = check(code, text, year_value, mileage_value)
        if price_value is not None and not (0 < price_value <= MAX_PRICE_USD and price_in_text(price_value, text)):
            found.append(f"{code}: цены {price_value} нет в тексте")
        if found:
            # Сомнительное поле не сохраняем, остальное берём
            problems.extend(found)
            if any("год" in p for p in found):
                year_value = None
            if any("пробег" in p for p in found):
                mileage_value = None
            if any("цен" in p for p in found):
                price_value = None
        parsed[code] = {
            "is_listing": status != "X",
            "brand": brand or None,
            "model": model or None,
            "year": year_value,
            "mileage_km": mileage_value,
            "price": price_value,
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
