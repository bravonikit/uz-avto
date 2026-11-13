"""Проверка разбора постов Telegram. Запуск: python test_tg_parse.py"""

from tg_parse import find_car, find_mileage_tg, find_year_tg, parse_post, price_of


def post(text, **extra):
    return {"channel": "test", "id": 1, "url": "https://t.me/test/1", "date": "2026-11-01T10:00:00Z", "text": text, **extra}


# Марка и модель
assert find_car("Zeekr 001 \nProbek: 20 000\nYili: 2024")[:2] == ("Zeekr", "001")
assert find_car("@arzon.mashina Gentra Avtomat\n▫️Yili-2015")[:2] == ("Chevrolet", "Gentra")
assert find_car("#MALIBU 2 Turbo\nYIL : 2020")[:2] == ("Chevrolet", "Malibu 2")
assert find_car("Malibu2 2.4 atmasferni mator")[:2] == ("Chevrolet", "Malibu 2")
assert find_car("Li 9 Livis\nYili: 2026")[:2] == ("Lixiang", "L9")
assert find_car("L7 pro\n2024")[:2] == ("Lixiang", "L7")
assert find_car("Gac Aion i60 ADVANCED\n- 2026")[:2] == ("GAC", "Aion i60")
assert find_car("🔥 SOTUVDA — MERCEDES-BENZ G63 AMG 🔥")[:2] == ("Mercedes-Benz", "G63")
assert find_car("Byd Song Plus\nYili 2023")[:2] == ("BYD", "Song Plus")
assert find_car("Bmw 540i \nГод выпуска: 2017")[:2] == ("BMW", "540i")
assert find_car("BARAKA BOLDI🤝\nVoyah Free 318")[:2] == ("Voyah", "Free")
assert find_car("Dong Feng 008 EV 635 km")[:2] == ("Dongfeng", "008")
assert find_car("Bugun yangi partiya keldi")[0] is None

# Год
assert find_year_tg("▫️Yili-2015", None) == 2015
assert find_year_tg("▪️Yili - 1986 ", None) == 1986
assert find_year_tg("📆 2023\n👣 125.000 KM", None) == 2023
assert find_year_tg("📅 Выпуск: 05.2026", None) == 2026
assert find_year_tg("Год выпуска: 2026/04", None) == 2026
assert find_year_tg("- 23.12.2024\n- 22000 km", None) == 2024
assert find_year_tg("▪️2021 йил", None) == 2021
assert find_year_tg("Narxi 2025$\n📞 2024", "Toyota LC 300 3.5 turbo 2024") == 2024
assert find_year_tg("Narxi: 38 800$\n☎️+998(94)662-11-27", None) is None

# Пробег
assert find_mileage_tg("Probek: 20 000\nYili: 2024") == 20000
assert find_mileage_tg("PRABEG : 240.000") == 240000
assert find_mileage_tg("📍 Пробег: 1 300 км") == 1300
assert find_mileage_tg("Gentra\n▫️255.000 km") == 255000
assert find_mileage_tg("Yurgani 45 ming") == 45000
assert find_mileage_tg("Bez probeg") == 0
assert find_mileage_tg("Byd Champion 520 km EV\nNarxi 21950$") is None  # запас хода, не пробег
assert find_mileage_tg("Aion\n- 650km zapas xod") is None

# Цена: зачёркнутая старая не берётся
assert price_of("Narxi: 48 500$❌ 46 000$✅") == 46000

assert price_of("BYD Sealion 06\nНархи💵3️⃣1️⃣.6️⃣0️⃣0️⃣") == 31600
assert price_of("💰 CIP Узбекистан: $36-37 000") == 36000
assert price_of("🔑 ПОД КЛЮЧ — $255 000\n☝️ Предоплата для бронирования — $10 000") == 255000

# Вид поста
assert parse_post(post("Zeekr 001 \nProbek: 20 000\nYili: 2024 \nNarxi: 38 800$ \n‼️SOTILDI‼️"))["kind"] == "listing"
assert parse_post(post("Zeekr 001 \nProbek: 20 000\nYili: 2024 \nNarxi: 38 800$ \n‼️SOTILDI‼️"))["is_sold"]
assert parse_post(post("🔷Gac S9 2025 Ultra 32000$ Cip tashkent\n🔷Buyurtma asosida yetqazib beramiz"))["kind"] == "catalog"
assert parse_post(post("BMW M2 Coupé\n📅 Выпуск: 05.2026\n📍 Пробег: 1 300 км\n💰 CIP Узбекистан: $60 000"))["kind"] == "listing"
assert parse_post(post("XPENG G9L\n702Max 39000$\n660Ultra SE 42500$\n660Ultra 46500$"))["kind"] == "catalog"
assert parse_post(post("Сотилди 🤝"))["kind"] == "sold_notice"
assert parse_post(post("TESLA ЯНГИ ROADSTER’НИ КЎРСАТДИ: ҳавога кўтарилиш!"))["kind"] == "other"
assert parse_post(post("HAMIDOV AUTO pinned «Porsche 911 GT3 Пробег: 1230км CIP Узбекистан: 248,000 $»"))["kind"] == "other"

# Прошлая цена из истории правок
changed = parse_post(post("Zeekr 001\nYili: 2024\nNarxi: 36 200$", history=[{"until": "2026-11-05T00:00:00Z", "text": "Zeekr 001\nYili: 2024\nNarxi: 38 800$"}]))
assert changed["price"] == 36200 and changed["price_history"] == [{"until": "2026-11-05T00:00:00Z", "price": 38800}]

print("ok: марка и модель, год, пробег, цена, вид поста, история цены")
