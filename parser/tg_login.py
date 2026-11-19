"""Вход в Telegram для парсера. Запускается один раз руками в терминале.

Нужен, чтобы качать тяжёлые видео: открытая страница t.me/s их не отдаёт, только через аккаунт.
Перед запуском в parser/.env должны быть строки (берутся на my.telegram.org → API development tools):
  TG_API_ID=1234567
  TG_API_HASH=abcdef...

  .venv/bin/python tg_login.py

Спросит номер телефона и код, который придёт в Telegram (и пароль, если включена двухэтапная защита).
Вход сохраняется в parser/tg.session. Этот файл как ключ от аккаунта: никому не отдавать, в git он не попадает.
"""

from tg_client import SESSION_FILE, make_client


def main() -> None:
    client = make_client()
    if client is None:
        return
    client.start()  # сама спросит номер, код и пароль
    me = client.get_me()
    print(f"Готово: вошли как {me.first_name} (@{me.username}). Сессия: {SESSION_FILE}.session")
    client.disconnect()


if __name__ == "__main__":
    main()
