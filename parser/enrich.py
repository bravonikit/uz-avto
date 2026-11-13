"""Дополнительные поля объявления из текста поста: тип цены, топливо, цвета, город.

Поля ищутся правилами по словам, которые продавец написал сам. Чего в тексте нет, того и в поле нет.
Результат дописывается в data/llm_parsed.json к уже разобранным постам (марка, модель, год и пробег
не меняются).

  python enrich.py          — заполнить поля у всех разобранных постов и показать сводку
  python enrich.py show     — то же, но ничего не сохранять, а напечатать найденное по каждому посту
"""

import json
import re
import sys

from accounts import account_dir
from llm_parse import LLM_PARSED_FILE, load_accounts_from_file, load_parsed

# Тип цены. Порядок важен: первое совпавшее правило побеждает.
PRICE_TYPES = [
    # цена без растаможки: растаможку покупатель платит сам
    ("no_customs", r"без\s+растамож|растаможк\w*\s*(?::|примерно|ориентировочно|отдельно)|rastamojka\w*\s*(?:siz|alohida)|bojsiz|rastamojkasiz"),
    # цена с доставкой до Ташкента, машина ещё не здесь
    ("cip", r"\bcip\b|\bсип\b"),
    # под заказ: машины нет в наличии
    ("order", r"предзаказ|под\s+заказ|buyurtma\s+asosida|zakaz\w*\s+(?:asosida|qilamiz|beramiz)|заказ\w*\s+(?:асосида|киламиз)|yo.?lda\b|в\s+пути"),
]
PRICE_TYPE_PATTERNS = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in PRICE_TYPES]

FUELS = [
    # "Gibrid polik" это коврики, а не топливо
    ("Гибрид", r"gibrid(?!\s+polik)|hybrid|hybird|гибрид|dm-?i\b|phev|erev"),
    # Только слово целиком: "elektronika", "электромотор", "электрические пороги" сюда не подходят
    ("Электро", r"\belektr\b|\belectr(?:ic)?\b|\bэлектро\b|электромобил|электрическ\w+\s+(?:suv|седан|кроссовер|авто)|\bev\b|\bev\s?\d|\btok(?:da)?\b"),
    ("Дизель", r"dizel|diesel|дизел"),
    ("Газ/бензин", r"metan|метан|propan|пропан|\bgaz\b|\bгаз\b"),
    ("Бензин", r"benzin|бензин|petrol"),
]
FUEL_PATTERNS = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in FUELS]

# Цвета: как пишут в постах → (название, цвет для кружка на сайте)
COLORS = [
    ("мокрый асфальт", "#4b5563", r"mokr\w*|мокр\w*"),
    ("белый", "#f8fafc", r"oq\w{0,2}|ок|ак|бел\w+|white|belyy|beliy"),
    ("чёрный", "#111827", r"qora\w{0,2}|кора|ч[её]рн\w+|black"),
    ("серый", "#9ca3af", r"kulrang|kul\s?rang|seriy|сер(?:ый|ая|ое|ого)|gr[ae]y"),
    ("серебристый", "#d1d5db", r"kumush\w*|serebr\w*|серебр\w+|silver"),
    ("синий", "#1d4ed8", r"ko.?k|siniy|син\w+|blue|голуб\w+|havo\s?rang"),
    ("красный", "#dc2626", r"qizil|красн\w+|red"),
    ("бордовый", "#7f1d1d", r"bordo\w*|бордов\w+"),
    ("зелёный", "#15803d", r"yashil|зел[её]н\w+|green"),
    ("коричневый", "#78350f", r"jigar\s?rang|коричнев\w+|brown|kofe|coffe+a?|кофе\w*"),
    ("бежевый", "#e7d8c1", r"bej\w*|бежев\w+|beige|krem\w*|кремов\w+"),
    ("жёлтый", "#facc15", r"sariq|ж[её]лт\w+|yellow"),
    ("оранжевый", "#ea580c", r"oranj\w*|оранж\w+|orange|apelsin\w*"),
    ("стальной", "#94a3b8", r"stalnoy|стальн\w+"),
    ("золотистый", "#ca8a04", r"oltin\w*|золот\w+|gold"),
]
COLOR_PATTERN = re.compile(
    "|".join(f"(?P<c{i}>{pattern})" for i, (_, _, pattern) in enumerate(COLORS)), re.IGNORECASE)
BODY_MARK = re.compile(r"rang|цвет|color|colour|kuzov|кузов", re.IGNORECASE)
SALON_MARK = re.compile(r"salon|салон|interior|интерьер", re.IGNORECASE)

