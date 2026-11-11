"""Выгружает объявления из Instagram для сайта (тестовый режим, без базы).

Берёт:   data/<аккаунт>/raw_posts.json, data/<аккаунт>/prices.json по всем аккаунтам
Пишет:   ../src/data/instagram-listings.json  (все аккаунты в одном файле)
         ../public/ig/<shortcode>.jpg

Запуск: python export_to_site.py
"""

import json
import re
import shutil

from accounts import PARSER_DIR, account_dir, load_accounts

SITE_DIR = PARSER_DIR.parent
OUTPUT_FILE = SITE_DIR / "src" / "data" / "instagram-listings.json"
SITE_IMAGES_DIR = SITE_DIR / "public" / "ig"
# Разбор постов языковой моделью: {shortcode: {brand, model, year, mileage_km, is_sold, is_listing, note}}.
# Если пост там есть, его поля важнее регулярок ниже. Постов, которых там нет, регулярки разбирают как раньше.
LLM_PARSED_FILE = PARSER_DIR / "data" / "llm_parsed.json"
OLDEST_YEAR, NEWEST_YEAR, MAX_MILEAGE_KM = 1990, 2027, 1_000_000

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

# Строки, которые не могут быть названием машины
NOT_TITLE = re.compile(
    r"^[\d\s()+\-]{7,}$|motors?\b|@|\bto.?lo.?v|bosh\s+to|рассрочк|nasiya|^narx|^цена|^price|^yili?\b|^год\b|^sotildi|^продано",
    re.IGNORECASE,
)
# Слова в начале строки, которые не относятся к названию: "SOTUVDA — BMW X7", "Sedan: Malibu"
TITLE_PREFIX = re.compile(
    r"^(?:sotuvda|sotiladi|srochno|срочно|продается|продаётся|продаю|new|новый|новая|sedan|седан|crossover|кроссовер)\b[\s:—\-]*",
    re.IGNORECASE,
)
# Марки из двух слов и разные написания одной марки
TWO_WORD_BRANDS = {
    ("mercedes", "benz"): "Mercedes-Benz", ("mersedes", "benz"): "Mercedes-Benz",
    ("mersedez", "benz"): "Mercedes-Benz", ("land", "rover"): "Land Rover",
}
BRAND_ALIASES = {
    "mercedes-benz": "Mercedes-Benz", "mercedes-amg": "Mercedes-Benz", "mercedes": "Mercedes-Benz",
    "mersedes": "Mercedes-Benz", "chagan": "Changan", "dongfen": "Dongfeng", "leapmotors": "Leapmotor",
    "range": "Land Rover", "deepal": "Deepal", "genesis": "Genesis", "toyota": "Toyota", "lexus": "Lexus",
    "chevrolet": "Chevrolet", "kia": "Kia", "audi": "Audi", "porsche": "Porsche", "tesla": "Tesla",
}

# "Yili 2025/09", "Yili-2025/26Model" → 2025. "Yil Garantiya" сюда не подходит.
YEAR_PATTERN = re.compile(r"\byili\s*[-:]?\s*((?:19|20)\d{2})", re.IGNORECASE)
# "Probeg 20.000km", "Probeg 15.000", "Probeg 8200" → число после слова
MILEAGE_PATTERN = re.compile(r"\b(?:probeg\w*|пробег\w*)\s*[-:]?\s*(\d[\d.,]*)", re.IGNORECASE)
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
    is_sold_any = bool(lines) and bool(SOLD_PATTERN.fullmatch(lines[0]))
    lines = [TITLE_PREFIX.sub("", line).strip() for line in lines]
    lines = [line for line in lines if line and not NOT_TITLE.search(line)]
    if is_sold_any:
        # Строка "BARAKA BOLDI" сама не название: берём первую строку после неё
        lines = [line for line in lines if not SOLD_PATTERN.fullmatch(line)]
        return (lines[0] if lines else None), True
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
    pair = tuple(w.lower() for w in words[:2])
    if pair in TWO_WORD_BRANDS:
        brand, rest = TWO_WORD_BRANDS[pair], words[2:]
    else:
        first = words[0].lower()
        brand = BRAND_NAMES.get(first) or BRAND_ALIASES.get(first) or normalize_word(words[0])
        rest = words[1:]
        if first == "range":  # "Range Rover Vogue" → Land Rover, модель Range
            rest = words[:1]
    model = normalize_word(rest[0]) if rest else None
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


