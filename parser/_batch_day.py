"""Проба на один день в пакетном режиме Gemini (вдвое дешевле, ответ в течение суток).

Берёт объявления за один день и прогоняет платные шаги схемы:
  4б  дорисовка краёв обложки (у объявлений с фото, где машина не влезла в рамку 4:3)
  5б  Gemini смотрит ролик: кадры по ракурсам, цена из голоса и надписи, год, пробег
  5в  четыре фото одной сеткой из кадров (запускается после 5б, когда известны кадры)
Бесплатные шаги (выбор обложки, рамка, нарезка кадров, разрезание сетки) идут на Маке.

Ничего не меняет в проекте и на сайте. Всё лежит в ~/Movies/uz-avto-lab/day-test/<дата>/:
  <id>/...          фото, кадры, обложки по каждому объявлению
  state.json        что отправлено и что получено
  report.json       итог и расходы, _sheet_*.jpg листы для просмотра

  .venv/bin/python _batch_day.py start               объявления за вчера: подготовка и отправка пакетов 4б и 5б
  .venv/bin/python _batch_day.py start 2026-11-17    за конкретный день
  .venv/bin/python _batch_day.py check               забрать готовое, отправить 5в, показать расходы
  .venv/bin/python _batch_day.py check --wait        то же, но ждать и проверять каждые 3 минуты до конца
  .venv/bin/python _batch_day.py publish             выложить уже готовое на сайт «стало», не дожидаясь остального
  .venv/bin/python _batch_day.py unpublish           убрать пробу со второго сайта

Сравнение «было и стало»: обычный сайт на порту 3000 (npm run dev) показывает как сейчас, второй на порту 3001
(npm run dev:new) подставляет результат пробы из src/data/preview-overlay.json и public/preview/.
"""
import base64
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from accounts import PARSER_DIR
from tg_parse import TG_DIR
from tg_video import Places, find_ffmpeg
import video_frames as vf
import _cover_test as cover
import _cover_test_outpaint as outpaint
import _frames_test_grid as grid

ROOT = Path.home() / "Movies" / "uz-avto-lab" / "day-test"
TASHKENT = timezone(timedelta(hours=5))
VIDEO_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.8-flash"
IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "").strip() or "gemini-nano-banana-2.1"
DONE_STATES = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
# Цены пакетного режима, $ за 1 млн токенов (половина обычных со страницы тарифов 17.11.2026). Для оценки расходов.
PRICE = {VIDEO_MODEL: {"in": 0.375, "out": 1.875, "image": 1.875},
         IMAGE_MODEL: {"in": 0.75, "out": 3.75, "image": 15.0}}
SLOTS = {"front_3q": 2, "front": 1, "side": 2, "rear_3q": 2, "rear": 1, "interior": 3}

VIDEO_PROMPT = """This is a seller's video of a used car for sale in Uzbekistan. Do two things.

A. Photo editor. For each slot find the best moments for a listing photo (at most the number given):
- front_3q (2): the whole car diagonally from the front corner
- front (1): the whole car straight from the front
- side (2): the whole car exactly from the side
- rear_3q (2): the whole car diagonally from the back corner
- rear (1): the whole car straight from behind
- interior (3): wide views of the cabin: dashboard, steering wheel and front seats
For every slot choose the moment filmed from as far away as possible, where the whole car is inside the frame
and as much of the surroundings as possible is visible. Prefer a steady camera, a sharp image, no person or hand
blocking the car and no text overlay. Moments of one slot must be at least 2 seconds apart and look different.
Do not put the same view into two slots. If the video never shows a slot well, return an empty list for it:
a missing slot is better than a wrong one. Every "t" must be inside the video duration.

B. Facts. Sellers often say the price aloud (in Uzbek or Russian) or show it as text overlaid on the video.
Prices are usually in US dollars ("13 500", "13.5", "13 ming 500", "o'n uch yarim"), sometimes in Uzbek sum.
Report only what is really in the video. Do not guess and do not use your knowledge of market prices.
If the seller gives an approximate price ("a bit above ten thousand"), set "approx": true.
If the video shows more than one car for sale, set "cars_in_video" accordingly and report the first car.

Answer only JSON:
{"car": "make model colour as seen", "duration": seconds, "cars_in_video": number,
 "front_3q": [{"t": seconds}], "front": [...], "side": [...], "rear_3q": [...], "rear": [...], "interior": [...],
 "price_overlay": {"value": number, "currency": "USD"|"UZS", "t": seconds, "text": "exact overlay text"} | null,
 "price_voice": {"value": number, "currency": "USD"|"UZS", "t": seconds, "heard": "exact words", "approx": true|false} | null,
 "year": {"value": number, "source": "overlay"|"voice"} | null,
 "mileage_km": {"value": number, "source": "overlay"|"voice"} | null}"""


