"""Разбирает сырые посты Telegram в объявления. Сырой слой не меняет.

Берёт:  data/_tg/<канал>/posts.json
Пишет:  data/_tg/<канал>/parsed.json  разбор каждого поста с текстом (вид поста и поля машины)
        data/_tg/listings.json         объявления всех каналов, дубли внутри канала склеены

Вид поста (kind):
  listing      конкретная машина: есть марка и хотя бы цена, год или пробег
  catalog      предложение под заказ: цена CIP или «под заказ» без пробега, либо прайс по комплектациям
  sold_notice  отдельное сообщение «продано» без описания машины
  other        новости, реклама, анонсы, служебные сообщения

Запуск: python tg_parse.py            все каналы
        python tg_parse.py azaavtoo   только указанные
"""

import json
import re
import sys
from collections import Counter

from enrich import extra_fields, find_price_type
from export_to_site import MAX_MILEAGE_KM, find_year, merge_account_duplicates
from extract_price import find_down_payment, find_prices, main_price
from tg_download import TG_DIR

LISTINGS_FILE = TG_DIR / "listings.json"
# Разбор ЛЛМ для постов, с которыми правила не справились: {id: {is_listing, brand, model, year, mileage_km, price, is_sold}}.
# Значения проверены по тексту поста (цена, год и пробег должны в нём читаться). Правится и пополняется руками или через ЛЛМ.
LLM_PARSED_FILE = TG_DIR / "llm_parsed.json"
OLDEST_YEAR, NEWEST_YEAR = 1980, 2027

