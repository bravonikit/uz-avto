"""Выгружает объявления из Instagram для сайта (тестовый режим, без базы).

Берёт:   data/raw_posts.json, data/prices.json
Пишет:   ../src/data/instagram-listings.json
         ../public/ig/<shortcode>.jpg

Запуск: python export_to_site.py
"""

import json
import re
import shutil
from pathlib import Path

from download import PROFILE

PARSER_DIR = Path(__file__).parent
SITE_DIR = PARSER_DIR.parent
RAW_POSTS_FILE = PARSER_DIR / "data" / "raw_posts.json"
PRICES_FILE = PARSER_DIR / "data" / "prices.json"
OUTPUT_FILE = SITE_DIR / "src" / "data" / "instagram-listings.json"
SITE_IMAGES_DIR = SITE_DIR / "public" / "ig"

# Первая строка проданных машин — это не название, пропускаем её
SOLD_PATTERN = re.compile(r"baraka\s+boldi", re.IGNORECASE)

# Единое написание марок: ключ — как пишут в постах (в нижнем регистре)
BRAND_NAMES = {
    "zeekr": "Zeekr",
    "byd": "BYD",
    "lixiang": "Lixiang",
    "nio": "NIO",
    "onvo": "ONVO",
    "bmw": "BMW",
    "gac": "GAC",
    "x-peng": "XPeng",
}

# "Yili 2025/09", "Yili-2025/26Model" → 2025. "Yil Garantiya" сюда не подходит.
YEAR_PATTERN = re.compile(r"\byili\s*[-:]?\s*((?:19|20)\d{2})", re.IGNORECASE)
# "Probeg 20.000km", "Probeg 15.000", "Probeg 8200" → число после слова
MILEAGE_PATTERN = re.compile(r"\bprobeg\s*[-:]?\s*(\d[\d.,]*)", re.IGNORECASE)
NO_MILEAGE_PATTERN = re.compile(r"\bbez\s+probeg", re.IGNORECASE)


def clean_line(line: str) -> str:
    """Убирает эмодзи и лишние символы по краям: "BARAKA BOLDI🤝" → "BARAKA BOLDI"."""
    return re.sub(r"^[^\w]+|[^\w+)]+$", "", line.strip())


def find_title(text: str) -> tuple[str | None, bool]:
    """Название машины = первая непустая строка, не считая "BARAKA BOLDI".

    Возвращает (название, продана ли машина).
    """
    lines = [clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    is_sold = bool(lines) and bool(SOLD_PATTERN.fullmatch(lines[0]))
    if is_sold:
        lines = lines[1:]
    return (lines[0] if lines else None), is_sold


def normalize_word(word: str) -> str:
    """"TANG" → "Tang", но "BYD", "7X", "L7" и "001" не трогаем."""
    if word.isalpha() and word.isupper() and len(word) > 3:
        return word.capitalize()
    return word


def split_title(title: str | None) -> tuple[str | None, str | None]:
    """"Zeekr 001 WE 100kWh" → ("Zeekr", "001"): марка — первое слово, модель — второе."""
    words = (title or "").split()
    if not words:
        return None, None
    brand = BRAND_NAMES.get(words[0].lower(), normalize_word(words[0]))
    model = normalize_word(words[1]) if len(words) > 1 else None
    return brand, model


def find_year(text: str) -> int | None:
    match = YEAR_PATTERN.search(text)
    return int(match.group(1)) if match else None


def find_mileage(text: str) -> int | None:
    if NO_MILEAGE_PATTERN.search(text):
        return 0
    match = MILEAGE_PATTERN.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def copy_image(post: dict) -> str | None:
    """Копирует картинку в public/ig/ и возвращает её адрес на сайте."""
    if not post.get("image"):
        return None
    source = PARSER_DIR / post["image"]
    if not source.exists():
        return None
    shutil.copyfile(source, SITE_IMAGES_DIR / f"{post['shortcode']}.jpg")
    return f"/ig/{post['shortcode']}.jpg"


def main() -> None:
    posts = json.loads(RAW_POSTS_FILE.read_text(encoding="utf-8"))
    prices = {item["url"]: item for item in json.loads(PRICES_FILE.read_text(encoding="utf-8"))}

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SITE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    listings = []
    for post in posts:
        price = prices.get(post["url"])
        if price is None or price["is_announcement"]:
            continue

        text = post["description"]
        title, is_sold = find_title(text)
        brand, model = split_title(title)
        listings.append(
            {
                "id": post["shortcode"],
                "title": title,
                "brand": brand,
                "model": model,
                "year": find_year(text),
                "mileage_km": find_mileage(text),
                "price": price["price"],
                "currency": price["currency"],
                "image": copy_image(post),
                "description": text,
                "is_sold": is_sold,
                "source_url": post["url"],
                "source_account": PROFILE,
                "date": post["date"],
            }
        )

    OUTPUT_FILE.write_text(json.dumps(listings, ensure_ascii=False, indent=2), encoding="utf-8")

    def count(key: str) -> int:
        return sum(1 for item in listings if item[key] is not None)

    print(f"Выгружено объявлений: {len(listings)} → {OUTPUT_FILE.relative_to(SITE_DIR)}")
    print(f"  с годом: {count('year')}, с пробегом: {count('mileage_km')}, с фото: {count('image')}")
    print(f"  с пометкой BARAKA BOLDI (вероятно, проданы): {sum(item['is_sold'] for item in listings)}")


if __name__ == "__main__":
    main()
