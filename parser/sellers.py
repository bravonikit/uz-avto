"""Продавцы и их входы: Instagram, Telegram, телефоны.

Два файла в data/sellers/ (в git не попадают, там телефоны):
  sellers.csv         один продавец на строку: seller_id, name, city, kind, status, note
  seller_sources.csv  все его входы: seller_id, platform, handle, access, note

platform: instagram, telegram, phone.
access:   open (качаем), private (нужен вход), closed (веб версия не отдаёт), none.
kind:     seller (продаёт свои машины) или aggregator (постит чужие, телефоны каждый раз разные).
status:   active или opted_out (попросил убрать: не качаем и не показываем ни из одного источника).

Файлы правятся руками. Скрипт только дописывает новое и ничего не удаляет.

Запуск:
  python sellers.py          создать файлы, если их нет, и дописать новые телефоны из постов
  python sellers.py check    показать телефоны, которые встречаются у разных продавцов
"""

import csv
import json
import re
import sys
from collections import Counter

from accounts import ACCOUNTS_FILE, DATA_DIR, clean_name

SELLERS_DIR = DATA_DIR / "sellers"
SELLERS_FILE = SELLERS_DIR / "sellers.csv"
SOURCES_FILE = SELLERS_DIR / "seller_sources.csv"
TG_DIR = DATA_DIR / "_tg"
TG_ACCOUNTS_FILE = ACCOUNTS_FILE.parent / "tg_accounts.txt"

SELLER_FIELDS = ["seller_id", "name", "city", "kind", "status", "note"]
SOURCE_FIELDS = ["seller_id", "platform", "handle", "access", "note"]

# Каналы, которые не качаются без входа: Instagram аккаунт → (канал, доступ). Сверено 13.11.2026
LOCKED_CHANNELS = {
    "turbosdelka.uz": ("+UVa3pHDvWLo0YTNi", "private"), "abozor.comfort": ("+jmsKoTE0DWYxYWEy", "private"),
    "germany_cars_uzb": ("+yDi5SQSiXGkyMTY8", "private"), "hmgroup.uz": ("+ETmfnYnu1mVkMjk1", "private"),
    "drivicouz": ("+EGO__zQWUd02M2Qy", "private"), "yaxshi.narxda": ("+sMCpvB4_m1Y3MWNi", "private"),
    "mirjalol_auto_sale": ("+ej7OZeu0uEA5Nzcy", "private"), "moshinachi__bola": ("+fnRXZ_ChrLs0MTIy", "private"),
    "gonzo_motors": ("GonzoCrib", "closed"), "budget_carsuz": ("Budget_cars", "closed"),
    "savlat__010": ("savlat010", "closed"), "arzon_yoki_qimmatmi": ("SunnatovMoxir", "closed"),
    "carsofuzb": ("Autosaleuzb", "closed"),
}

# Коды операторов и Ташкента: отсекают цены и пробеги, похожие на телефон
PHONE_CODES = {"20", "33", "50", "55", "71", "77", "78", "88", "90", "91", "93", "94", "95", "97", "98", "99"}
PHONE_RE = re.compile(r"(?<!\d)(?:\+?998[\s().-]*)?\(?(\d{2})\)?[\s().-]*(\d{3})[\s().-]*(\d{2})[\s().-]*(\d{2})(?!\d)")
OWN_PHONE_SHARE = 0.3  # телефон считаем своим, если он в такой доле постов аккаунта
OWN_PHONE_MIN_POSTS = 3  # или хотя бы в стольких постах
AGGREGATOR_PHONES = 8  # столько разных телефонов и ни одного своего: это агрегатор


def find_phones(text: str) -> set[str]:
    """Телефоны из текста в виде 998XXXXXXXXX."""
    return {"998" + "".join(match) for match in PHONE_RE.findall(text or "") if match[0] in PHONE_CODES}


def own_phones(texts: list[str]) -> tuple[list[str], int]:
    """(свои телефоны аккаунта, сколько всего разных телефонов встретилось)."""
    counts = Counter(phone for text in texts for phone in find_phones(text))
    need = max(OWN_PHONE_MIN_POSTS, OWN_PHONE_SHARE * len(texts))
    return [phone for phone, count in counts.most_common() if count >= need], len(counts)


def read_csv(path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, fields: list[str], rows: list[dict]) -> None:
    SELLERS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def instagram_accounts() -> list[str]:
    """Все аккаунты: из accounts.txt (и выключенные через #) и те, по которым есть посты."""
    names = []
    for line in ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("#").strip()
        if line and " " not in line and re.fullmatch(r"[\w.@/:?=&-]+", line):
            names.append(clean_name(line))
    names += [folder.name for folder in sorted(DATA_DIR.iterdir()) if (folder / "raw_posts.json").exists()]
    return list(dict.fromkeys(names))