# Как пишут марку в постах → единое название
BRANDS = {
    "zeekr": "Zeekr", "byd": "BYD", "бид": "BYD", "bmw": "BMW", "бмв": "BMW", "audi": "Audi", "ауди": "Audi",
    "mercedes": "Mercedes-Benz", "mersedes": "Mercedes-Benz", "mersedez": "Mercedes-Benz", "mercedes-benz": "Mercedes-Benz",
    "mercedesbenz": "Mercedes-Benz", "mercedes-amg": "Mercedes-Benz", "mercedes-maybach": "Mercedes-Benz", "mb": "Mercedes-Benz",
    "мерседес": "Mercedes-Benz", "mercades": "Mercedes-Benz", "maybach": "Mercedes-Benz",
    "porsche": "Porsche", "toyota": "Toyota", "tayota": "Toyota", "тойота": "Toyota", "lexus": "Lexus", "lexsus": "Lexus",
    "лексус": "Lexus", "kia": "Kia", "киа": "Kia", "hyundai": "Hyundai", "hundai": "Hyundai", "xundai": "Hyundai",
    "хендай": "Hyundai", "genesis": "Genesis", "chevrolet": "Chevrolet", "шевроле": "Chevrolet", "gac": "GAC",
    "lixiang": "Lixiang", "lixian": "Lixiang", "li": "Lixiang", "voyah": "Voyah", "voyax": "Voyah", "dongfeng": "Dongfeng",
    "dongfen": "Dongfeng", "changan": "Changan", "chagan": "Changan", "deepal": "Deepal", "depal": "Deepal",
    "deepall": "Deepal", "hongqi": "Hongqi", "xpeng": "XPeng", "x-peng": "XPeng", "xiaomi": "Xiaomi", "xiomi": "Xiaomi",
    "nio": "NIO", "onvo": "ONVO", "geely": "Geely", "tesla": "Tesla", "volkswagen": "Volkswagen", "vw": "Volkswagen",
    "wolksvagen": "Volkswagen", "vokswagen": "Volkswagen", "volkswagеn": "Volkswagen", "ford": "Ford", "nissan": "Nissan",
    "honda": "Honda", "mazda": "Mazda", "haval": "Haval", "jetour": "Jetour", "chery": "Chery", "exeed": "Exeed",
    "denza": "Denza", "avatr": "Avatr", "aito": "Aito", "maextro": "Maextro", "neta": "Neta", "lynk&co": "Lynk & Co",
    "lynk": "Lynk & Co", "leapmotor": "Leapmotor", "leapmotors": "Leapmotor", "cadillac": "Cadillac", "dodge": "Dodge",
    "jeep": "Jeep", "mitsubishi": "Mitsubishi", "subaru": "Subaru", "volvo": "Volvo", "skoda": "Skoda", "opel": "Opel",
    "daewoo": "Daewoo", "ravon": "Ravon", "lada": "Lada", "vaz": "Lada", "bentley": "Bentley", "lamborghini": "Lamborghini",
    "ferrari": "Ferrari", "rolls-royce": "Rolls-Royce", "rolls": "Rolls-Royce", "mini": "Mini", "jaguar": "Jaguar",
    "infiniti": "Infiniti", "yangwang": "Yangwang", "wey": "Wey", "tank": "Tank", "icar": "iCar", "roewe": "Roewe",
    "mg": "MG", "jaecoo": "Jaecoo", "omoda": "Omoda", "kaiyi": "Kaiyi", "baic": "BAIC", "faw": "FAW", "jac": "JAC",
    "isuzu": "Isuzu", "fiat": "Fiat", "peugeot": "Peugeot", "renault": "Renault", "smart": "Smart", "abt": "Audi",
    "land": "Land Rover", "range": "Land Rover", "defender": "Land Rover", "aion": "GAC", "galaxy": "Geely",
    "chazor": "BYD", "seagull": "BYD", "sealion": "BYD", "corvette": "Chevrolet", "camaro": "Chevrolet",
    "mustang": "Ford", "leopard": "BYD", "fangchengbao": "BYD", "fang": "BYD",
    "zikeer": "Zeekr", "zeeker": "Zeekr", "zikr": "Zeekr", "zekr": "Zeekr", "seres": "Seres", "hycan": "Hycan",
    "wolswagen": "Volkswagen", "volkswagen-id": "Volkswagen", "amg": "Mercedes-Benz", "prado": "Toyota",
    "camry": "Toyota", "highlander": "Toyota", "yuan": "BYD", "song": "BYD", "tang": "BYD", "qin": "BYD",
    "livan": "Livan", "geometry": "Geely", "im": "IM", "rox": "Rox", "luxeed": "Luxeed", "stelato": "Stelato",
    "shevrolet": "Chevrolet", "chevrolett": "Chevrolet", "мерседес-бенц": "Mercedes-Benz", "мерс": "Mercedes-Benz",
    "hiphi": "HiPhi", "nammi": "Dongfeng", "forthing": "Dongfeng", "bestune": "Bestune", "kaiyi": "Kaiyi",
}
# Модели Chevrolet, которые пишут без марки: как пишут → модель
CHEVROLET = {
    "malibu": "Malibu", "малибу": "Malibu", "gentra": "Gentra", "jentra": "Gentra", "жентра": "Gentra", "джентра": "Gentra",
    "cobalt": "Cobalt", "kobalt": "Cobalt", "кобальт": "Cobalt", "кобалт": "Cobalt", "spark": "Spark", "спарк": "Spark",
    "nexia": "Nexia", "нексия": "Nexia", "tracker": "Tracker", "trecker": "Tracker", "trekir": "Tracker", "treker": "Tracker",
    "трекер": "Tracker", "equinox": "Equinox", "equnox": "Equinox", "traverse": "Traverse", "треверс": "Traverse", "trecer": "Tracker", "treker2": "Tracker", "kaptiva": "Captiva", "eqinoks": "Equinox", "ekvinoks": "Equinox", "lasetti": "Lacetti", "neksiya": "Nexia", "jentira": "Gentra", "траверс": "Traverse", "эквинокс": "Equinox", "onix": "Onix", "oniks": "Onix",
    "оникс": "Onix", "captiva": "Captiva", "каптива": "Captiva", "monza": "Monza", "matiz": "Matiz", "матиз": "Matiz",
    "tahoe": "Tahoe", "lacetti": "Lacetti", "ласетти": "Lacetti", "damas": "Damas", "дамас": "Damas", "labo": "Labo",
    "orlando": "Orlando", "epica": "Epica", "trailblazer": "Trailblazer", "trablizer": "Trailblazer",
}
# Слова после марки, которые не модель
FILLER = {"benz", "amg", "rover", "motors", "auto", "avto", "new", "yangi", "новый", "новая", "the", "-", "—", "full", "elektro"}
# Вторая часть модели, без которой это другая машина: BYD Song Plus и BYD Song Pro
MODEL_TAIL = {"plus", "pro", "l", "up", "max", "05", "06", "07", "08", "champion", "cross", "sport", "cruiser"}
KEEP_BRAND_WORD = {"aion": "Aion", "galaxy": "Galaxy", "range": "Range Rover", "defender": "Defender",
                   "chazor": "Chazor", "seagull": "Seagull", "sealion": "Sealion", "maybach": "Maybach",
                   "mercedes-maybach": "Maybach", "corvette": "Corvette", "camaro": "Camaro", "mustang": "Mustang",
                   "leopard": "Leopard", "fangchengbao": "Fangchengbao", "fang": "Fangchengbao",
                   "prado": "Prado", "camry": "Camry", "highlander": "Highlander", "yuan": "Yuan", "song": "Song",
                   "tang": "Tang", "qin": "Qin", "nammi": "Nammi", "geometry": "Geometry"}
