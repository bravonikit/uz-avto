"""Оценка цены и ликвидности объявления по похожим машинам. Первая версия, без обучения модели.

Цена. Для машины берём аналоги: та же марка и модель, год отличается не больше чем на 1 (если аналогов
мало, на 2), тот же класс (новая или с пробегом), машина в наличии, другой продавец. По ценам аналогов
считаем медиану и границы средней половины (25% и 75%). Поля объявления:
  market_price, market_low, market_high   медиана и границы по аналогам, USD
  market_n                                сколько аналогов
  price_delta                             насколько цена отличается от медианы: -0.08 это на 8% ниже
  price_label                             below, fair, above или check (слишком далеко от рынка,
                                          на сайте такую оценку не показываем)

Ликвидность. Доля машин этой модели, которые продавец пометил проданными, среди объявлений
возрастом от LIQUIDITY_MIN_DAYS до LIQUIDITY_MAX_DAYS дней. Считается только по продавцам, которые
вообще отмечают «продано». Поля: liquidity_share, liquidity_n, liquidity_label (high, medium, low),
liquidity_level (model: посчитано по модели, brand: по марке, потому что по модели мало данных).
Это не срок продажи: точные даты продажи начнут копиться с ежедневных прогонов.
"""

from datetime import datetime, timezone
from statistics import median, quantiles

MIN_ANALOGS = 5
NEW_CAR_KM = 1_000  # пробег меньше этого: машина новая
NEW_CAR_YEARS = 1  # без пробега в тексте новой считаем машину этого и прошлого года
LABEL_DELTA = 0.07  # ближе к медиане, чем на 7%: цена в рынке
CHECK_DELTA = 0.35  # дальше от медианы, чем на 35%: скорее ошибка разбора или другая машина, чем выгода
LIQUIDITY_MIN_DAYS, LIQUIDITY_MAX_DAYS = 21, 90
LIQUIDITY_MIN_MODEL, LIQUIDITY_MIN_BRAND = 8, 15
MARKS_SOLD_SHARE = 0.08  # продавец отмечает «продано», если так помечено хотя бы 8% его объявлений
MARKET_FIELDS = ("market_price", "market_low", "market_high", "market_n", "price_delta", "price_label",
                 "liquidity_share", "liquidity_n", "liquidity_label", "liquidity_level")


def is_new(item: dict, this_year: int) -> bool:
    if item["mileage_km"] is not None:
        return item["mileage_km"] < NEW_CAR_KM
    return item["year"] is not None and item["year"] >= this_year - NEW_CAR_YEARS


def car_key(item: dict) -> tuple[str, str] | None:
    if not (item["brand"] and item["model"]):
        return None
    return item["brand"].lower(), item["model"].lower()


def add_prices(listings: list[dict], this_year: int) -> None:
    pool: dict[tuple, list[dict]] = {}
    for item in listings:
        key = car_key(item)
        if key and item["price"] is not None and item["year"] is not None and not item["price_type"]:
            pool.setdefault((key, is_new(item, this_year)), []).append(item)
    for item in listings:
        key = car_key(item)
        if not key or item["price"] is None or item["year"] is None or item["price_type"]:
            continue
        others = [o for o in pool.get((key, is_new(item, this_year)), [])
                  if o is not item and o["seller_id"] != item["seller_id"]]
        analogs: list[int] = []
        for window in (1, 2):
            analogs = [o["price"] for o in others if abs(o["year"] - item["year"]) <= window]
            if len(analogs) >= MIN_ANALOGS:
                break
        if len(analogs) < MIN_ANALOGS:
            continue
        low, _, high = quantiles(analogs, n=4)
        middle = median(analogs)
        delta = item["price"] / middle - 1
        label = "check" if abs(delta) > CHECK_DELTA else "below" if delta <= -LABEL_DELTA and item["price"] < low else "above" if delta >= LABEL_DELTA and item["price"] > high else "fair"
        item.update(market_price=round(middle), market_low=round(low), market_high=round(high), market_n=len(analogs),
                    price_delta=round(delta, 3), price_label=label)


def add_liquidity(listings: list[dict], now: datetime) -> None:
    by_account: dict[str, list[dict]] = {}
    for item in listings:
        by_account.setdefault(item["source_account"], []).append(item)
    marking = {account for account, items in by_account.items()
               if sum(item["is_sold"] for item in items) >= MARKS_SOLD_SHARE * len(items)}

    def age_days(item: dict) -> float:
        first = item.get("first_posted") or item["date"]
        return (now - datetime.fromisoformat(first.replace("Z", "+00:00"))).total_seconds() / 86400

    by_model: dict[tuple, list[bool]] = {}
    by_brand: dict[str, list[bool]] = {}
    for item in listings:
        key = car_key(item)
        if key and item["source_account"] in marking and not item["price_type"] and LIQUIDITY_MIN_DAYS <= age_days(item) <= LIQUIDITY_MAX_DAYS:
            by_model.setdefault(key, []).append(item["is_sold"])
            by_brand.setdefault(key[0], []).append(item["is_sold"])
    for item in listings:
        key = car_key(item)
        if not key or item["price_type"]:
            continue
        sold, level = by_model.get(key, []), "model"
        if len(sold) < LIQUIDITY_MIN_MODEL:
            sold, level = by_brand.get(key[0], []), "brand"
            if len(sold) < LIQUIDITY_MIN_BRAND:
                continue
        share = sum(sold) / len(sold)
        item.update(liquidity_share=round(share, 2), liquidity_n=len(sold), liquidity_level=level,
                    liquidity_label="high" if share >= 0.5 else "medium" if share >= 0.25 else "low")


def add_market(listings: list[dict]) -> dict:
    """Дописывает оценку цены и ликвидности. Возвращает сводку для отчёта."""
    now = datetime.now(timezone.utc)
    for item in listings:
        item.update(dict.fromkeys(MARKET_FIELDS))
    add_prices(listings, now.year)
    add_liquidity(listings, now)
    priced = [item for item in listings if item["price_delta"] is not None]
    labels = {name: sum(1 for item in priced if item["price_label"] == name) for name in ("below", "fair", "above", "check")}
    return {
        "priced": len(priced),
        "labels": labels,
        "median_error": round(median(abs(item["price_delta"]) for item in priced), 3) if priced else None,
        "with_liquidity": sum(1 for item in listings if item["liquidity_share"] is not None),
        "liquidity_by_model": sum(1 for item in listings if item["liquidity_level"] == "model"),
    }
