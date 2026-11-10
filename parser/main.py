"""Парсер объявлений об авто из Instagram.

Пока это заготовка: проверяет, что окружение и настройки на месте.
Сбор постов добавим на шаге 2.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PARSER_DIR = Path(__file__).parent

# Подхватываем настройки из parser/.env (если файл есть)
load_dotenv(PARSER_DIR / ".env")


def main() -> None:
    profile = os.getenv("INSTAGRAM_PROFILE", "auto_sale_abdulloh")
    print(f"Python {sys.version.split()[0]}")
    print(f"Профиль для парсинга: {profile}")
    print("Окружение готово. Сбор постов появится на шаге 2.")


if __name__ == "__main__":
    main()