# После этих слов модель продолжается: "GAC Aion i60", "Geely Galaxy M9", "Toyota Land Cruiser"
MODEL_HEAD = {"aion", "galaxy", "land", "range", "model", "id", "song", "yuan"}
LIXIANG_SHORT = re.compile(r"^(?:li|l)?-?([6-9])$|^(?:li)-?(mega|i[68])$", re.IGNORECASE)

SOLD = re.compile(r"sot[iu]ld[iy]|сот[иу]лд[иы]|продан[оа]?\b|\bsold\b|baraka\s*(?:bo|to)|барака\s*(?:бо|то)", re.IGNORECASE)
SERVICE = re.compile(r"\bpinned\s+«|pinned a (?:photo|video|file)|закрепил", re.IGNORECASE)
STRUCK_PRICE = re.compile(r"\d[\d .,'’]*\s*\$?\s*❌")  # "48 500$❌ 46 000$✅": старая цена зачёркнута
HANDLE = re.compile(r"@[\w.]+")
WORD = re.compile(r"[^\W_][\w&.\-/+]*", re.UNICODE)

YEAR = r"((?:19[89]\d|20[0-2]\d))"
YEAR_AFTER_WORD = re.compile(r"(?:yil\w*|йил\w*|год\w*|выпуск\w*|year|sana\w*|📆|📅)[^\d\n]{0,25}(?:\d{1,2}[./]){0,2}" + YEAR + r"(?!\d)", re.IGNORECASE)
YEAR_IN_DATE = re.compile(r"(?<!\d)(?:\d{1,2}[./]){1,2}" + YEAR + r"(?!\d)|(?<!\d)" + YEAR + r"[./]\d{1,2}(?!\d)")  # 23.12.2024, 04/2026, 2026/02
YEAR_BEFORE_WORD = re.compile(r"(?<!\d)" + YEAR + r"\s*[-/]?\s*(?:yil|йил|год|г\.|model|модел|restayl|рестайл)", re.IGNORECASE)
YEAR_ALONE = re.compile(r"(?<![\d.,/:$\-+])" + YEAR + r"(?![\d]|[.,]\d|\s*(?:\$|km|км|kw|квт|cc|ot\b|л\.?с|usd|💰|💵|ml|мл|ming|минг))", re.IGNORECASE)
NOT_YEAR_LINE = re.compile(r"narx|нарх|цена|price|tel\b|тел\b|📞|☎|📲|\+998|garant|гарант|kafolat", re.IGNORECASE)

NUMBER = r"(\d{1,3}(?:[ .,]\d{3})+|\d+)"
THOUSAND = r"\s*(ming|минг|тыс\.?|k\b|к\b)?"
MILEAGE_AFTER_WORD = re.compile(r"(?:pro?b[eе][gkгк]\w*|prabeg\w*|пробег\w*|yurgan\w*|юрган\w*|👣)[^\d\n]{0,12}" + NUMBER + THOUSAND, re.IGNORECASE)
MILEAGE_BEFORE_KM = re.compile(r"(?<![\d.,])" + NUMBER + THOUSAND + r"\s*(?:km|км)\b(?!\s*/)", re.IGNORECASE)
NO_MILEAGE = re.compile(r"bez\s+pro?b[eе][gk]|без\s+пробег|pro?b[eе][gkгк]\w*\s*[-:]?\s*0\b(?!\s*[.,]?\d)", re.IGNORECASE)
NOT_MILEAGE_LINE = re.compile(r"zapas|запас|masofa|elektr|электр|\bev\b|cltc|wltp|soat|км/ч|km/h|yurish|yuradi|юради|\bxod|ход\b|заряд|zaryad|quvvat|0\s*[-–]\s*100|battery|batare|батаре|gibrid|hybrid|гибрид", re.IGNORECASE)


