"""Архив на Google Диске: резервная копия данных и переезд старых фото.

Диск подключён к Маку как обычная папка (приложение «Google Диск для компьютера»,
режим потоковой передачи), поэтому здесь нет ни API Google, ни ключей: только копирование файлов.

Что делает за один запуск:
  1. Резервная копия: все небольшие файлы данных (json, csv, txt) копируются в <архив>/backup/.
     Фото можно скачать заново, а историю правок и удалений постов нельзя.
  2. Переезд фото: картинки постов Telegram переносятся в папку поста на Диске
     (<архив>/cards/<канал>/<день>_<id>/photo_NN.jpg, см. card_paths.py), а на их месте остаётся
     ссылка (symlink) на файл в архиве. С 19.11.2026 переносятся все фото сразу, а не только старые:
     на Маке остаются ссылки и рабочие файлы парсера, место на диске Мака проект больше не занимает.
     Остальные скрипты ничего не замечают: открывают фото по старому пути, Диск сам его подтянет.
     Если Диск не принял файл (нет сети, занят), оригинал остаётся на Маке и уедет в следующий запуск.

Обложки, которые уже стоят на сайте (public/tg), остаются на Маке: это жёсткие ссылки на те же данные.

Путь к архиву задаётся в parser/.env строкой ARCHIVE_DIR="...". Нет строки или Диск не подключён:
скрипт ничего не делает и выходит.

Запуск:
  python archive.py --dry-run   только показать, что было бы сделано
  python archive.py             сделать
  python archive.py --days 14   переносить только фото постов старше 14 дней (как было до 19.11.2026)
  python archive.py --limit 500 не больше 500 фото за запуск
"""

import argparse
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from accounts import DATA_DIR, PARSER_DIR
from card_paths import CardIndex, write_text

ARCHIVE_AFTER_DAYS = 0  # сколько дней фото поста живут на Маке. 0: уезжают на Диск сразу (до 19.11.2026 было 14)
MAX_FAILS_IN_ROW = 50  # столько отказов Диска подряд: дальше не пробуем, остальное уедет в следующий запуск
BACKUP_SUFFIXES = {".json", ".csv", ".txt"}
BACKUP_SKIP_DIRS = {"_scratch", "logs", "images"}  # черновики, логи и сами картинки в копию не идут


def archive_dir_from_env() -> Path | None:
    """Папка архива из .env. None, если не задана или Диск сейчас не подключён."""
    load_dotenv(PARSER_DIR / ".env")
    value = os.environ.get("ARCHIVE_DIR", "").strip()
    if not value:
        print("Архив не настроен: в .env нет строки ARCHIVE_DIR")
        return None
    path = Path(value).expanduser()
    # Саму папку архива создадим сами, но её родитель (Диск) должен уже быть на месте
    if not path.parent.is_dir():
        print(f"Диск не подключён, нет папки {path.parent}. Архив пропущен")
        return None
    return path


def same_file(source: Path, target: Path) -> bool:
    """Копия уже свежая: тот же размер и не старше исходника."""
    if not target.exists():
        return False
    a, b = source.stat(), target.stat()
    return a.st_size == b.st_size and b.st_mtime >= a.st_mtime - 1


def backup_data(data_dir: Path, archive_dir: Path, dry_run: bool) -> int:
    """Копирует небольшие файлы данных в <архив>/backup/. Возвращает, сколько файлов обновлено."""
    copied = 0
    for source in sorted(data_dir.rglob("*")):
        relative = source.relative_to(data_dir)
        if source.is_symlink() or not source.is_file() or source.suffix not in BACKUP_SUFFIXES:
            continue
        if BACKUP_SKIP_DIRS & set(relative.parts) or any(part.startswith(".") for part in relative.parts):
            continue
        target = archive_dir / "backup" / relative
        if same_file(source, target):
            continue
        if not dry_run:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            except OSError as error:
                # Диск иногда отказывает («Resource deadlock avoided»): этот файл повторим в следующий запуск,
                # а перенос фото ниже всё равно должен пройти
                print(f"Резервная копия: Диск не принял {relative} ({error.strerror or error}), повторю позже")
                continue
        copied += 1
    return copied


