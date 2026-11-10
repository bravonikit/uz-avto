"""Файл состояния data/state.json: что и когда скачано по каждому аккаунту.

Пример записи:
  "auto_sale_abdulloh": {
    "last_run": "2026-11-10T13:05:00Z",      последняя попытка (UTC)
    "last_success": "2026-11-10T13:05:00Z",  последняя удачная скачка
    "status": "ok",                           или "ошибка: ..."
    "new_last_run": 3,                        новых постов в последний раз
    "posts_total": 53,                        всего постов в raw_posts.json
    "newest_post": "2026-11-10T09:12:00Z",    дата самого свежего поста
    "maybe_missed": false                     все посты новые, часть могли пропустить
  }
"""

import json

from accounts import DATA_DIR

STATE_FILE = DATA_DIR / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