def text_lines(text: str) -> list[str]:
    return [line.strip() for line in HANDLE.sub(" ", text).splitlines() if line.strip()]


def find_car(text: str) -> tuple[str | None, str | None, str | None]:
    """(марка, модель, название) по первым строкам поста. Марку ищем по словарю, а не берём первое слово."""
    for line in text_lines(text)[:8]:
        if SOLD.search(line) and len(line) < 30:
            continue
        line = re.sub(r"\bdong\s+feng\b", "Dongfeng", line.replace("#", " "), flags=re.IGNORECASE)
        # "Malibu2", "Трекер2", "MONZA1.5": отделяем цифру от названия
        line = re.sub(r"(?<![^\W\d_])([^\W\d_]{4,})(\d(?:\.\d)?)\b", r"\1 \2", line)
        words = WORD.findall(line)
        for index, word in enumerate(words[:8]):
            key = word.lower().strip(".-/")
            rest = [w for w in words[index + 1:] if w.lower() not in FILLER]
            short = LIXIANG_SHORT.match(key)
            if short and key not in ("li", "l"):
                model = "L" + short.group(1) if short.group(1) else short.group(2).capitalize()
                return "Lixiang", model, " ".join(["Lixiang", model] + rest[:2])
            if key in CHEVROLET:
                model = CHEVROLET[key]
                if rest and rest[0] in ("1", "2", "3", "4") and model in ("Malibu", "Nexia", "Tracker", "Cobalt", "Spark"):
                    model += " " + rest[0]
                return "Chevrolet", model, " ".join(words[index:index + 4])
            if key not in BRANDS:
                continue
            brand = BRANDS[key]
            if key == "land" and not (rest or words[index + 1:index + 2] == ["Rover"]):
                continue
            parts = [KEEP_BRAND_WORD[key]] if key in KEEP_BRAND_WORD else []
            if brand == "Chevrolet" and rest and rest[0].lower() in CHEVROLET:
                parts, rest = [CHEVROLET[rest[0].lower()]], rest[1:]
            elif brand == "Lixiang" and rest and LIXIANG_SHORT.match(rest[0]):
                short = LIXIANG_SHORT.match(rest[0])
                parts, rest = ["L" + short.group(1) if short.group(1) else short.group(2).capitalize()], rest[1:]
            elif rest and not re.fullmatch(r"(?:19|20)\d{2}|\d{4,}", rest[0]) and key not in ("range", "defender", "maybach", "mercedes-maybach"):
                parts.append(model_word(rest[0], brand))
                rest = rest[1:]
            if parts and parts[-1].lower() in MODEL_HEAD and rest and not re.fullmatch(r"(?:19|20)\d{2}|\d{4,}", rest[0]):
                parts.append(model_word(rest[0], brand))
                rest = rest[1:]
            if rest and rest[0].lower() in MODEL_TAIL and parts:
                parts.append(model_word(rest[0], brand))
            model = " ".join(parts) or None
            return brand, model, " ".join(words[index:index + 5])
    return None, None, None


def model_word(word: str, brand: str) -> str:
    word = word.strip(".-/")
    if word.isalpha():
        return word.upper() if len(word) <= 3 and brand != "BYD" else word.capitalize()
    if re.fullmatch(r"[iI][A-Za-z]?\d*", word):  # BMW i5, Aion i60, Hyundai i30
        return "i" + word[1:].upper()
    if re.fullmatch(r"\d{3}[A-Za-z]{1,2}", word):  # BMW 530i, 540i, 320d
        return word.lower()
    return word.upper() if len(word) <= 6 else word


def find_year_tg(text: str, title: str | None) -> int | None:
    year = find_year(text)
    if year is None:
        for pattern in (YEAR_AFTER_WORD, YEAR_BEFORE_WORD, YEAR_IN_DATE):
            match = pattern.search(text)
            if match:
                year = int(match.group(1) or match.group(2)) if pattern is YEAR_IN_DATE else int(match.group(1))
                break
    if year is None:
        lines = ([title] if title else []) + [line for line in text_lines(text) if not NOT_YEAR_LINE.search(line)]
        for line in lines:
            match = YEAR_ALONE.search(line)
            if match:
                year = int(match.group(1))
                break
    return year if year is not None and OLDEST_YEAR <= year <= NEWEST_YEAR else None