# ---------- общее

def client():
    load_dotenv(PARSER_DIR / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        sys.exit("Нет GEMINI_API_KEY в .env")
    from google import genai
    return genai.Client(api_key=key)


def load_state(folder: Path) -> dict:
    path = folder / "state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_state(folder: Path, state: dict) -> None:
    (folder / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def jpeg_part(image: Image.Image) -> dict:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88)
    return {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(buffer.getvalue()).decode()}}


def submit(api, folder: Path, name: str, model: str, lines: list[dict]) -> dict:
    """Пишет запросы в JSONL, загружает и создаёт пакетное задание. Возвращает запись для state.json."""
    from google.genai import types
    path = folder / f"batch_{name}.jsonl"
    with path.open("w", encoding="utf-8") as file:
        for line in lines:
            file.write(json.dumps(line, ensure_ascii=False) + "\n")
    uploaded = api.files.upload(file=str(path), config=types.UploadFileConfig(display_name=f"uz-avto-{name}", mime_type="jsonl"))
    job = api.batches.create(model=model, src=uploaded.name, config={"display_name": f"uz-avto-{name}"})
    print(f"Пакет {name}: отправлено запросов {len(lines)}, задание {job.name}", flush=True)
    return {"job": job.name, "model": model, "requests": len(lines), "sent": datetime.now().isoformat(timespec="seconds"),
            "collected": False}