def old_post_images(data_dir: Path, parser_dir: Path, days: int) -> list[Path]:
    """Картинки постов Telegram, которые старше days дней (при 0 все) и ещё лежат на Маке (не ссылкой)."""
    border = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = []
    for posts_file in sorted((data_dir / "_tg").glob("*/posts.json")):
        posts = json.loads(posts_file.read_text(encoding="utf-8"))
        for post in posts.values():
            if post.get("date", "9") >= border:
                continue
            for name in post.get("images") or []:
                path = parser_dir / name
                if path.is_file() and not path.is_symlink():
                    found.append(path)
    return found


def move_to_archive(path: Path, parser_dir: Path, archive_dir: Path, cards: CardIndex | None = None) -> bool:
    """Переносит файл в архив и оставляет на его месте ссылку. False, если копия не сошлась.

    Фото поста ложится в папку поста (card_paths.py): <архив>/cards/<канал>/<день>_<id>/photo_NN.jpg,
    рядом кладётся текст поста. Файл с другим именем едет по старому: в <архив>/ с тем же путём.
    """
    relative = path.relative_to(parser_dir)
    target = cards.photo_target(archive_dir, relative.as_posix()) if cards else None
    if target is None:
        target = archive_dir / relative
    else:
        channel, post_id = relative.parts[2], path.name.split("_")[0]
        write_text(target.parent, cards.text(channel, post_id))
    target.parent.mkdir(parents=True, exist_ok=True)
    if not (target.exists() and target.stat().st_size == path.stat().st_size):
        shutil.copy2(path, target)
    if target.stat().st_size != path.stat().st_size:
        return False  # копия неполная: оригинал не трогаем
    # Ссылку создаём рядом и одним движением подменяем ею оригинал: файл ни на миг не пропадает
    link = path.with_name(path.name + ".lnk-tmp")
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)
    os.replace(link, path)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Резервная копия и архив фото на Google Диске")
    parser.add_argument("--dry-run", action="store_true", help="только показать, ничего не менять")
    parser.add_argument("--days", type=int, default=ARCHIVE_AFTER_DAYS, help="фото старше скольких дней переносить")
    parser.add_argument("--limit", type=int, default=0, help="не больше стольких фото за запуск, 0: без ограничения")
    args = parser.parse_args()

    archive_dir = archive_dir_from_env()
    if archive_dir is None:
        return
    note = " (проба, ничего не меняю)" if args.dry_run else ""
    print(f"Архив: {archive_dir}{note}")

    copied = backup_data(DATA_DIR, archive_dir, args.dry_run)
    print(f"  резервная копия: обновлено файлов {copied}")

    images = old_post_images(DATA_DIR, PARSER_DIR, args.days)
    size_mb = sum(path.stat().st_size for path in images) / 1e6
    batch = images[: args.limit] if args.limit else images
    which = f"старше {args.days} дней" if args.days else "постов"
    print(f"  фото {which} на Маке: {len(images)} ({size_mb:.0f} МБ), за этот запуск: {len(batch)}")
    if args.dry_run:
        return
    moved = failed = fails_in_row = 0
    cards = CardIndex(DATA_DIR / "_tg")
    for path in batch:
        try:
            ok = move_to_archive(path, PARSER_DIR, archive_dir, cards)
        except OSError as error:
            ok = False
            if failed < 3:
                print(f"  не удалось перенести {path.name}: {error}")
        if ok:
            moved += 1
            fails_in_row = 0
            continue
        failed += 1
        fails_in_row += 1
        if fails_in_row >= MAX_FAILS_IN_ROW:
            print(f"  Диск не принимает файлы ({MAX_FAILS_IN_ROW} отказов подряд): остановка, остальное в следующий запуск")
            break
    print(f"  перенесено в архив: {moved}, не удалось: {failed}, осталось на Маке: {len(images) - moved}")


if __name__ == "__main__":
    main()
