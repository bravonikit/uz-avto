"""Дополнительные поля карточки при выгрузке на сайт (вызывает export_to_site.py).

  fix_euro          цены в евро («Cip Tashkent: 239,000 €») переводим в доллары, исходник в price_original
  apply_ev_specs    запас хода и батарея из текста поста (ev_specs.py)
  apply_price_fill  цена, запас хода и батарея из голоса и фото (ответы Gemini из price_fill.py),
                    только там, где в тексте поста этого нет

Курсы задаются здесь. Они приблизительные: поправьте, если курс сильно ушёл.
"""
from __future__ import annotations

import json
import re

from accounts import PARSER_DIR
from ev_specs import ev_specs

UZS_PER_USD = 12_500  # тот же курс, что на сайте (src/lib/format.ts)
USD_PER_EUR = 1.16
PRICE_FILL_FILE = PARSER_DIR / "data" / "price_fill.json"
EURO_PRICE = re.compile(r"\d[\d\s.,]*\s*€|€\s*\d|\d[\d\s.,]*\s*(?:euro|evro|евро)\b", re.I)
MIN_USD, MAX_USD = 1_000, 5_000_000
EV_FIELDS = ("powertrain", "range_km", "range_total_km", "range_now_km", "battery_pct")


def _to_usd(value, currency: str | None) -> int | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    currency = (currency or "USD").upper()
    if currency == "UZS":
        value = value / UZS_PER_USD
    elif currency == "EUR":
        value = value * USD_PER_EUR
    elif currency == "USD" and value < 1000:
        value *= 1000  # «19.9» или «19,5» в тысячах долларов
    value = round(value / 100) * 100
    return int(value) if MIN_USD <= value <= MAX_USD else None


def fix_euro(listings: list[dict]) -> int:
    fixed = 0
    for item in listings:
        text = item.get("description") or ""
        if item["price"] is None or "$" in text or not EURO_PRICE.search(text):
            continue
        item["price_original"] = {"value": item["price"], "currency": "EUR"}
        item["price"] = _to_usd(item["price"], "EUR") or item["price"]
        fixed += 1
    return fixed


def apply_ev_specs(listings: list[dict]) -> int:
    count = 0
    for item in listings:
        specs = ev_specs(item.get("brand"), item.get("model"), item.get("title"), item.get("description"))
        for key in EV_FIELDS:
            item[key] = specs.get(key)
        count += "range_km" in specs or "range_total_km" in specs
    return count


def apply_price_fill(listings: list[dict]) -> dict:
    """Цена из голоса или с фото, если в тексте её нет. Сначала надпись на фото: она точнее, чем на слух."""
    try:
        answers = json.loads(PRICE_FILL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        answers = {}
    stats = {"image": 0, "voice": 0, "range": 0}
    for item in listings:
        item["price_source"] = None
        answer = answers.get(item["id"])
        if not answer:
            continue
        if item["price"] is None and not item.get("price_type"):
            for source, field in (("image", "price_image"), ("voice", "price_voice")):
                found = answer.get(field) or {}
                usd = _to_usd(found.get("value"), found.get("currency"))
                if usd:
                    item.update(price=usd, currency="USD", price_source=source,
                                price_approx=bool(found.get("approx")) if source == "voice" else False)
                    stats[source] += 1
                    break
        if item.get("range_km") is None and item.get("range_total_km") is None and answer.get("range_km"):
            try:
                value = int(answer["range_km"])
            except (TypeError, ValueError):
                value = 0
            if 50 <= value <= 1600:
                item["range_km"] = value
                item["powertrain"] = item.get("powertrain") or "ev"
                stats["range"] += 1
        if item.get("battery_pct") is None and isinstance(answer.get("battery_pct"), (int, float)) and 50 <= answer["battery_pct"] <= 100:
            item["battery_pct"] = int(answer["battery_pct"])
    return stats