def to_km(number: str, thousand: str | None) -> int | None:
    value = int(re.sub(r"\D", "", number))
    if thousand:
        value *= 1000
    return value if 0 <= value <= MAX_MILEAGE_KM else None


def find_mileage_tg(text: str) -> int | None:
    if NO_MILEAGE.search(text):
        return 0
    match = MILEAGE_AFTER_WORD.search(text)
    if match:
        return to_km(match.group(1), match.group(2))
    # Первая строка это название: "BYD Champion 520 km" там запас хода, а не пробег
    for line in text_lines(text)[1:]:
        if NOT_MILEAGE_LINE.search(line):
            continue
        match = MILEAGE_BEFORE_KM.search(line)
        if match:
            return to_km(match.group(1), match.group(2))
    return None


KEYCAP_DIGIT = re.compile(r"(\d)\ufe0f?\u20e3")  # цифры эмодзи: 3️⃣1️⃣.6️⃣0️⃣0️⃣
PRICE_RANGE = re.compile(r"(\$\s*\d{1,3})\s*[-–—]\s*\d{1,3}([ .,]\d{3})")  # "$36-37 000": берём нижнюю границу
TURNKEY_LINE = re.compile(r"под\s+ключ|pod\s+klyuch", re.IGNORECASE)


def price_text(text: str) -> str:
    """Текст, в котором цену видят общие правила: без зачёркнутых цен, эмодзи цифр и диапазонов."""
    text = KEYCAP_DIGIT.sub(r"\1", text)
    text = STRUCK_PRICE.sub(" ", text)
    return PRICE_RANGE.sub(r"\1\2", text)


def price_of(text: str) -> int | None:
    text = price_text(text)
    price = main_price(text)
    if price is None:
        # "ПОД КЛЮЧ — $255 000" рядом с предоплатой: это цена машины, а не взнос
        for line in text.splitlines():
            if TURNKEY_LINE.search(line) and find_prices(line):
                return find_prices(line)[0]
    return price


def parse_post(post: dict) -> dict:
    """Разбор одного поста: вид и поля машины."""
    text = post["text"]
    priced_text = price_text(text)
    brand, model, title = find_car(text)
    price, year, mileage = price_of(text), find_year_tg(text, title), find_mileage_tg(text)
    is_sold = bool(SOLD.search(text))
    price_type = find_price_type(text)
    many_prices = len(find_prices(priced_text)) >= 3

    if SERVICE.search(text):
        kind = "other"
    elif is_sold and not brand and len(re.sub(r"\W", "", text)) < 60:
        kind = "sold_notice"
    elif brand and (price is not None or year is not None or mileage is not None):
        on_order = price_type in ("cip", "order") and not mileage
        kind = "catalog" if on_order or (many_prices and mileage is None) else "listing"
    elif price is not None and (year is not None or mileage is not None):
        kind = "listing"  # машина есть, марку не узнали: кандидат на разбор ЛЛМ
    else:
        kind = "other"

    # Прошлые цены из истории правок поста
    price_history = []
    for old in post.get("history", []):
        old_price = price_of(old["text"])
        if old_price is not None and old_price != price and (not price_history or price_history[-1]["price"] != old_price):
            price_history.append({"until": old["until"], "price": old_price})

    return {
        "id": f"tg-{post['channel']}-{post['id']}", "kind": kind, "title": title, "brand": brand, "model": model,
        "year": year, "mileage_km": mileage, "price": price, "currency": "USD" if price is not None else None,
        "down_payment": find_down_payment(text), "is_sold": is_sold, "price_history": price_history,
        **extra_fields(text),
        "description": text, "source": "telegram", "source_account": post["channel"], "source_url": post["url"],
        "date": post["date"], "views": post.get("views"), "edited": post.get("edited", False),
        "first_seen": post.get("first_seen"), "removed_at": post.get("removed_at"),
    }


def add_repost_prices(car: dict, by_id: dict[str, dict]) -> None:
    """Машину выкладывали несколько раз с разной ценой: прошлые цены идут в историю."""
    older = sorted((by_id[code] for code in car["duplicate_ids"]), key=lambda item: item["date"])
    history = list(car["price_history"])
    for item in older:
        if item["price"] is not None and item["price"] != car["price"] and item["price"] not in [h["price"] for h in history]:
            history.append({"until": item["date"], "price": item["price"]})
    car["price_history"] = sorted(history, key=lambda entry: entry["until"])
    car["first_posted"] = older[0]["date"] if older else car["date"]


