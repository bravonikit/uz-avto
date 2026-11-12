"""Выгружает объявления из Instagram для сайта (тестовый режим, без базы).

Берёт:   data/<аккаунт>/raw_posts.json, data/<аккаунт>/prices.json по всем аккаунтам
Пишет:   ../src/data/instagram-listings.json  (все аккаунты в одном файле)
         ../public/ig/<shortcode>.jpg

Запуск: python export_to_site.py
"""

import json
import re
import shutil
from datetime import datetime
from statistics import median

from accounts import PARSER_DIR, account_dir, load_accounts

SITE_DIR = PARSER_DIR.parent
OUTPUT_FILE = SITE_DIR / "src" / "data" / "instagram-listings.json"
SITE_IMAGES_DIR = SITE_DIR / "public" / "ig"
# Разбор постов языковой моделью: {shortcode: {brand, model, year, mileage_km, is_sold, is_listing, note}}.
# Если пост там есть, его поля важнее регулярок ниже. Постов, которых там нет, регулярки разбирают как раньше.
LLM_PARSED_FILE = PARSER_DIR / "data" / "llm_parsed.json"
OLDEST_YEAR, NEWEST_YEAR, MAX_MILEAGE_KM = 1990, 2027, 1_000_000

# Фильтр странных цен. Подозрительную цену на сайте не показываем («Цена по запросу»),
# само объявление остаётся. Список для проверки: data/price_suspects.json.
PRICE_SUSPECTS_FILE = PARSER_DIR / "data" / "price_suspects.json"
# Ручные решения после проверки: {"shortcode": 79900} задаёт цену, {"shortcode": null} убирает её.
# Цена из этого файла больше не проверяется.
PRICE_OVERRIDES_FILE = PARSER_DIR / "data" / "price_overrides.json"
CHEAP_PRICE, CHEAP_SINCE_YEAR = 3_000, 2015  # машина с 2015 года дешевле 3000$: скорее взнос или опция
ANALOG_YEARS = 2  # аналоги: та же марка и модель, год отличается не больше чем на 2
MIN_ANALOGS = 2
TOO_CHEAP, TOO_EXPENSIVE = 0.45, 2.2  # во сколько раз цена может отличаться от медианы аналогов

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
    # Если модель не определена, строка из поста ("Byd Champion Hybrid") полезнее одной марки
    known_part = model or brand
    keep_post_title = bool(title) and bool(known_part) and known_part.lower() in title.lower()
    if clean_name and not keep_post_title:
        listing["title"] = clean_name
    return listing


# Дубли внутри одного аккаунта: продавец выложил одну машину несколько раз.
SAME_TEXT_MIN_LENGTH = 20  # короче этого текст слишком общий ("Malibu 2025"), по нему не сравниваем
DIFFERENT_CARS_HOURS = 12  # два поста подряд с разной ценой: это две машины, а не смена цены


def text_key(text: str) -> str:
    """Текст без хэштегов, пробелов и эмодзи: одинаковые посты дают одинаковый ключ."""
    return re.sub(r"\W+", "", re.sub(r"#\S+", "", text)).lower()


def hours_between(first: dict, second: dict) -> float:
    dates = [datetime.fromisoformat(item["date"].replace("Z", "+00:00")) for item in (first, second)]
    return abs((dates[0] - dates[1]).total_seconds()) / 3600


def same_car(first: dict, second: dict) -> bool:
    """Два объявления одного аккаунта про одну и ту же машину?

    Да, если текст совпадает полностью. Или если это машина с пробегом и совпали марка,
    модель, год и пробег. Новые машины (пробег 0 или не указан) с разным текстом не склеиваем:
    у салона может стоять несколько одинаковых.
    """
    if first["source_account"] != second["source_account"]:
        return False
    text = text_key(first["description"])
    if len(text) >= SAME_TEXT_MIN_LENGTH and text == text_key(second["description"]):
        return True
    keys = ("brand", "model", "year", "mileage_km")
    if any(first[key] != second[key] or not first[key] for key in keys):
        return False
    prices_differ = None not in (first["price"], second["price"]) and first["price"] != second["price"]
    if prices_differ and not (first["is_sold"] or second["is_sold"]):
        # Цену меняют через дни. Два поста подряд с разной ценой: две разные машины
        return hours_between(first, second) >= DIFFERENT_CARS_HOURS
    return True


