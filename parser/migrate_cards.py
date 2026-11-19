"""Разовый переезд архива на Google Диске в папки постов (раскладка из card_paths.py).

Что переносит (всё внутри Диска, файлы не копируются, а переименовываются):
  фото     <архив>/data/_tg/<канал>/images/<id>_N.jpg  →  <архив>/cards/<канал>/<день>_<id>/photo_NN.jpg
           и перевешивает ярлык на Маке (data/_tg/<канал>/images/<id>_N.jpg) на новое место
  ролики   <архив>/data/_tg/<канал>/videos/<id>.mp4    →  .../<день>_<id>/video.mp4
  кадры    <архив>/videos/<канал>/tg-<канал>-<id>/     →  .../<день>_<id>/frames/
  текст    кладёт post.txt в папку каждого поста с фото или видео

Запускать только на Маке (ярлыки ведут на пути Мака) и когда не идут парсер и видеопрогон:
скрипт сам проверяет замки и на время работы занимает их.
Можно прерывать и запускать снова: уже перенесённое пропускается.

  .venv/bin/python migrate_cards.py --dry-run                 посчитать, ничего не менять
  .venv/bin/python migrate_cards.py --dry-run aslauto         только один канал
  .venv/bin/python migrate_cards.py aslauto                   перенести один канал (проба)
  .venv/bin/python migrate_cards.py                           перенести все каналы
"""

from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

from accounts import DATA_DIR, PARSER_DIR
from archive import archive_dir_from_env
from card_paths import FRAMES_NAME, TG_DIR, VIDEO_NAME, CardIndex, write_text

LOCKS = [DATA_DIR / ".daily.lock", DATA_DIR / ".video.lock"]


def take_locks() -> list[Path]:
    """Занимает замки обоих прогонов. Если какой то занят живым процессом, возвращает пустой список."""
    taken = []
    for lock in LOCKS:
        try:
            lock.mkdir()
        except FileExistsError:
            pid = (lock / "pid").read_text().strip() if (lock / "pid").exists() else ""
            alive = pid.isdigit() and _alive(int(pid))
            if alive:
                release(taken)
                print(f"Сейчас идёт прогон ({lock.name}, процесс {pid}). Дождитесь конца и запустите снова.")
                return []
            # брошенный замок: процесса уже нет
        (lock / "pid").write_text(str(os.getpid()))
        taken.append(lock)
    return taken


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def release(locks: list[Path]) -> None:
    for lock in locks:
        (lock / "pid").unlink(missing_ok=True)
        try:
            lock.rmdir()
        except OSError:
            pass


def repoint(link: Path, target: Path) -> None:
    """Перевешивает ярлык одним движением: файл по старому пути ни на миг не пропадает."""
    temp = link.with_name(link.name + ".lnk-tmp")
    if temp.is_symlink() or temp.exists():
        temp.unlink()
    temp.symlink_to(target)
    os.replace(temp, link)


def move(source: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    os.rename(source, target)


def migrate_channel(channel: str, archive: Path, cards: CardIndex, dry_run: bool, count: Counter, errors: list[str]) -> None:
    posts = cards.channel_posts(channel)

    def attempt(what: str, action) -> None:
        try:
            action()
        except OSError as error:
            count[f"{what}: ошибка"] += 1
            if len(errors) < 8:
                errors.append(f"{channel} {what}: {error}")

    # Фото: по ярлыкам на Маке
    for post_id, post in posts.items():
        has_media = False
        for name in post.get("images") or []:
            local = PARSER_DIR / name
            target = cards.photo_target(archive, name)
            if target is None:
                continue
            has_media = True
            if not local.is_symlink():
                count["фото: ещё файлом на Маке (перенесёт archive.py)" if local.exists() else "фото: нет ни файла, ни ярлыка"] += 1
                continue
            current = Path(os.readlink(local))
            if current == target:
                count["фото: уже на месте"] += 1
            elif current.exists() and not target.exists():
                def photo(current=current, target=target, local=local):
                    move(current, target, dry_run)
                    if not dry_run:
                        repoint(local, target)
                    count["фото: перенесено"] += 1
                attempt("фото", photo)
            elif target.exists():
                def relink(local=local, target=target):
                    if not dry_run:
                        repoint(local, target)
                    count["фото: ярлык перевешен"] += 1
                attempt("фото", relink)
            else:
                count["фото: ярлык ведёт в никуда"] += 1
        is_video = bool(post.get("video_url") or post.get("video_thumbs") or post.get("type") == "video")
        card = cards.card_dir(archive, channel, post_id)

        # Ролик
        old_video = archive / "data" / "_tg" / channel / "videos" / f"{post_id}.mp4"
        if is_video and old_video.exists():
            has_media = True
            if (card / VIDEO_NAME).exists():
                count["ролик: в папке поста уже есть, старый оставлен"] += 1
            else:
                def video(old_video=old_video, card=card):
                    move(old_video, card / VIDEO_NAME, dry_run)
                    count["ролик: перенесён"] += 1
                attempt("ролик", video)
        elif is_video and (card / VIDEO_NAME).exists():
            has_media = True
            count["ролик: уже на месте"] += 1

        # Раскадровка
        old_cut = archive / "videos" / channel / f"tg-{channel}-{post_id}"
        if old_cut.is_dir():
            if (card / FRAMES_NAME).exists():
                count["кадры: в папке поста уже есть, старые оставлены"] += 1
            else:
                def cut(old_cut=old_cut, card=card):
                    move(old_cut, card / FRAMES_NAME, dry_run)
                    count["кадры: перенесены"] += 1
                attempt("кадры", cut)

        # Текст поста
        if has_media and not post.get("removed_at"):
            text = cards.text(channel, post_id)
            if text and not (card / "post.txt").exists():
                def put(card=card, text=text):
                    if not dry_run:
                        write_text(card, text)
                    count["текст: записан"] += 1
                attempt("текст", put)


def main() -> None:
    parser = argparse.ArgumentParser(description="Переезд архива в папки постов")
    parser.add_argument("channels", nargs="*", help="каналы, без них все")
    parser.add_argument("--dry-run", action="store_true", help="только посчитать")
    args = parser.parse_args()

    archive = archive_dir_from_env()
    if archive is None:
        return
    channels = args.channels or sorted(folder.name for folder in TG_DIR.iterdir() if (folder / "posts.json").exists())
    locks: list[Path] = []
    if not args.dry_run:
        locks = take_locks()
        if not locks:
            return
    count: Counter = Counter()
    errors: list[str] = []
    cards = CardIndex(TG_DIR)
    try:
        for number, channel in enumerate(channels, start=1):
            before = sum(count.values())
            migrate_channel(channel, archive, cards, args.dry_run, count, errors)
            print(f"[{number}/{len(channels)}] {channel}: действий {sum(count.values()) - before}", flush=True)
    finally:
        release(locks)
    print(f"\nИтог{' (проба, ничего не менялось)' if args.dry_run else ''}, архив {archive}:")
    for name in sorted(count):
        print(f"  {name}: {count[name]}")
    for line in errors:
        print(f"  ! {line}")
    if count and not any(key.endswith("ошибка") for key in count) and not args.dry_run:
        print("Готово. Старые папки <архив>/data/_tg/<канал>/images и videos и <архив>/videos теперь должны быть пустыми.")


if __name__ == "__main__":
    main()