def load_llm_parsed() -> dict:
    if not LLM_PARSED_FILE.exists():
        return {}
    return json.loads(LLM_PARSED_FILE.read_text(encoding="utf-8"))


def apply_llm(listing: dict, parsed: dict | None) -> dict | None:
    """Подставляет в объявление поля из разбора ЛЛМ. Возвращает None, если пост не объявление."""
    if parsed is None:
        return listing
    if not parsed.get("is_listing", True):
        return None
    year, mileage = parsed.get("year"), parsed.get("mileage_km")
    # Защита от выдумок: значения вне разумных границ не берём
    if year is not None and not OLDEST_YEAR <= year <= NEWEST_YEAR:
        year = None
    if mileage is not None and not 0 <= mileage <= MAX_MILEAGE_KM:
        mileage = None
    brand, model = parsed.get("brand"), parsed.get("model")
    listing.update(brand=brand, model=model, year=year, mileage_km=mileage, is_sold=bool(parsed.get("is_sold")))
    # Название из поста оставляем, если в нём есть модель; иначе собираем "Марка Модель"
    title = re.sub(r"^(?:модель|model)\s*:\s*", "", listing["title"] or "", flags=re.IGNORECASE)
    listing["title"] = title or None
    clean_name = " ".join(part for part in (brand, model) if part)
    if clean_name and not (model and model.lower() in title.lower()):
        listing["title"] = clean_name
    return listing


def copy_image(post: dict) -> str | None:
    """Копирует картинку в public/ig/ и возвращает её адрес на сайте."""
    if not post.get("image"):
        return None
    source = PARSER_DIR / post["image"]
    if not source.exists():
        return None
    shutil.copyfile(source, SITE_IMAGES_DIR / f"{post['shortcode']}.jpg")
    return f"/ig/{post['shortcode']}.jpg"


def account_listings(account: str, llm_parsed: dict) -> list[dict]:
    """Объявления одного аккаунта (без анонсов и постов без цены)."""
    raw_file = account_dir(account) / "raw_posts.json"
    prices_file = account_dir(account) / "prices.json"
    if not raw_file.exists() or not prices_file.exists():
        print(f"  {account}: нет данных, сначала download.py и extract_price.py")
        return []
    posts = json.loads(raw_file.read_text(encoding="utf-8"))
    prices = {item["url"]: item for item in json.loads(prices_file.read_text(encoding="utf-8"))}

    listings = []
    for post in posts:
        price = prices.get(post["url"])
        if price is None or price["is_announcement"] or price["price"] is None:
            continue

        text = post["description"]
        title, is_sold = find_title(text)
        brand, model = split_title(title)
        listing = apply_llm(
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
                "source_account": account,
                "date": post["date"],
            },
            llm_parsed.get(post["shortcode"]),
        )
        if listing is not None:
            listings.append(listing)
    print(f"  {account}: {len(listings)} объявлений")
    return listings


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SITE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    llm_parsed = load_llm_parsed()
    listings, seen = [], set()
    for account in load_accounts():
        for listing in account_listings(account, llm_parsed):
            # Совместные посты приходят от двух аккаунтов с одним shortcode: берём один раз
            if listing["id"] not in seen:
                seen.add(listing["id"])
                listings.append(listing)
    # Свежие объявления первыми, вперемешку по аккаунтам
    listings.sort(key=lambda item: item["date"], reverse=True)

    OUTPUT_FILE.write_text(json.dumps(listings, ensure_ascii=False, indent=2), encoding="utf-8")

    def count(key: str) -> int:
        return sum(1 for item in listings if item[key] is not None)

    print(f"\nВыгружено объявлений: {len(listings)} → {OUTPUT_FILE.relative_to(SITE_DIR)}")
    print(f"  с годом: {count('year')}, с пробегом: {count('mileage_km')}, с фото: {count('image')}")
    print(f"  с пометкой BARAKA BOLDI (вероятно, проданы): {sum(item['is_sold'] for item in listings)}")


if __name__ == "__main__":
    main()
