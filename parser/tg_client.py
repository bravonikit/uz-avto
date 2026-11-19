"""Клиент Telegram (Telethon) для парсера: общий для tg_login.py и tg_video.py."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from accounts import PARSER_DIR

SESSION_FILE = PARSER_DIR / "tg"  # Telethon сам допишет .session


def credentials() -> tuple[int, str] | None:
    load_dotenv(PARSER_DIR / ".env")
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    if not api_id or not api_hash:
        return None
    return int(api_id), api_hash


def make_client():
    """Клиент без подключения. None, если нет Telethon или ключей в .env."""
    try:
        from telethon.sync import TelegramClient
    except ImportError:
        print("Нет Telethon. Поставьте: .venv/bin/pip install -r requirements.txt")
        return None
    keys = credentials()
    if not keys:
        print("Telegram API не настроен: в .env нет TG_API_ID и TG_API_HASH")
        return None
    # flood_sleep_threshold: короткие паузы от Telegram ждём сами, а не падаем
    return TelegramClient(str(SESSION_FILE), *keys, flood_sleep_threshold=120)


def connected_client():
    """Подключённый клиент с готовым входом. None, если входа ещё нет (нужен tg_login.py)."""
    client = make_client()
    if client is None:
        return None
    client.connect()
    if not client.is_user_authorized():
        print("Telegram: входа нет. Один раз запустите: .venv/bin/python tg_login.py")
        client.disconnect()
        return None
    return client