def telegram_links() -> dict[str, tuple[str, str]]:
    """Instagram аккаунт → (канал, доступ) из tg_accounts.txt (и выключенные) и списка закрытых."""
    links = dict(LOCKED_CHANNELS)
    for line in TG_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().lstrip("#").strip().split()
        if len(parts) == 2 and re.fullmatch(r"[\w+]+", parts[0]) and re.fullmatch(r"[\w.,]+", parts[1]):
            for account in parts[1].lower().split(","):
                links[account] = (parts[0], "open")
    return links


def instagram_texts(account: str) -> list[str]:
    path = DATA_DIR / account / "raw_posts.json"
    return [post.get("description") or "" for post in json.loads(path.read_text(encoding="utf-8"))] if path.exists() else []


def telegram_texts(channel: str) -> list[str]:
    path = TG_DIR / channel / "posts.json"
    if not path.exists():
        return []
    return [post["text"] for post in json.loads(path.read_text(encoding="utf-8")).values() if post["text"]]


def build() -> None:
    sellers, sources = read_csv(SELLERS_FILE), read_csv(SOURCES_FILE)
    known = {(row["platform"], row["handle"].lower()): row["seller_id"] for row in sources}
    next_id = max((int(row["seller_id"]) for row in sellers), default=0) + 1
    links = telegram_links()
    added = Counter()

    def add_source(seller_id: str, platform: str, handle: str, access: str, note: str = "") -> None:
        if (platform, handle.lower()) not in known:
            sources.append({"seller_id": seller_id, "platform": platform, "handle": handle, "access": access, "note": note})
            known[(platform, handle.lower())] = seller_id
            added[platform] += 1

    for account in instagram_accounts():
        channel, access = links.get(account, (None, None))
        # Два аккаунта с одним каналом это один продавец
        seller_id = known.get(("instagram", account)) or (channel and known.get(("telegram", channel.lower())))
        if not seller_id:
            seller_id = str(next_id)
            next_id += 1
            sellers.append({"seller_id": seller_id, "name": account, "city": "Ташкент", "kind": "seller", "status": "active", "note": ""})
            added["seller"] += 1
        add_source(seller_id, "instagram", account, "open")
        if channel:
            add_source(seller_id, "telegram", channel, access)

    # Телефоны: свои дописываем, агрегаторов помечаем
    by_seller = {row["seller_id"]: row for row in sellers}
    texts: dict[str, list[str]] = {}
    for row in sources:
        if row["platform"] == "instagram":
            texts.setdefault(row["seller_id"], []).extend(instagram_texts(row["handle"]))
        elif row["platform"] == "telegram" and row["access"] == "open":
            texts.setdefault(row["seller_id"], []).extend(telegram_texts(row["handle"]))
    for seller_id, seller_texts in texts.items():
        phones, distinct = own_phones(seller_texts)
        for phone in phones:
            if ("phone", phone) not in known:
                add_source(seller_id, "phone", phone, "none")
        seller = by_seller[seller_id]
        if not phones and distinct >= AGGREGATOR_PHONES and seller["kind"] == "seller" and not seller["note"]:
            seller["kind"] = "aggregator"
            seller["note"] = f"{distinct} разных телефонов в постах"

    write_csv(SELLERS_FILE, SELLER_FIELDS, sellers)
    write_csv(SOURCES_FILE, SOURCE_FIELDS, sources)
    kinds = Counter(row["kind"] for row in sellers)
    print(f"Продавцов {len(sellers)} (агрегаторов {kinds['aggregator']}), входов {len(sources)}. "
          f"Добавлено: продавцов {added['seller']}, Instagram {added['instagram']}, Telegram {added['telegram']}, телефонов {added['phone']}")


def check() -> None:
    """Один телефон у разных продавцов: возможно, это один продавец. Склеивать руками."""
    names = {row["seller_id"]: row["name"] for row in read_csv(SELLERS_FILE)}
    owners: dict[str, set[str]] = {}
    for row in read_csv(SOURCES_FILE):
        texts = instagram_texts(row["handle"]) if row["platform"] == "instagram" else telegram_texts(row["handle"]) if row["platform"] == "telegram" else []
        for phone in own_phones(texts)[0]:
            owners.setdefault(phone, set()).add(row["seller_id"])
    shared = {phone: ids for phone, ids in owners.items() if len(ids) > 1}
    for phone, ids in sorted(shared.items()):
        print(phone, "→", ", ".join(sorted(names[seller_id] for seller_id in ids)))
    print(f"Общих телефонов: {len(shared)}")


if __name__ == "__main__":
    check() if sys.argv[1:] == ["check"] else build()