def apply_llm(item: dict, parsed: dict | None) -> None:
    """Дополняет разбор правил разбором ЛЛМ: марка и модель из ЛЛМ, остальное только туда, где пусто."""
    if not parsed:
        return
    if not parsed.get("is_listing", True):
        item["kind"] = "other"
        return
    if parsed.get("brand"):
        item["brand"], item["model"] = parsed["brand"], parsed.get("model") or item["model"]
        item["title"] = item["title"] or " ".join(part for part in (item["brand"], item["model"]) if part)
    for key in ("year", "mileage_km", "price"):
        if item[key] is None and parsed.get(key) is not None:
            item[key] = parsed[key]
    if item["price"] is not None:
        item["currency"] = "USD"
    item["is_sold"] = item["is_sold"] or bool(parsed.get("is_sold"))
    item["llm"] = True
    if item["kind"] == "other" and item["brand"]:
        item["kind"] = "listing"


def post_images(post: dict, posts: dict[str, dict]) -> tuple[list[str], bool]:
    """(картинки поста, есть ли видео). У текста без картинок берём их из сообщения перед ним."""
    owner = post if post.get("images") or not post.get("media_from") else posts.get(str(post["media_from"]), post)
    return list(owner.get("images") or []), owner["type"] == "video" or bool(owner.get("video_durations"))


def parse_channel(channel: str, llm_parsed: dict) -> list[dict]:
    posts = json.loads((TG_DIR / channel / "posts.json").read_text(encoding="utf-8"))
    parsed = []
    for post in posts.values():
        if not post["text"]:
            continue
        item = parse_post(post)
        apply_llm(item, llm_parsed.get(item["id"]))
        item["images"], item["has_video"] = post_images(post, posts)
        item["image"] = item["images"][0] if item["images"] else None
        parsed.append(item)
    (TG_DIR / channel / "parsed.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=1), encoding="utf-8")
    return parsed


def main() -> None:
    wanted = {name.lower() for name in sys.argv[1:]}
    channels = sorted(folder.name for folder in TG_DIR.iterdir() if (folder / "posts.json").exists())
    channels = [name for name in channels if not wanted or name.lower() in wanted]
    kinds, listings, removed_total = Counter(), [], 0
    llm_parsed = json.loads(LLM_PARSED_FILE.read_text(encoding="utf-8")) if LLM_PARSED_FILE.exists() else {}
    for channel in channels:
        parsed = parse_channel(channel, llm_parsed)
        kinds.update(item["kind"] for item in parsed)
        cars = [item for item in parsed if item["kind"] in ("listing", "catalog")]
        by_id = {item["id"]: item for item in cars}
        cars, removed = merge_account_duplicates(cars)
        for car in cars:
            add_repost_prices(car, by_id)
        removed_total += removed
        listings += cars
        count = Counter(item["kind"] for item in cars)
        print(f"  {channel}: постов с текстом {len(parsed)}, машин {count['listing']}, под заказ {count['catalog']}, дублей убрано {removed}")
    if not wanted:
        listings.sort(key=lambda item: item["date"], reverse=True)
        LISTINGS_FILE.write_text(json.dumps(listings, ensure_ascii=False, indent=1), encoding="utf-8")

    cars = [item for item in listings if item["kind"] == "listing"]

    def share(key: str) -> str:
        return f"{sum(1 for item in cars if item[key] is not None)}"

    print(f"\nПостов с текстом: {sum(kinds.values())}. Объявления {kinds['listing']}, под заказ {kinds['catalog']}, "
          f"«продано» отдельным постом {kinds['sold_notice']}, прочее {kinds['other']}")
    print(f"После склейки дублей внутри каналов (убрано {removed_total}): машин {len(cars)}, под заказ {len(listings) - len(cars)}")
    print(f"  у машин: с маркой {share('brand')}, с моделью {share('model')}, с ценой {share('price')}, с годом {share('year')}, "
          f"с пробегом {share('mileage_km')}, с фото {share('image')}")
    print(f"  проданы {sum(item['is_sold'] for item in cars)}, пост удалён {sum(1 for item in cars if item['removed_at'])}, "
          f"цена менялась {sum(1 for item in cars if item['price_history'])}, разобрано ЛЛМ {sum(1 for item in listings if item.get('llm'))}")


if __name__ == "__main__":
    main()
