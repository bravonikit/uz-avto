"""Ежедневная обработка карточек: обложка, фото из видео, цена и пробег из ролика, описание.

Опирается на _batch_day.py (те же шаги и запросы), но работает как постоянный шаг:
  * берёт объявления за вчера (или за указанный день), под заказ и CIP пропускает;
  * бесплатные шаги делает на Маке, платные отправляет в очередь Google (пакетный режим, вдвое дешевле);
  * не начинает день, если оценка расходов выше потолка (--budget, по умолчанию 6 долларов);
  * забирает готовые ответы и за прошлые дни, если они тогда не успели прийти;
  * кладёт результат на основной сайт: src/data/cards-overlay.json и public/cards/<id>/;
  * кладёт итог в папку поста на Google Диске (<папка поста>/result/ и card.json: что сделано и откуда каждое значение);
  * после этого удаляет рабочие файлы дня с Мака, остаются только state.json и итог.

Рабочая папка: parser/data/_cards/<день>/ (на Маке: в папке Диска много мелких записей идут с ошибками).

  .venv/bin/python cards_daily.py run                 вчерашний день: отправить, подождать до 45 минут, выложить
  .venv/bin/python cards_daily.py run 2026-11-18      конкретный день
  .venv/bin/python cards_daily.py run --wait 0        отправить и не ждать (ответы заберёт следующий запуск)
  .venv/bin/python cards_daily.py collect             только забрать готовое и выложить, новый день не начинать
  .venv/bin/python cards_daily.py status              что по дням: отправлено, получено, сколько стоило
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import _batch_day as bd
from accounts import DATA_DIR, PARSER_DIR
from archive import archive_dir_from_env
from card_paths import CardIndex

ROOT = DATA_DIR / "_cards"
bd.ROOT = ROOT  # _batch_day.start пишет рабочие файлы дня сюда
SITE_DIR = PARSER_DIR.parent
OVERLAY_FILE = SITE_DIR / "src" / "data" / "cards-overlay.json"
SITE_IMAGES = SITE_DIR / "public" / "cards"
ORDER = ("outpaint", "video", "text", "grid")  # сетки после видео: их пакет создаётся при сборе видео
COLLECTORS = {"outpaint": bd.collect_outpaint, "video": bd.collect_video, "text": bd.collect_text, "grid": bd.collect_grid}
# Средние цены одной операции по пробе 16.11.2026 (очередь Google), для оценки до отправки
PRICE_OUTPAINT, PRICE_VIDEO, PRICE_GRID, PRICE_TEXT = 0.026, 0.004, 0.043, 0.001
SHARE_OUTPAINT, SHARE_GRID = 0.51, 0.78  # доля фото на дорисовку и доля роликов, из которых выходит сетка


def day_folders() -> list[Path]:
    return sorted(p for p in ROOT.iterdir() if (p / "state.json").exists()) if ROOT.exists() else []


def pending(state: dict) -> list[str]:
    return [name for name, info in state.get("jobs", {}).items() if not info.get("collected")]


def estimate(day: str) -> tuple[int, int, float]:
    """Сколько объявлений дня пойдёт в обработку и сколько это примерно стоит: (с фото, только видео, доллары)."""
    listings = json.loads((bd.TG_DIR / "listings.json").read_text(encoding="utf-8"))
    photo = video = text = 0
    for item in listings:
        when = datetime.fromisoformat(item["date"].replace("Z", "+00:00")).astimezone(bd.TASHKENT).strftime("%Y-%m-%d")
        if when != day or not item.get("brand") or item.get("kind") != "listing" or item.get("is_sold"):
            continue
        if item.get("price_type") or item.get("removed_at") or item["id"] in bd.SKIP_IDS:
            continue
        if item.get("has_video") and len(item.get("images") or []) <= 1:
            video += 1
        elif item.get("images"):
            photo += 1
        if len((item.get("description") or "").strip()) >= bd.TEXT_MIN_CHARS:
            text += 1
    dollars = (photo * SHARE_OUTPAINT * PRICE_OUTPAINT + video * (PRICE_VIDEO + SHARE_GRID * PRICE_GRID) + text * PRICE_TEXT)
    return photo, video, dollars


SITE_LISTINGS = SITE_DIR / "src" / "data" / "instagram-listings.json"
PRICE_FIELDS = ("price", "priceSource", "priceApprox")


def reuse_reposts(day: str, archive: Path | None, cards: CardIndex) -> set[str]:
    """Повторы и перепосты дня, которые не надо обрабатывать за деньги. Возвращает их коды.

    * Перепост: на сайте объявление склеено в чужую карточку (лежит в её duplicate_ids или also_at).
      Его не обрабатываем совсем, машину показывает главная карточка.
    * Повтор: главная карточка на сайте, а у одного из её прошлых постов (duplicate_ids) карточка уже готова.
      Берём готовые файлы (обложку, фото, описание) под новым кодом. Цена всегда из нового поста:
      цена из видео остаётся, только если в новом посте цены нет. Решение Ника 19.11.2026.
    """
    if not SITE_LISTINGS.exists():
        return set()
    site = json.loads(SITE_LISTINGS.read_text(encoding="utf-8"))
    site = site if isinstance(site, list) else site.get("listings") or []
    main_ids = {item["id"]: item for item in site}
    merged = {}
    for item in site:
        for other in [*(item.get("duplicate_ids") or []), *(entry.get("id") for entry in item.get("also_at") or [] if isinstance(entry, dict))]:
            if other:
                merged[other] = item["id"]
    listings = json.loads((bd.TG_DIR / "listings.json").read_text(encoding="utf-8"))
    overlay = load_overlay()
    skip, reposts, repeats = set(), 0, 0
    for item in listings:
        if not candidate(item, day):
            continue
        code = item["id"]
        if code not in main_ids:
            if code in merged:
                skip.add(code)
                reposts += 1
            continue
        if code in overlay:
            continue
        ready = next((old for old in main_ids[code].get("duplicate_ids") or [] if old in overlay), None)
        if not ready:
            continue
        entry = dict(overlay[ready], reused_from=ready)
        if main_ids[code].get("price") is not None:
            for field in PRICE_FIELDS:
                entry.pop(field, None)
        overlay[code] = entry
        skip.add(code)
        repeats += 1
        if archive is not None and code.startswith("tg-"):
            channel, _, post_id = code[3:].rpartition("-")
            card = cards.card_dir(archive, channel, post_id)
            try:
                card.mkdir(parents=True, exist_ok=True)
                (card / "card.json").write_text(json.dumps(
                    {"id": code, "day": day, "processed_at": datetime.now().isoformat(timespec="seconds"),
                     "branch": "repeat", "reused_from": ready,
                     "price": "из нового поста" if main_ids[code].get("price") is not None else "из прошлой карточки"},
                    ensure_ascii=False, indent=1), encoding="utf-8")
            except OSError as error:
                print(f"  {code}: Диск не принял card.json ({error})")
    if repeats:
        OVERLAY_FILE.write_text(json.dumps({"updated": datetime.now().isoformat(timespec="seconds"), "listings": overlay},
                                           ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{day}: повторов с готовой карточкой {repeats} (перенесены бесплатно), перепостов в чужих карточках {reposts} (пропущены)", flush=True)
    return skip


def candidate(item: dict, day: str) -> bool:
    """Тот же отбор, что в _batch_day.start: объявление дня, в наличии, не продано и не удалено."""
    when = datetime.fromisoformat(item["date"].replace("Z", "+00:00")).astimezone(bd.TASHKENT).strftime("%Y-%m-%d")
    return (when == day and bool(item.get("brand")) and item.get("kind") == "listing" and not item.get("is_sold")
            and not item.get("price_type") and not item.get("removed_at"))


def collect_once(api, folder: Path, state: dict) -> list[str]:
    """Один проход по пакетам дня: готовые забирает. Возвращает имена тех, что ещё в работе."""
    for name in ORDER:
        info = state.get("jobs", {}).get(name)
        if not info or info.get("collected"):
            continue
        job = api.batches.get(name=info["job"])
        status = job.state.name if job.state else "?"
        info["state"] = status
        print(f"{datetime.now().strftime('%H:%M')} {state['day']} пакет {name}: {status}", flush=True)
        if status == "JOB_STATE_SUCCEEDED":
            COLLECTORS[name](api, folder, state, job)
        elif status in bd.DONE_STATES:
            info["collected"] = True
            info["failed"] = str(getattr(job, "error", "") or status)[:300]
        bd.save_state(folder, state)
    return pending(state)


def load_overlay() -> dict:
    if OVERLAY_FILE.exists():
        try:
            return json.loads(OVERLAY_FILE.read_text(encoding="utf-8")).get("listings") or {}
        except ValueError:
            pass
    return {}


def put(listing_id: str, source: Path, name: str) -> str:
    """Копия картинки туда, откуда её раздаёт сайт. Уже лежащую не трогаем."""
    target = SITE_IMAGES / listing_id / name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return f"/cards/{listing_id}/{name}"


def card_record(listing_id: str, day: str, entry: dict, photo_row: dict | None, video_row: dict | None, text_row: dict | None) -> dict:
    """Учёт по объявлению для card.json: что сделано и откуда взято каждое значение."""
    record: dict = {"id": listing_id, "day": day, "processed_at": datetime.now().isoformat(timespec="seconds"),
                    "branch": "video" if video_row else "photo" if photo_row else "text", "models": {"video_and_text": bd.VIDEO_MODEL, "image": bd.IMAGE_MODEL}}
    if photo_row:
        record["cover"] = {"source": {"outpaint": "фото продавца, края дорисованы ИИ", "crop": "фото продавца, обрезка 4:3"}.get(entry.get("kind"), "без изменений"),
                           "chosen_photo": photo_row.get("chosen"), "verdict": photo_row.get("verdict"),
                           "changed_photo": photo_row.get("changed_photo")}
    if video_row:
        record["video"] = {"file": video_row.get("video"), "car_seen": video_row.get("car"), "cars_in_video": video_row.get("cars_in_video"),
                           "frames": video_row.get("frames"), "grid": video_row.get("grid"), "tiles": video_row.get("tiles"),
                           "price_voice": video_row.get("price_voice"), "price_overlay": video_row.get("price_overlay"),
                           "year": video_row.get("year"), "mileage_km": video_row.get("mileage_km"),
                           "post_price": video_row.get("post_price"), "post_year": video_row.get("post_year"), "post_mileage": video_row.get("post_mileage")}
        if entry.get("kind") == "generated":
            record["cover"] = {"source": "4 фото сделаны ИИ по кадрам ролика"}
    if entry.get("price") is not None:
        record["price"] = {"value": entry["price"], "source": "надпись на видео" if entry.get("priceSource") == "overlay" else "голос продавца",
                           "approx": entry.get("priceApprox", False), "used_only_if_post_has_no_price": True}
    if text_row:
        record["description"] = {"source": "пересказ текста поста", "text": text_row["description"]}
    if video_row and video_row.get("speech_ru"):
        record["speech"] = {"source": "пересказ речи продавца в ролике", "text": video_row["speech_ru"]}
    if video_row and video_row.get("transcript"):
        record["transcript"] = {"source": "дословная расшифровка речи в ролике, язык оригинала", "file": "transcript.txt"}
    return record


def archive_result(archive: Path | None, cards: CardIndex, listing_id: str, record: dict, work: Path) -> bool:
    """Итог по объявлению в папку поста на Диске: result/ с картинками и card.json. False, если Диск не принял."""
    if archive is None:
        return False
    channel, _, post_id = listing_id[3:].rpartition("-")  # "tg-<канал>-<номер поста>"
    if not listing_id.startswith("tg-") or not channel:
        return False
    card = cards.card_dir(archive, channel, post_id)
    try:
        result = card / "result"
        result.mkdir(parents=True, exist_ok=True)
        files = [(work / "cover_ai.jpg", "cover.jpg")] if (work / "cover_ai.jpg").exists() else \
                [(work / "after.jpg", "cover.jpg")] if (work / "after.jpg").exists() else []
        if (work / "generated").is_dir():
            files += [(path, path.name) for path in sorted((work / "generated").glob("*.jpg"))]
        if (work / "video.json").exists():
            files.append((work / "video.json", "video.json"))
        for source, name in files:
            shutil.copyfile(source, result / name)
        (card / "card.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        if record.get("transcript") and (work / "video.json").exists():
            spoken = json.loads((work / "video.json").read_text(encoding="utf-8")).get("transcript") or ""
            (card / "transcript.txt").write_text(spoken.strip() + "\n", encoding="utf-8")
        return True
    except OSError as error:
        print(f"  {listing_id}: Диск не принял итог ({error}). Повторю в следующий запуск")
        return False


def publish_day(folder: Path, state: dict, overlay: dict, archive: Path | None, cards: CardIndex) -> int:
    """Выкладывает готовое по дню на сайт и в папки постов. Возвращает, сколько объявлений выложено."""
    entries = bd.build_entries(folder, state, put)
    overlay.update(entries)
    photo_rows = {row["id"]: row for row in state.get("photo") or []}
    video_rows = {row["id"]: row for row in state.get("video") or []}
    text_rows = {row["id"]: row for row in state.get("text") or []}
    finished = not pending(state)
    done = set(state.get("archived") or [])
    for listing_id in sorted(set(photo_rows) | set(video_rows) | set(text_rows)):
        if not finished or listing_id in done:
            continue
        record = card_record(listing_id, state["day"], entries.get(listing_id, {}), photo_rows.get(listing_id),
                             video_rows.get(listing_id), text_rows.get(listing_id))
        work = folder / listing_id
        if archive_result(archive, cards, listing_id, record, work):
            done.add(listing_id)
            shutil.rmtree(work, ignore_errors=True)  # рабочие файлы объявления больше не нужны
    state["archived"] = sorted(done)
    if finished:
        for name in ("batch_outpaint.jsonl", "batch_video.jsonl", "batch_grid.jsonl", "batch_text.jsonl"):
            (folder / name).unlink(missing_ok=True)  # запросы с картинками внутри: сотни мегабайт
    return len(entries)


def summary(state: dict) -> str:
    jobs = state.get("jobs", {})
    photo = state.get("photo") or []
    cost = sum(info.get("cost") or 0 for info in jobs.values())
    wait = pending(state)
    return (f"Карточки за {state['day']}: объявлений {state.get('listings')}, обложек обрезкой "
            f"{sum(1 for row in photo if row.get('verdict') == 'готово')}, дорисовано {jobs.get('outpaint', {}).get('got', 0)}, "
            f"видео разобрано {jobs.get('video', {}).get('got', 0)}, сеток {jobs.get('grid', {}).get('got', 0)}, "
            f"описаний {jobs.get('text', {}).get('got', 0)}, около ${cost:.2f}"
            + (f". Ещё в очереди Google: {', '.join(wait)}" if wait else ""))


def publish_all(only: list[Path] | None = None) -> None:
    overlay = load_overlay()
    archive, cards = archive_dir_from_env(), CardIndex()
    for folder in only if only is not None else day_folders():
        state = bd.load_state(folder)
        if state.get("published"):
            continue
        count = publish_day(folder, state, overlay, archive, cards)
        if not pending(state) and len(state.get("archived") or []) >= len(
                {row["id"] for key in ("photo", "video", "text") for row in state.get(key) or []}):
            state["published"] = True  # всё получено, выложено и убрано в папки постов: к этому дню больше не возвращаемся
        bd.save_state(folder, state)
        print(f"{summary(state)}. На сайте объявлений этого дня: {count}", flush=True)
    OVERLAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    OVERLAY_FILE.write_text(json.dumps({"updated": datetime.now().isoformat(timespec="seconds"), "listings": overlay},
                                       ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Сайт: в cards-overlay.json объявлений {len(overlay)}", flush=True)


def collect_all(api) -> None:
    for folder in day_folders():
        state = bd.load_state(folder)
        if pending(state):
            collect_once(api, folder, state)


def run(day: str, wait_minutes: int, budget: float) -> None:
    api = bd.client()
    collect_all(api)  # сначала хвосты прошлых дней
    folder = ROOT / day
    if not (folder / "state.json").exists() or not bd.load_state(folder).get("jobs"):
        bd.SKIP_IDS = reuse_reposts(day, archive_dir_from_env(), CardIndex())
        photo, video, dollars = estimate(day)
        print(f"{day}: в обработку с фото {photo}, только видео {video}, оценка расходов ${dollars:.2f} (потолок ${budget:.2f})", flush=True)
        if photo + video == 0:
            print("Обрабатывать нечего.")
        elif dollars > budget:
            print(f"Прогон карточек остановлен: оценка ${dollars:.2f} выше потолка ${budget:.2f}. "
                  f"Поднять потолок: cards_daily.py run {day} --budget {dollars + 1:.0f}")
        else:
            bd.start(day)
    else:
        print(f"{day}: пакеты уже отправлены, забираю ответы")
    deadline = time.time() + wait_minutes * 60
    while (folder / "state.json").exists():
        state = bd.load_state(folder)
        if not pending(state) or not collect_once(api, folder, state):
            break
        if time.time() >= deadline:
            print(f"Ответы пришли не все за {wait_minutes} мин. Остальное заберёт следующий запуск (cards_daily.py collect)")
            break
        time.sleep(180)
    publish_all()


def status() -> None:
    total = 0.0
    for folder in day_folders():
        state = bd.load_state(folder)
        total += sum(info.get("cost") or 0 for info in state.get("jobs", {}).values())
        print(summary(state) + (" [выложено]" if state.get("published") else ""))
    print(f"Всего дней: {len(day_folders())}, потрачено около ${total:.2f}. На сайте объявлений с обработкой: {len(load_overlay())}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ежедневная обработка карточек")
    parser.add_argument("command", choices=["run", "collect", "status"])
    parser.add_argument("day", nargs="?", help="день по Ташкенту, по умолчанию вчера")
    parser.add_argument("--wait", type=int, default=45, help="сколько минут ждать ответы очереди Google")
    parser.add_argument("--budget", type=float, default=6.0, help="потолок расходов на один день, доллары")
    args = parser.parse_args()
    if args.command == "status":
        status()
    elif args.command == "collect":
        collect_all(bd.client())
        publish_all()
    else:
        day = args.day or (datetime.now(bd.TASHKENT) - timedelta(days=1)).strftime("%Y-%m-%d")
        run(day, args.wait, args.budget)


if __name__ == "__main__":
    main()
