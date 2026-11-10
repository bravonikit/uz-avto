"""Находит цену в описании поста.

Понимает разные форматы продавцов:
  "NARXI:30.900💰", "💰 NARXI: 19 500 $", "Цена: $31.500", "Нархи💵 40.500",
  "💵Cтоимость 130.000$", "- Narxi 111000$", "CIP UZBEKISTAN: $78 000",
  "Narxi tushti 🔥 69.900", "1.261.ml (106000$)", "⚫️⚪️-44.900💰" (цены по цветам).
Точка, запятая и пробел внутри числа разделяют тысячи. Валюта всегда USD.

Не считаются ценой: первый взнос и платежи рассрочки, суммы в вонах, юанях и сумах,
пробег (км), телефоны, числа меньше 1000.
Пост без цены (анонс партии, обзор, «цена в директ») получает price = None.

Запуск: python extract_price.py  →  data/<аккаунт>/prices.json
        (все аккаунты из accounts.txt или только указанные: python extract_price.py имя)
"""

import json
import re

from accounts import account_dir, load_accounts

CURRENCY = "USD"
MIN_PRICE = 1_000
MAX_PRICE = 3_000_000

# Число: 30.900 / 19 500 / 1,250,000 / 111000. Минимум 4 цифры.
NUM = r"(?<![\d.,])(\d{1,3}(?:[ .,'’]\d{3})+|\d{4,7})(?![\d]|[.,]\d)"
# После числа не должно идти: км, вон, юань, сум, млн (это не доллары)
NOT_USD = r"(?!\.?\s*(?:km|км|won|вон|yuan|юан|ml\b|mln|млн|million|so.?m|сум|ming|минг))"
KEYWORD = r"(?:narx\w*|нарх\w*|цена|price|[сc]тоимост\w*|cip\b[^:\n]{0,20}:?)"
CUR_SIGN = r"(?:\$|💰|💵|💲)"
CUR_AFTER = r"\s*(?:\$|💰|💵|💲|y\.?\s?e\b|у\.?\s?е\b|usd|долл)"

PRICE_PATTERNS = [
    re.compile(KEYWORD + r"[^\d\n]{0,15}" + NUM + NOT_USD, re.IGNORECASE),  # Narxi: 19 500
    re.compile(CUR_SIGN + r"\s*" + NUM + NOT_USD, re.IGNORECASE),            # $31.500, 💵34 500
    re.compile(NUM + CUR_AFTER, re.IGNORECASE),                                # 28900$, 30.900💰
]

# Строки про рассрочку и взнос: суммы там не цена машины
SKIP_LINE = re.compile(
    r"boshlang|boshiga|nasiyaga|насияга|первоначальн|предоплат|взнос|to.?lov|тўлов|тулов|oyiga|ойига|ежемесяч|в месяц|bonus|бонус|kafolat|шин[аы]",
    re.IGNORECASE,
)


def to_number(raw: str) -> int:
    return int(re.sub(r"[ .,'’]", "", raw))


def find_prices(text: str) -> list[int]:
    """Все разные цены из текста в USD, в порядке появления."""
    prices: list[int] = []
    for line in text.splitlines():
        if SKIP_LINE.search(line):
            continue
        for pattern in PRICE_PATTERNS:
            for match in pattern.finditer(line):
                price = to_number(match.group(1))
                if MIN_PRICE <= price <= MAX_PRICE and price not in prices:
                    prices.append(price)
    return prices


def main_price(text: str) -> int | None:
    """Цена машины для сайта.

    Если есть строка со словом «цена» (Narxi, Нархи, Цена, Price...), берём первую такую цену.
    Иначе берём минимальную: так у продавцов, которые пишут цены по цветам
    ("⚫️⚪️-44.900💰", "⚫️🟠-44.500💰"), получается цена «от».
    """
    keyword_prices = []
    for line in text.splitlines():
        if SKIP_LINE.search(line):
            continue
        for match in PRICE_PATTERNS[0].finditer(line):
            price = to_number(match.group(1))
            if MIN_PRICE <= price <= MAX_PRICE:
                keyword_prices.append(price)
    if keyword_prices:
        return keyword_prices[0]
    prices = find_prices(text)
    return min(prices) if prices else None


def is_announcement(text: str) -> bool:
    """Пост без цены: анонс партии, обзор, «цена в директ»."""
    return not find_prices(text)


EXAMPLES_WITHOUT_PRICE = 3  # сколько постов без цены показать по каждому аккаунту


def process_account(account: str) -> dict | None:
    """Ищет цены в постах одного аккаунта. Возвращает счётчики для итоговой таблицы."""
    input_file = account_dir(account) / "raw_posts.json"
    if not input_file.exists():
        print(f"{account}: нет {input_file.name}, сначала запустите download.py")
        return None
    posts = json.loads(input_file.read_text(encoding="utf-8"))

    results = []
    for post in posts:
        text = post["description"]
        announcement = is_announcement(text)
        prices = [] if announcement else find_prices(text)
        results.append(
            {
                "url": post["url"],
                "price": main_price(text) if prices else None,
                "all_prices": prices,
                "currency": CURRENCY if prices else None,
                "is_announcement": announcement,
            }
        )

    output_file = account_dir(account) / "prices.json"
    output_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    ads = [r for r in results if not r["is_announcement"]]
    without_price = [(r, p) for r, p in zip(results, posts) if not r["is_announcement"] and r["price"] is None]
    for result, post in without_price[:EXAMPLES_WITHOUT_PRICE]:
        print(f"\n--- {account}, без цены: {result['url']}")
        print(post["description"])
    return {
        "account": account,
        "posts": len(results),
        "announcements": len(results) - len(ads),
        "with_price": len(ads) - len(without_price),
        "without_price": len(without_price),
    }


def main() -> None:
    stats = [s for s in (process_account(a) for a in load_accounts()) if s]

    print(f"\n{'аккаунт':<30}{'постов':>8}{'с ценой':>9}{'без цены':>10}")
    for row in stats:
        print(f"{row['account']:<30}{row['posts']:>8}{row['with_price']:>9}{row['announcements']:>10}")


if __name__ == "__main__":
    main()