CITIES = [
    ("Ташкент", r"toshkent|tashkent|ташкент"), ("Самарканд", r"samarqand|samarkand|самарканд"),
    ("Бухара", r"buxoro|bukhara|бухар"), ("Андижан", r"andijon|andijan|андижан"),
    ("Наманган", r"namangan|наманган"), ("Фергана", r"farg.?ona|fergana|ферган"),
    ("Нукус", r"nukus|нукус"), ("Карши", r"qarshi|карши"), ("Навои", r"navoiy|navoi|навои"),
    ("Ургенч", r"urganch|xorazm|ургенч|хорезм"), ("Джизак", r"jizzax|джизак"),
    ("Коканд", r"qo.?qon|коканд"), ("Термез", r"termiz|термез"),
]
CITY_PATTERNS = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in CITIES]
CITY_MARK = re.compile(r"viloyat|manzil|adres|адрес|город|shahar|шаҳар|шахар|📍|joylashuv", re.IGNORECASE)
NOT_LOCATION = re.compile(r"\bcip\b|viloyatga\s+beriladi|вилоятга|yetkazib|доставк|propiska|прописк|hujjat", re.IGNORECASE)


def clean(text: str) -> str:
    return re.sub(r"#\S+", "", text)


def color_name(word: str) -> tuple[str, str] | None:
    match = COLOR_PATTERN.fullmatch(word.strip())
    if not match:
        return None
    index = int(match.lastgroup[1:])
    return COLORS[index][0], COLORS[index][1]


GA_SUFFIX = re.compile(r"(?:ga|га)$", re.IGNORECASE)


def colors_in(line: str) -> list[tuple[tuple[str, str], bool]]:
    """Цвета в строке по порядку: (цвет, стоит ли он в форме «oqga» / «окга» = «на белом»)."""
    found = []
    words = re.findall(r"[^\W\d_]+(?:[’'‘`][^\W\d_]+)?", line)
    for i, word in enumerate(words):
        with_ga = bool(GA_SUFFIX.search(word)) and color_name(GA_SUFFIX.sub("", word)) is not None
        color = color_name(GA_SUFFIX.sub("", word)) if with_ga else color_name(word)
        # "Mokriy asfalt ga qora": суффикс стоит отдельным словом
        if color and not with_ga and any(GA_SUFFIX.fullmatch(w) for w in words[i + 1:i + 3]):
            with_ga = True
        if color and color not in [c for c, _ in found]:
            found.append((color, with_ga))
    return found


def find_price_type(text: str) -> str | None:
    text = clean(text)
    for name, pattern in PRICE_TYPE_PATTERNS:
        if pattern.search(text):
            return name
    return None


def find_fuel(text: str) -> str | None:
    text = clean(text)
    for name, pattern in FUEL_PATTERNS:
        if pattern.search(text):
            return name
    return None


def find_colors(text: str) -> tuple[tuple[str, str] | None, tuple[str, str] | None]:
    """(цвет кузова, цвет салона). Только из строк, где продавец сам написал «цвет», «rangi», «salon»."""
    body = interior = None
    for line in clean(text).splitlines():
        is_salon, is_body = bool(SALON_MARK.search(line)), bool(BODY_MARK.search(line))
        if not (is_salon or is_body):
            continue
        found = colors_in(line)
        if not found:
            continue
        on_color = [color for color, with_ga in found if with_ga]
        plain = [color for color, with_ga in found if not with_ga]
        if on_color:
            # "Oqga qora salon", "Цвет: окга кора": первый цвет кузов, второй салон
            body = body or on_color[0]
            if plain:
                interior = interior or plain[0]
        elif is_salon and is_body and len(plain) > 1:
            body, interior = body or plain[0], interior or plain[1]
        elif is_salon:
            interior = interior or plain[0]
        else:
            body = body or plain[0]
    return body, interior


def find_city(text: str) -> str | None:
    for line in clean(text).splitlines():
        if not CITY_MARK.search(line) or NOT_LOCATION.search(line):
            continue
        for name, pattern in CITY_PATTERNS:
            if pattern.search(line):
                return name
    return None


def extra_fields(text: str) -> dict:
    body, interior = find_colors(text)
    return {
        "price_type": find_price_type(text),
        "fuel": find_fuel(text),
        "body_color": body[0] if body else None,
        "body_color_hex": body[1] if body else None,
        "interior_color": interior[0] if interior else None,
        "city": find_city(text),
    }


def all_posts() -> dict[str, dict]:
    posts = {}
    for account in load_accounts_from_file():
        raw_file = account_dir(account) / "raw_posts.json"
        if raw_file.exists():
            for post in json.loads(raw_file.read_text(encoding="utf-8")):
                posts.setdefault(post["shortcode"], post)
    return posts


def main() -> None:
    show = len(sys.argv) > 1 and sys.argv[1] == "show"
    parsed, posts = load_parsed(), all_posts()
    counts = {key: 0 for key in ("price_type", "fuel", "body_color", "interior_color", "city")}
    listings = 0
    for code, item in parsed.items():
        if code not in posts or not item.get("is_listing", True):
            continue
        listings += 1
        fields = extra_fields(posts[code]["description"])
        for key in counts:
            counts[key] += fields[key] is not None
        if show:
            print(code, {k: v for k, v in fields.items() if v and k != "body_color_hex"})
        else:
            item.update(fields)
    if not show:
        LLM_PARSED_FILE.write_text(json.dumps(parsed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Объявлений: {listings}. Заполнено: " + ", ".join(f"{key} {value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
