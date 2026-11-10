"""Находит цену в описании поста.

Формат профиля auto_sale_abdulloh:
  "NARXI:30.900💰", "Narxi:33.300💰", "25.500💰", "37500💰"
  точка разделяет тысячи (30.900 = 30 900), валюта не пишется — это USD.
  Несколько цен по цветам: "⚫️⚪️-44.900💰" и "⚫️🟠-44.500💰".
  Пост без 💰 — анонс («Yengi partiya keldi» и список машин).

Запуск: python extract_price.py  →  data/prices.json
"""

import json
import re
from pathlib import Path

CURRENCY = "USD"
MONEY = "💰"

PARSER_DIR = Path(__file__).parent
INPUT_FILE = PARSER_DIR / "data" / "raw_posts.json"
OUTPUT_FILE = PARSER_DIR / "data" / "prices.json"

# Число прямо перед 💰 (пробелы между ними допустимы):
#   30.900 / 109.500 / 1.250.000 — с точками между тысячами
#   37500                       — без точек
# (?<![\d.,]) — число не должно быть хвостом другого числа.
# "Naqd💰" и "Probeg 20.000km" сюда не подходят: перед 💰 нет числа.
PRICE_PATTERN = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+|\d+)[ \t ]*" + MONEY)


def find_prices(text: str) -> list[int]:
    """Все разные цены из текста в USD, в порядке появления."""
    prices: list[int] = []
    for match in PRICE_PATTERN.finditer(text):
        price = int(re.sub(r"[.,]", "", match.group(1)))
        if price not in prices:
            prices.append(price)
    return prices


def is_announcement(text: str) -> bool:
    """Анонс новой партии: в тексте вообще нет 💰."""
    return MONEY not in text


def main() -> None:
    posts = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

    results = []
    for post in posts:
        text = post["description"]
        announcement = is_announcement(text)
        prices = [] if announcement else find_prices(text)
        results.append(
            {
                "url": post["url"],
                "price": min(prices) if prices else None,
                "all_prices": prices,
                "currency": CURRENCY if prices else None,
                "is_announcement": announcement,
            }
        )

    OUTPUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    ads = [r for r in results if not r["is_announcement"]]
    without_price = [(r, p) for r, p in zip(results, posts) if not r["is_announcement"] and r["price"] is None]
    print(f"Сохранено: {OUTPUT_FILE.relative_to(PARSER_DIR)}")
    print(f"Объявлений: {len(ads)}")
    print(f"Анонсов: {len(results) - len(ads)}")
    print(f"Объявлений с ценой: {len(ads) - len(without_price)}")
    print(f"Объявлений без цены: {len(without_price)}")
    for result, post in without_price:
        print(f"\n--- {result['url']}")
        print(post["description"])


if __name__ == "__main__":
    main()
