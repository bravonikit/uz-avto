"""Общие настройки для всех шагов парсера: список аккаунтов и папки с их данными.

Данные каждого аккаунта лежат отдельно:
  data/<аккаунт>/raw_posts.json
  data/<аккаунт>/prices.json
  data/<аккаунт>/images/<shortcode>.jpg
"""

import sys
from pathlib import Path

PARSER_DIR = Path(__file__).parent
DATA_DIR = PARSER_DIR / "data"
ACCOUNTS_FILE = PARSER_DIR / "accounts.txt"


def load_accounts() -> list[str]:
    """Аккаунты для работы.

    `python download.py name1 name2` → только эти аккаунты,
    без аргументов → все из accounts.txt.
    """
    if len(sys.argv) > 1:
        return [clean_name(name) for name in sys.argv[1:]]
    accounts = []
    for line in ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            name = clean_name(line)
            if name not in accounts:
                accounts.append(name)
    return accounts


def clean_name(name: str) -> str:
    """"@auto_sale_abdulloh", "instagram.com/auto_sale_abdulloh/?igsh=..." → "auto_sale_abdulloh"."""
    name = name.strip().split("?")[0].split("#")[0].rstrip("/")
    return name.split("/")[-1].lstrip("@").lower()


def account_dir(account: str) -> Path:
    return DATA_DIR / account