def merge_account_duplicates(listings: list[dict]) -> tuple[list[dict], int]:
    """Оставляет по одному объявлению на машину у каждого продавца: самое свежее.

    Если хотя бы один из постов помечен «продано», машина считается проданной.
    Если в свежем посте нет цены, года или пробега, они берутся из старого.
    Коды убранных постов остаются в поле duplicate_ids.
    Возвращает (объявления, сколько дублей убрано).
    """
    kept: list[dict] = []
    by_account: dict[str, list[dict]] = {}
    removed = 0
    for item in sorted(listings, key=lambda item: item["date"], reverse=True):
        item["duplicate_ids"] = []
        main = next((other for other in by_account.get(item["source_account"], []) if same_car(other, item)), None)
        if main is None:
            kept.append(item)
            by_account.setdefault(item["source_account"], []).append(item)
            continue
        removed += 1
        main["duplicate_ids"].append(item["id"])
        main["is_sold"] = main["is_sold"] or item["is_sold"]
        for key in ("price", "currency", "down_payment", "year", "mileage_km", "image"):
            if main[key] is None:
                main[key] = item[key]
    return kept, removed


def load_price_overrides() -> dict:
    if not PRICE_OVERRIDES_FILE.exists():
        return {}
    return json.loads(PRICE_OVERRIDES_FILE.read_text(encoding="utf-8"))


def find_price_suspects(listings: list[dict], checked: set[str]) -> dict[str, str]:
    """Объявления со странной ценой: {shortcode: причина}. checked — цены, проверенные вручную."""
    suspects = {}
    for item in listings:
        price, year = item["price"], item["year"]
        if price is None or item["id"] in checked:
            continue
        if price < CHEAP_PRICE and year is not None and year >= CHEAP_SINCE_YEAR:
            suspects[item["id"]] = f"машина {year} года дешевле {CHEAP_PRICE}$"
            continue
        if not (item["brand"] and item["model"] and year):
            continue
        analogs = [
            other["price"]
            for other in listings
            if other is not item
            and other["price"] is not None
            and (other["brand"], other["model"]) == (item["brand"], item["model"])
            and other["year"] is not None
            and abs(other["year"] - year) <= ANALOG_YEARS
            and other["source_account"] != item["source_account"]
        ]
        if len(analogs) < MIN_ANALOGS:
            continue
        typical = median(analogs)
        if price < typical * TOO_CHEAP or price > typical * TOO_EXPENSIVE:
            side = "ниже" if price < typical else "выше"
            suspects[item["id"]] = f"в {max(price, typical) / min(price, typical):.1f} раза {side} аналогов (медиана {typical:.0f}$ по {len(analogs)} шт.)"
    return suspects


def hide_suspect_prices(listings: list[dict]) -> list[dict]:
    """Применяет ручные цены, прячет подозрительные и сохраняет их список для проверки."""
    overrides = load_price_overrides()
    for item in listings:
        if item["id"] in overrides:
            item["price"] = overrides[item["id"]]
            item["currency"] = "USD" if item["price"] is not None else None
    suspects = find_price_suspects(listings, set(overrides))
    report = []
    for item in listings:
        reason = suspects.get(item["id"])
        if reason:
            report.append(
                {
                    "id": item["id"], "account": item["source_account"], "title": item["title"],
                    "year": item["year"], "price": item["price"], "reason": reason, "url": item["source_url"],
                }
            )
            item["price"], item["currency"] = None, None
    PRICE_SUSPECTS_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


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
    """Объявления одного аккаунта (без анонсов).

    Пост без цены попадает на сайт, только если ЛЛМ разобрала его и признала объявлением.
    """
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
        if price is None or price["is_announcement"]:
            continue
        parsed = llm_parsed.get(post["shortcode"])
        if price["price"] is None and not (parsed and parsed.get("is_listing", True)):
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
                "down_payment": price.get("down_payment"),
                "image": copy_image(post),
                "description": text,
                "is_sold": is_sold,
                "source_url": post["url"],
                "source_account": account,
                "date": post["date"],
            },
            parsed,
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
    # Свежие первыми. Дубли убираем до проверки цен
    listings, duplicates = merge_account_duplicates(listings)
    suspects = hide_suspect_prices(listings)

    OUTPUT_FILE.write_text(json.dumps(listings, ensure_ascii=False, indent=2), encoding="utf-8")

    def count(key: str) -> int:
        return sum(1 for item in listings if item[key] is not None)

    print(f"\nВыгружено объявлений: {len(listings)} → {OUTPUT_FILE.relative_to(SITE_DIR)}")
    print(f"  убрано дублей внутри аккаунтов: {duplicates}")
    print(f"  с годом: {count('year')}, с пробегом: {count('mileage_km')}, с фото: {count('image')}")
    print(f"  с ценой: {count('price')}, цена по запросу: {len(listings) - count('price')}")
    if suspects:
        print(f"  подозрительных цен: {len(suspects)} (скрыты, список в data/{PRICE_SUSPECTS_FILE.name})")
        for item in suspects:
            print(f"    {item['account']} {item['id']} {item['title']}: {item['price']}$, {item['reason']}")
    print(f"  с пометкой BARAKA BOLDI (вероятно, проданы): {sum(item['is_sold'] for item in listings)}")


if __name__ == "__main__":
    main()