def results(api, job) -> dict[str, dict]:
    """Ответы пакетного задания по ключам запросов."""
    raw = api.files.download(file=job.dest.file_name)
    out = {}
    for line in raw.decode("utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            out[item.get("key")] = item
    return out


def parts_of(item: dict) -> list[dict]:
    response = item.get("response") or {}
    candidates = response.get("candidates") or []
    return ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []


def text_of(item: dict) -> str:
    return "".join(part.get("text") or "" for part in parts_of(item) if not part.get("thought"))


def image_of(item: dict) -> Image.Image | None:
    for part in parts_of(item):
        blob = part.get("inlineData") or part.get("inline_data")
        if blob and blob.get("data"):
            return Image.open(io.BytesIO(base64.b64decode(blob["data"]))).convert("RGB")
    return None


def cost_of(item: dict, model: str) -> tuple[float, int]:
    """Оценка цены одного ответа по числу токенов."""
    usage = (item.get("response") or {}).get("usageMetadata") or {}
    prompt = usage.get("promptTokenCount") or 0
    thoughts = usage.get("thoughtsTokenCount") or 0
    answer = usage.get("candidatesTokenCount") or 0
    price = PRICE[model]
    is_image = model == IMAGE_MODEL
    dollars = (prompt * price["in"] + thoughts * price["out"] + answer * (price["image"] if is_image else price["out"])) / 1e6
    return dollars, usage.get("totalTokenCount") or (prompt + thoughts + answer)


def video_post(channel: str, listing_post: str, cache: dict) -> str:
    if channel not in cache:
        cache[channel] = json.loads((TG_DIR / channel / "posts.json").read_text(encoding="utf-8"))
    post = cache[channel].get(str(listing_post)) or {}
    return str(post.get("media_from") or listing_post)


# ---------- start

def start(day: str) -> None:
    folder = ROOT / day
    state = load_state(folder)
    if state.get("jobs"):
        sys.exit(f"За {day} пакеты уже отправлены. Дальше: .venv/bin/python _batch_day.py check")
    folder.mkdir(parents=True, exist_ok=True)
    listings = json.loads((TG_DIR / "listings.json").read_text(encoding="utf-8"))

    def local_day(item: dict) -> str:
        return datetime.fromisoformat(item["date"].replace("Z", "+00:00")).astimezone(TASHKENT).strftime("%Y-%m-%d")

    todays = [item for item in listings
              if item.get("brand") and item.get("kind") == "listing" and not item.get("is_sold") and local_day(item) == day]
    places, posts_cache = Places(), {}
    video_items, photo_items = [], []
    for item in todays:
        only_video = item.get("has_video") and len(item.get("images") or []) <= 1
        if only_video:
            channel = item["source_account"]
            vpost = video_post(channel, item["id"].rsplit("-", 1)[1], posts_cache)
            path = places.raw(channel, vpost)
            if path.exists():
                video_items.append((item, path))
        elif item.get("images"):
            photo_items.append(item)
    print(f"{day}: объявлений {len(todays)}, с фото {len(photo_items)}, только видео со скачанным роликом {len(video_items)}", flush=True)
    api = client()
    state = {"day": day, "listings": len(todays), "photo": [], "video": [], "jobs": {}}

    # Ветка фото: бесплатные шаги 1 и 2, затем запросы на дорисовку
    print("Ветка фото: выбираю обложки и рамки (локально, бесплатно)...", flush=True)
    classify = vf.load_clip("ViT-B-32", "laion2b_s34b_b79k")
    detect = cover.load_detector()
    outpaint_lines = []
    for item in photo_items:
        try:
            row = cover.pick_cover(item, folder / item["id"], classify, detect)
        except Exception as error:  # noqa: BLE001
            print(f"  {item['id']}: ошибка выбора обложки {type(error).__name__}: {str(error)[:120]}")
            continue
        if not row:
            continue
        state["photo"].append({"id": row["id"], "title": row["title"], "chosen": row["chosen"], "verdict": row["verdict"],
                               "changed_photo": row["changed_photo"]})
        if row["verdict"] == "нужна дорисовка":
            source = Image.open(folder / item["id"] / f"src_{row['chosen']}.jpg").convert("RGB")
            source.thumbnail((1280, 1280))
            car = f" ({row['title']})" if row.get("title") else ""
            outpaint_lines.append({"key": item["id"], "request": {
                "contents": [{"role": "user", "parts": [{"text": outpaint.PROMPT.replace("{car}", car)}, jpeg_part(source)]}],
                "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:3", "imageSize": "1K"}}}})
    counts = {}
    for row in state["photo"]:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    print(f"Обложки: {counts}", flush=True)
    save_state(folder, state)
    if outpaint_lines:
        state["jobs"]["outpaint"] = submit(api, folder, "outpaint", IMAGE_MODEL, outpaint_lines)
        save_state(folder, state)

    # Ветка видео: загрузка роликов и запросы 5б
    print(f"Ветка видео: загружаю {len(video_items)} роликов в Gemini...", flush=True)
    video_lines = []
    for number, (item, path) in enumerate(video_items, start=1):
        try:
            uploaded = api.files.upload(file=str(path))
            waited = 0
            while uploaded.state and uploaded.state.name == "PROCESSING" and waited < 180:
                time.sleep(3)
                waited += 3
                uploaded = api.files.get(name=uploaded.name)
            if uploaded.state and uploaded.state.name != "ACTIVE":
                raise RuntimeError(f"файл в состоянии {uploaded.state.name}")
        except Exception as error:  # noqa: BLE001
            print(f"  {item['id']}: ролик не загрузился, {type(error).__name__}: {str(error)[:120]}")
            continue
        state["video"].append({"id": item["id"], "title": item.get("title"), "video": str(path), "file": uploaded.name,
                               "post_price": item.get("price"), "post_year": item.get("year"), "post_mileage": item.get("mileage_km")})
        video_lines.append({"key": item["id"], "request": {
            "contents": [{"role": "user", "parts": [{"fileData": {"fileUri": uploaded.uri, "mimeType": "video/mp4"}},
                                                    {"text": VIDEO_PROMPT}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}})
        if number % 10 == 0:
            print(f"  загружено {number} из {len(video_items)}", flush=True)
            save_state(folder, state)
    if video_lines:
        state["jobs"]["video"] = submit(api, folder, "video", VIDEO_MODEL, video_lines)
    save_state(folder, state)
    print("Отправлено. Ответ приходит в течение суток, обычно быстрее. Проверка: .venv/bin/python _batch_day.py check --wait")


# ---------- check

def collect_outpaint(api, folder: Path, state: dict, job) -> None:
    info = state["jobs"]["outpaint"]
    got, dollars = 0, 0.0
    for key, item in results(api, job).items():
        image = image_of(item)
        if image is not None:
            image.save(folder / key / "cover_ai.jpg", quality=92)
            got += 1
        price, _ = cost_of(item, info["model"])
        dollars += price
    info.update({"collected": True, "got": got, "cost": round(dollars, 3)})
    print(f"Дорисовка: получено {got} из {info['requests']}, около ${dollars:.2f}", flush=True)


def collect_video(api, folder: Path, state: dict, job) -> None:
    """Ответы 5б: сохраняем факты, режем кадры и отправляем пакет 5в."""
    info = state["jobs"]["video"]
    ffmpeg = find_ffmpeg()
    by_id = {row["id"]: row for row in state["video"]}
    grid_lines, dollars, got = [], 0.0, 0
    for key, item in results(api, job).items():
        row = by_id.get(key)
        if not row:
            continue
        price, _ = cost_of(item, info["model"])
        dollars += price
        try:
            answer = json.loads(text_of(item))
        except ValueError:
            row["error"] = "ответ не разобран"
            continue
        got += 1
        out = folder / key
        (out / "frames").mkdir(parents=True, exist_ok=True)
        (out / "video.json").write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding="utf-8")
        row.update({"car": answer.get("car"), "price_voice": answer.get("price_voice"), "price_overlay": answer.get("price_overlay"),
                    "year": answer.get("year"), "mileage_km": answer.get("mileage_km"), "cars_in_video": answer.get("cars_in_video")})
        frames = {}
        for slot, count in SLOTS.items():
            picks = answer.get(slot) or []
            if isinstance(picks, dict):
                picks = [picks]
            for n, pick in enumerate(picks[:count], start=1):
                if not isinstance(pick, dict) or pick.get("t") is None:
                    continue
                name = slot if count == 1 else f"{slot}_{n}"
                target = out / "frames" / f"{name}.jpg"
                vf.full_frame(ffmpeg, Path(row["video"]), float(pick["t"]), target)
                if target.exists() and target.stat().st_size > 0:
                    frames[name] = target
        row["frames"] = sorted(frames)
        exterior = [frames[n] for n in grid.EXTERIOR if n in frames][: grid.MAX_EXTERIOR]
        interior = [frames[n] for n in grid.INTERIOR if n in frames][: grid.MAX_INTERIOR]
        if len(exterior) < 2:
            row["grid"] = "пропуск: мало внешних кадров"
            continue
        car = answer.get("car") or ""
        prompt = (grid.PROMPT.replace("{car}", f" ({car})" if car else "")
                  .replace("{fourth}", grid.FOURTH_INTERIOR if interior else grid.FOURTH_REAR))
        row["tiles"] = ["main", "front", "side", "interior" if interior else "rear_3q"]
        grid_lines.append({"key": key, "request": {
            "contents": [{"role": "user", "parts": [{"text": prompt}] + [jpeg_part(grid.load(p)) for p in exterior + interior]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:3", "imageSize": grid.GRID_SIZE}}}})
        try:
            api.files.delete(name=row["file"])
        except Exception:  # noqa: BLE001
            pass
    info.update({"collected": True, "got": got, "cost": round(dollars, 3)})
    print(f"Видео: разобрано {got} из {info['requests']}, около ${dollars:.2f}", flush=True)
    save_state(folder, state)
    if grid_lines and "grid" not in state["jobs"]:
        state["jobs"]["grid"] = submit(api, folder, "grid", IMAGE_MODEL, grid_lines)


def collect_grid(api, folder: Path, state: dict, job) -> None:
    info = state["jobs"]["grid"]
    by_id = {row["id"]: row for row in state["video"]}
    got, dollars = 0, 0.0
    for key, item in results(api, job).items():
        price, _ = cost_of(item, info["model"])
        dollars += price
        image, row = image_of(item), by_id.get(key)
        if image is None or not row:
            if row:
                row["grid"] = "модель не вернула картинку"
            continue
        out = folder / key / "generated"
        out.mkdir(exist_ok=True)
        image.save(out / "grid.jpg", quality=92)
        grid.split(image, row["tiles"], out)
        row["grid"] = "ok"
        got += 1
    info.update({"collected": True, "got": got, "cost": round(dollars, 3)})
    print(f"Сетки: получено {got} из {info['requests']}, около ${dollars:.2f}", flush=True)


def report(folder: Path, state: dict) -> None:
    jobs = state["jobs"]
    total = sum(info.get("cost") or 0 for info in jobs.values())
    video = state["video"]
    with_price = [row for row in video if (row.get("price_voice") or row.get("price_overlay"))]
    new_price = [row for row in with_price if not row.get("post_price")]
    summary = {
        "day": state["day"], "listings": state["listings"],
        "photo_listings": len(state["photo"]),
        "covers_ready_free": sum(1 for row in state["photo"] if row["verdict"] == "готово"),
        "covers_outpainted": jobs.get("outpaint", {}).get("got", 0),
        "video_listings": len(video), "video_parsed": jobs.get("video", {}).get("got", 0),
        "price_from_video": len(with_price), "price_new_where_post_had_none": len(new_price),
        "grids": jobs.get("grid", {}).get("got", 0),
        "cost_usd": {name: info.get("cost") for name, info in jobs.items()}, "cost_total_usd": round(total, 2),
    }
    (folder / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    tw, th = 400, 300
    # Лист обложек: как сейчас / рамка / дорисовка
    ai = [row for row in state["photo"] if (folder / row["id"] / "cover_ai.jpg").exists()]
    for page, start_at in enumerate(range(0, len(ai), 5), start=1):
        part = ai[start_at:start_at + 5]
        sheet = Image.new("RGB", (5 * (tw + 8), 3 * (th + 6) + 34), "white")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(part):
            x = index * (tw + 8)
            draw.text((x + 4, 6), (row["title"] or "")[:34], fill="black", font=font)
            for k, name in enumerate(("before.jpg", "after.jpg", "cover_ai.jpg")):
                sheet.paste(Image.open(folder / row["id"] / name).convert("RGB").resize((tw, th)), (x, 32 + k * (th + 6)))
        sheet.save(folder / f"_sheet_covers_{page}.jpg", quality=86)
    # Лист видео: четыре фото из сетки
    done = [row for row in video if row.get("grid") == "ok"]
    for page, start_at in enumerate(range(0, len(done), 6), start=1):
        part = done[start_at:start_at + 6]
        sheet = Image.new("RGB", (4 * (tw + 8), len(part) * (th + 34)), "white")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(part):
            y = index * (th + 34)
            voice = row.get("price_voice") or row.get("price_overlay") or {}
            draw.text((4, y + 4), f"{(row.get('car') or row.get('title') or '')[:40]} | в посте {row.get('post_price') or 'нет'} | из видео {voice.get('value') or 'нет'}",
                      fill="black", font=font)
            for k, name in enumerate(row["tiles"]):
                sheet.paste(Image.open(folder / row["id"] / "generated" / f"{name}.jpg").convert("RGB").resize((tw, th)), (k * (tw + 8), y + 30))
        sheet.save(folder / f"_sheet_video_{page}.jpg", quality=86)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"Листы и report.json: {folder}")
    publish(folder, state)


SITE_DIR = PARSER_DIR.parent
OVERLAY_FILE = SITE_DIR / "src" / "data" / "preview-overlay.json"


def publish(folder: Path, state: dict) -> None:
    """Кладёт результат пробы на второй сайт «стало» (npm run dev:new, порт 3001).
    Обычный сайт не меняется: он этот файл не читает."""
    import shutil
    day = state["day"]
    target_root = SITE_DIR / "public" / "preview" / day
    entries = {}

    def put(listing_id: str, source: Path, name: str) -> str:
        target = target_root / listing_id / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return f"/preview/{day}/{listing_id}/{name}"

    for row in state["photo"]:
        source_dir = folder / row["id"]
        if (source_dir / "cover_ai.jpg").exists():
            kind, cover_file = "outpaint", source_dir / "cover_ai.jpg"
        elif (source_dir / "after.jpg").exists():
            kind, cover_file = "crop", source_dir / "after.jpg"
        else:
            continue
        photos = [put(row["id"], cover_file, "cover.jpg")]
        for album_photo in sorted(source_dir.glob("src_*.jpg"), key=lambda path: int(path.stem.split("_")[1])):
            photos.append(put(row["id"], album_photo, album_photo.name))
        entries[row["id"]] = {"kind": kind, "cover": photos[0], "photos": photos}

    for row in state["video"]:
        entry = {}
        if row.get("grid") == "ok":
            photos = [put(row["id"], folder / row["id"] / "generated" / f"{name}.jpg", f"{name}.jpg") for name in row["tiles"]]
            entry.update({"kind": "generated", "cover": photos[0], "photos": photos})
        voice, overlay = row.get("price_voice") or {}, row.get("price_overlay") or {}
        found = overlay if overlay.get("value") and overlay.get("currency") == "USD" else voice
        if found.get("value") and found.get("currency") == "USD":
            entry.update({"price": int(found["value"]), "priceSource": "overlay" if found is overlay else "voice",
                          "priceApprox": bool(found.get("approx"))})
        for key, field in (("year", "year"), ("mileage", "mileage_km")):
            value = (row.get(field) or {}).get("value") if isinstance(row.get(field), dict) else None
            if isinstance(value, (int, float)) and value >= 0:
                entry[key] = int(value)
        if entry:
            entry.setdefault("kind", "crop")
            entries[row["id"]] = entry
    OVERLAY_FILE.write_text(json.dumps({"day": day, "listings": entries}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"На сайт «стало» выложено объявлений: {len(entries)}. Запуск второго сайта: npm run dev:new, "
          f"потом http://localhost:3001/cars?day={day}&hideSold=1 (было: http://localhost:3000/cars?day={day}&hideSold=1)")


def check(wait: bool) -> None:
    days = sorted(p.name for p in ROOT.iterdir() if (p / "state.json").exists()) if ROOT.exists() else []
    if not days:
        sys.exit("Нет отправленных пакетов. Сначала: .venv/bin/python _batch_day.py start")
    folder = ROOT / days[-1]
    state = load_state(folder)
    api = client()
    collectors = {"outpaint": collect_outpaint, "video": collect_video, "grid": collect_grid}
    while True:
        pending = []
        for name in ("outpaint", "video", "grid"):
            info = state["jobs"].get(name)
            if not info or info.get("collected"):
                continue
            job = api.batches.get(name=info["job"])
            status = job.state.name if job.state else "?"
            info["state"] = status
            print(f"{datetime.now().strftime('%H:%M')} пакет {name}: {status}", flush=True)
            if status == "JOB_STATE_SUCCEEDED":
                collectors[name](api, folder, state, job)
                save_state(folder, state)
            elif status in DONE_STATES:
                info["collected"] = True
                info["failed"] = str(getattr(job, "error", "") or status)[:300]
                save_state(folder, state)
            else:
                pending.append(name)
        # после сбора видео мог появиться новый пакет сеток
        not_collected = [n for n, info in state["jobs"].items() if not info.get("collected")]
        save_state(folder, state)
        if not not_collected:
            report(folder, state)
            return
        if not wait:
            print(f"Ещё в работе: {', '.join(not_collected)}. Повтори check позже или запусти check --wait.")
            return
        time.sleep(180)


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["start"]:
        day = args[1] if len(args) > 1 else (datetime.now(TASHKENT) - timedelta(days=1)).strftime("%Y-%m-%d")
        start(day)
    elif args[:1] == ["check"]:
        check("--wait" in args)
    elif args[:1] == ["publish"]:  # выложить на сайт «стало» то, что уже готово, не дожидаясь остальных пакетов
        days = sorted(p.name for p in ROOT.iterdir() if (p / "state.json").exists())
        publish(ROOT / days[-1], load_state(ROOT / days[-1]))
    elif args[:1] == ["unpublish"]:  # убрать пробу со второго сайта
        OVERLAY_FILE.write_text(json.dumps({"day": None, "listings": {}}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("Сайт «стало» снова показывает то же, что обычный.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
