"""Связь поста «продано» с исходным объявлением канала.

Продавцы отмечают продажу отдельным сообщением через несколько дней: «SOTILDI», «Baraka bo'ldi», «ПРОДАНО!».
Ищем, какую машину продали, тремя способами по очереди:
  reply  сообщение ответом на объявление (reply_to из tg_download.py) — точное совпадение;
  photo  в сообщении то же фото машины, что в объявлении (перцептивный хэш, нужен Pillow);
  text   в сообщении та же марка и модель (и год с пробегом, если указаны): последнее непроданное объявление канала.
Объявление получает is_sold, sold_at (дата сообщения), sold_via (способ) и sold_notice (id сообщения).

Хэши фото кэшируются в data/_tg/<канал>/photo_hash.json, чтобы не читать фото с Диска каждый день.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

LOOKBACK_DAYS = 90  # объявление ищем не старше этого до сообщения «продано»
MAX_HAMMING = 8  # из 64 бит: одинаковые и пережатые фото дают 0-6

try:
    from PIL import Image
except ImportError:  # без Pillow работают только reply и text
    Image = None


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def dhash(path: Path) -> int | None:
    """64-битный разностный хэш: устойчив к пережатию и смене размера."""
    try:
        with Image.open(path) as image:
            pixels = list(image.convert("L").resize((9, 8)).getdata())
    except Exception:  # noqa: BLE001  битый файл или Диск не отдал
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


class PhotoHashes:
    def __init__(self, channel_dir: Path, parser_dir: Path):
        self.file = channel_dir / "photo_hash.json"
        self.parser_dir = parser_dir
        self.cache = json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else {}
        self.dirty = False

    def get(self, name: str) -> int | None:
        if Image is None:
            return None
        if name not in self.cache:
            path = self.parser_dir / name
            if not path.exists():  # фото на Диске недоступно сейчас: не запоминаем, попробуем в следующий раз
                return None
            self.cache[name] = dhash(path)
            self.dirty = True
        return self.cache[name]

    def save(self) -> None:
        if self.dirty:
            self.file.write_text(json.dumps(self.cache), encoding="utf-8")


def norm(value: str | None) -> str:
    return re.sub(r"[^0-9a-zа-я]", "", (value or "").lower())


def same_car(notice: dict, car: dict) -> bool:
    """Марка и модель совпадают; год и пробег, если есть в обоих постах, тоже."""
    notice_model, car_model = norm(notice.get("model")), norm(car.get("model"))
    if len(notice_model) < 2 or len(car_model) < 2:
        return False
    if not (car_model.startswith(notice_model) or notice_model.startswith(car_model)):
        return False
    if notice.get("brand") and car.get("brand") and notice["brand"] != car["brand"]:
        return False
    if notice.get("year") and car.get("year") and notice["year"] != car["year"]:
        return False
    a, b = notice.get("mileage_km"), car.get("mileage_km")
    if a and b and abs(a - b) > 0.05 * max(a, b):
        return False
    return True


def mark(item: dict, notice: dict, via: str) -> None:
    item["is_sold"] = True
    item["sold_at"] = notice["date"]
    item["sold_via"] = via
    item["sold_notice"] = notice["id"]
    days = (parse_date(notice["date"]) - parse_date(item["date"])).total_seconds() / 86400
    item["days_to_sell"] = round(max(days, 0), 1)


def link_sold(channel: str, parsed: list[dict], channel_dir: Path, parser_dir: Path) -> dict:
    """Помечает проданные объявления. Возвращает счётчики по способам."""
    notices = [item for item in parsed if item["kind"] == "sold_notice"]
    counts = {"notices": len(notices), "reply": 0, "photo": 0, "text": 0, "none": 0}
    if not notices:
        return counts
    cars = [item for item in parsed if item["kind"] in ("listing", "catalog")]
    by_id = {item["id"]: item for item in cars}
    hashes = PhotoHashes(channel_dir, parser_dir)
    for notice in sorted(notices, key=lambda item: item["date"]):
        start = parse_date(notice["date"]) - timedelta(days=LOOKBACK_DAYS)
        candidates = [car for car in cars if start <= parse_date(car["date"]) <= parse_date(notice["date"])
                      and car["id"] != notice["id"] and not car.get("sold_notice")]
        target, via = None, None
        # 1. Ответ на объявление
        reply_to = notice.get("reply_to")
        if reply_to and f"tg-{channel}-{reply_to}" in by_id:
            target, via = by_id[f"tg-{channel}-{reply_to}"], "reply"
        # 2. То же фото
        if target is None and Image is not None and notice.get("images"):
            notice_hashes = [h for h in (hashes.get(name) for name in notice["images"]) if h is not None]
            best = None
            for car in candidates:
                for name in (car.get("images") or [])[:3]:
                    car_hash = hashes.get(name)
                    if car_hash is None:
                        continue
                    distance = min(bin(car_hash ^ h).count("1") for h in notice_hashes) if notice_hashes else 99
                    if distance <= MAX_HAMMING and (best is None or distance < best[0]):
                        best = (distance, car)
            if best:
                target, via = best[1], "photo"
        # 3. Та же машина по тексту: марка и модель совпадают, а год и пробег, если указаны в обоих, тоже
        if target is None:
            matched = [car for car in candidates if not car["is_sold"] and same_car(notice, car)]
            if matched:
                target, via = max(matched, key=lambda car: car["date"]), "text"
        if target is None:
            counts["none"] += 1
            notice["sold_link"] = None
            continue
        mark(target, notice, via)
        notice["sold_link"] = target["id"]
        counts[via] += 1
    hashes.save()
    return counts
