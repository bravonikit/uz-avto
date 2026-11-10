"""Показывает, что скачано по каждому аккаунту, и пишет то же в data/status.csv.

Запуск: python status.py
"""

import csv
from datetime import datetime, timedelta, timezone

from accounts import DATA_DIR, load_accounts
from state import load_state

TASHKENT_OFFSET_H = 5


def local(iso: str | None) -> str:
    """"2026-11-10T13:05:00Z" → "10.11 18:05" по Ташкенту."""
    if not iso:
        return "-"
    moment = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (moment + timedelta(hours=TASHKENT_OFFSET_H)).strftime("%d.%m %H:%M")


def main() -> None:
    state = load_state()
    accounts = load_accounts()
    rows = []
    for account in accounts:
        r = state.get(account, {})
        rows.append({
            "аккаунт": account,
            "последняя скачка": local(r.get("last_success")),
            "статус": r.get("status", "не качали"),
            "новых": r.get("new_last_run", ""),
            "всего постов": r.get("posts_total", ""),
            "свежий пост": local(r.get("newest_post")),
            "мог пропустить": "да" if r.get("maybe_missed") else "",
        })
    rows.sort(key=lambda row: (row["статус"] == "ok", row["последняя скачка"]))

    widths = {key: max(len(key), *(len(str(row[key])) for row in rows)) for key in rows[0]}
    print("  ".join(key.ljust(widths[key]) for key in widths))
    for row in rows:
        print("  ".join(str(row[key]).ljust(widths[key]) for key in widths))

    done = sum(1 for row in rows if row["статус"] == "ok")
    print(f"\nСкачано: {done} из {len(rows)}, ни разу не качали: {sum(1 for r in rows if r['статус'] == 'не качали')}")

    out = DATA_DIR / "status.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Таблица для Excel/Numbers: {out.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
