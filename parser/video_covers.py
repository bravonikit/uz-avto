"""Обложки видео объявлений из самого ролика, бесплатно, на Маке.

У объявлений «только видео» на сайте сейчас стоит превью Telegram: часто это лицо продавца.
Скрипт смотрит ролик целиком (1 кадр в секунду), находит кадры, где машина видна целиком
и крупно, без человека в кадре, и ставит лучший кадр обложкой. Ещё до 4 кадров идут в галерею:
бок, зад 3/4, перед, салон. Без Gemini и без денег: CLIP (ракурс) и детектор машин torchvision.

Как выбирается обложка (по очкам):
  * машина влезает в рамку 4:3 целиком, с отступом, и не упирается в край кадра: главное;
  * машина крупная: от четверти до 3/4 рамки;
  * ракурс: перед 3/4 лучше всего, потом перед, бок, зад 3/4, зад;
  * резкость и нормальная яркость;
  * человек в рамке (лицо продавца) сильно штрафуется.

Куда пишет:
  public/cards/<id>/vf_cover.jpg, vf_2.jpg ...       картинки для сайта (длинная сторона 1280)
  src/data/video-frames-overlay.json                 подложка для сайта. Карточки cards_daily.py
                                                     (сетка из видео, дорисовка) идут поверх неё
  <папка поста на Диске>/frames/cover_frame.jpg      копия обложки к посту
  data/_cards/video_covers_state.json                что сделано, чтобы продолжать с места
  ~/Movies/uz-avto-lab/video-covers/_sheet_N.jpg     листы «было / стало» для проверки глазами

  .venv/bin/python video_covers.py --limit 20          пробные 20 свежих, потом посмотреть листы
  .venv/bin/python video_covers.py                     все (свежие первыми), можно прерывать
  .venv/bin/python video_covers.py tg-aslauto-3691     конкретные объявления (заново)
  .venv/bin/python video_covers.py --with-sold         и проданные тоже

Считается на процессоре (как video_frames.py). Ролик тянется с Диска при чтении.
Объявления, уже обработанные cards_daily.py, пропускаются: там результат лучше.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import video_frames as vf
from _cover_test import crop_window, touches_edge
from accounts import DATA_DIR, PARSER_DIR
from tg_video import Places, find_ffmpeg

TG_DIR = DATA_DIR / "_tg"
SITE_DIR = PARSER_DIR.parent
OVERLAY_FILE = SITE_DIR / "src" / "data" / "video-frames-overlay.json"
CARDS_OVERLAY = SITE_DIR / "src" / "data" / "cards-overlay.json"
SITE_IMAGES = SITE_DIR / "public" / "cards"
STATE_FILE = DATA_DIR / "_cards" / "video_covers_state.json"
LOCK_FILE = DATA_DIR / "_cards" / ".video_covers.lock"
CHECK_DIR = Path.home() / "Movies" / "uz-avto-lab" / "video-covers"

SAMPLE_FPS = 1
MAX_SECONDS = 180
OUT_SIDE = 1280
EXTERIOR = {"front_3q": 1.0, "front": 0.8, "side": 0.65, "rear_3q": 0.6, "rear": 0.4}
GALLERY = ("side", "rear_3q", "front", "interior")  # что добавляем к обложке, по одному кадру
MIN_GAP = 2.0
SAVE_EVERY = 10


# ---------- модели

def load_detector():
    import os
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    import torch
    from torchvision.models.detection import (FasterRCNN_MobileNet_V3_Large_FPN_Weights,
                                              fasterrcnn_mobilenet_v3_large_fpn)
    weights = FasterRCNN_MobileNet_V3_Large_FPN_Weights.DEFAULT
    model = fasterrcnn_mobilenet_v3_large_fpn(weights=weights).eval()
    names, to_tensor = weights.meta["categories"], weights.transforms()

    def detect(image: Image.Image) -> tuple[list | None, list[list]]:
        """(самая большая машина или None, рамки людей)."""
        with torch.no_grad():
            found = model([to_tensor(image)])[0]
        car, car_area, people = None, 0.0, []
        for box, label, score in zip(found["boxes"].tolist(), found["labels"].tolist(), found["scores"].tolist()):
            name = names[label]
            if name == "person" and score >= 0.6:
                people.append(box)
            elif name in ("car", "truck", "bus") and score >= 0.5:
                area = (box[2] - box[0]) * (box[3] - box[1])
                if area > car_area:
                    car, car_area = box, area
        return car, people
    return detect


# ---------- оценка кадра

def person_share(people: list[list], window: tuple) -> float:
    """Какую долю рамки занимают люди (самый крупный)."""
    x0, y0, x1, y1 = window
    area = max((x1 - x0) * (y1 - y0), 1)
    best = 0.0
    for b in people:
        ix = max(0.0, min(b[2], x1) - max(b[0], x0))
        iy = max(0.0, min(b[3], y1) - max(b[1], y0))
        best = max(best, ix * iy / area)
    return best


def score_frame(f: dict, view: str, top_sharp: float) -> float:
    box, size = f["car"], f["size"]
    if box is None:
        return -1.0
    window, fits, inside = crop_window(size, box)
    f["window"], f["fits"], f["inside"] = window, fits, inside
    edge = touches_edge(size, box)
    car_share = (box[2] - box[0]) * (box[3] - box[1]) / max((window[2] - window[0]) * (window[3] - window[1]), 1)
    big = min(car_share / 0.45, 1.0) if car_share <= 0.8 else 0.6
    person = person_share(f["people"], window)
    sharp = min(f["sharp"] / top_sharp, 1.0)
    return ((1.2 if fits and not edge else 0.5 * inside)
            + 0.5 * big
            + 0.6 * EXTERIOR[view] * (0.5 + 0.5 * f["probs"][view])
            + 0.3 * sharp
            - (1.5 * min(person / 0.05, 1.0) if person > 0.01 else 0.0)
            - 0.6 * f["probs"].get("person", 0.0))


def ok_light(f: dict) -> bool:
    return 35 <= f["bright"] <= 225


# ---------- один ролик

def sample(ffmpeg: str, video: Path, folder: Path) -> list[Path]:
    vf.run(ffmpeg, "-i", str(video), "-t", str(MAX_SECONDS), "-vf",
           f"fps={SAMPLE_FPS},scale='min(960,iw)':-2", "-q:v", "3", str(folder / "s_%04d.jpg"))
    return sorted(folder.glob("s_*.jpg"))


def full_frame(ffmpeg: str, video: Path, t: float, target: Path) -> Image.Image | None:
    try:
        vf.full_frame(ffmpeg, video, t, target)
        return Image.open(target).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def scaled(box, k: float):
    return [v * k for v in box]


def shrink(image: Image.Image) -> Image.Image:
    image = image.copy()
    image.thumbnail((OUT_SIDE, OUT_SIDE))
    return image


def process(item: dict, video: Path, classify, detect, ffmpeg: str, work: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        paths = sample(ffmpeg, video, tmp)
        if not paths:
            return {"status": "ffmpeg не дал кадров"}
        images = [Image.open(p).convert("RGB") for p in paths]
        probs = classify(images)
        frames = []
        for i, (im, pr) in enumerate(zip(images, probs)):
            view = max(vf.VIEWS, key=pr.get)
            f = {"t": i / SAMPLE_FPS, "probs": pr, "view": view, "size": im.size,
                 "sharp": vf.sharpness(im), "bright": vf.brightness(im), "car": None, "people": []}
            if ok_light(f) and (view in EXTERIOR or max(pr[v] for v in EXTERIOR) >= 0.2):
                f["car"], f["people"] = detect(im)
            frames.append(f)
        top = max((f["sharp"] for f in frames), default=1.0) or 1.0

        # обложка: лучший внешний кадр по очкам, ракурс берём самый вероятный из внешних
        for f in frames:
            ext = max(EXTERIOR, key=lambda v: f["probs"][v])
            f["ext_view"] = ext
            f["score"] = score_frame(f, ext, top) if f["car"] is not None and ok_light(f) else -1.0
        best = max(frames, key=lambda f: f["score"])
        if best["score"] < 0.9:
            return {"status": "нет кадра с машиной целиком", "best_score": round(best["score"], 2)}

        out = []
        cover_img = full_frame(ffmpeg, video, best["t"], tmp / "cover_full.jpg")
        if cover_img is None:
            return {"status": "не вырезался кадр"}
        k = cover_img.width / best["size"][0]
        window, _, _ = crop_window(cover_img.size, scaled(best["car"], k))
        shrink(cover_img.crop(window)).save(work / "vf_cover.jpg", quality=88)
        out.append(("vf_cover.jpg", best["ext_view"], best["t"], round(best["score"], 2)))

        # галерея: по одному кадру на ракурс, не ближе MIN_GAP к уже взятым
        taken = [best["t"]]
        for slot in GALLERY:
            if slot == "interior":
                pool = [f for f in frames if f["view"] == "interior" and f["probs"]["interior"] >= vf.MIN_PROB
                        and ok_light(f) and f["sharp"] >= vf.MIN_SHARP_SHARE * top]
                pool.sort(key=lambda f: -(0.5 * f["probs"]["_wide_in"] + 0.3 * f["probs"]["interior"]
                                          + 0.2 * min(f["sharp"] / top, 1)))
            else:
                pool = [f for f in frames if f["ext_view"] == slot and f["score"] >= 0.9
                        and f["probs"][slot] >= 0.3]
                pool.sort(key=lambda f: -f["score"])
            pick = next((f for f in pool if all(abs(f["t"] - t) >= MIN_GAP for t in taken)), None)
            if pick is None:
                continue
            img = full_frame(ffmpeg, video, pick["t"], tmp / f"{slot}_full.jpg")
            if img is None:
                continue
            if slot == "interior":
                window, _, _ = crop_window(img.size, None)
            else:
                window, _, _ = crop_window(img.size, scaled(pick["car"], img.width / pick["size"][0]))
            name = f"vf_{len(out) + 1}.jpg"
            shrink(img.crop(window)).save(work / name, quality=85)
            out.append((name, slot, pick["t"], round(pick.get("score", 0), 2)))
            taken.append(pick["t"])
    return {"status": "ok", "files": out, "fits": bool(best.get("fits")),
            "person": round(person_share(best["people"], best.get("window") or (0, 0, 1, 1)), 3)}


# ---------- учёт и сайт

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_overlay(overlay: dict) -> None:
    OVERLAY_FILE.write_text(json.dumps({"updated": datetime.now().isoformat(timespec="seconds"), "listings": overlay},
                                       ensure_ascii=False, indent=1), encoding="utf-8")


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def video_post(channel: str, post_id: str, cache: dict) -> str:
    if channel not in cache:
        cache[channel] = load_json(TG_DIR / channel / "posts.json", {})
    post = cache[channel].get(str(post_id)) or {}
    return str(post.get("media_from") or post_id)


def check_sheet(rows: list[tuple[str, Path | None, Path]], page: int) -> Path:
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    tw, th = 360, 270
    sheet = Image.new("RGB", (4 * (tw * 2 + 20), ((len(rows) + 3) // 4) * (th + 34)), "white")
    draw = ImageDraw.Draw(sheet)
    for n, (lid, before, after) in enumerate(rows):
        x, y = (n % 4) * (tw * 2 + 20), (n // 4) * (th + 34)
        for k, path in enumerate((before, after)):
            try:
                tile = Image.open(path).convert("RGB")
                tile.thumbnail((tw, th))
                sheet.paste(tile, (x + k * tw, y + 28))
            except Exception:  # noqa: BLE001
                draw.text((x + k * tw + 10, y + 120), "нет фото", fill="gray", font=font)
        draw.text((x + 4, y + 4), f"{lid}   было / стало", fill="black", font=font)
    target = CHECK_DIR / f"_sheet_{page}.jpg"
    sheet.save(target, quality=85)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="конкретные объявления (делаются заново)")
    parser.add_argument("--limit", type=int, default=0, help="сколько объявлений за запуск, 0 все")
    parser.add_argument("--with-sold", action="store_true", help="и проданные или снятые")
    parser.add_argument("--redo", action="store_true", help="переделать уже сделанные")
    args = parser.parse_args()

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("video_covers.py уже идёт")

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        sys.exit("нет ffmpeg")
    listings = load_json(TG_DIR / "listings.json", [])
    paid = set((load_json(CARDS_OVERLAY, {}).get("listings") or {}))
    overlay = load_json(OVERLAY_FILE, {}).get("listings") or {}
    state = load_json(STATE_FILE, {})
    places, cache = Places(), {}

    wanted = set(args.ids)
    items = []
    for item in listings:
        if wanted:
            if item["id"] in wanted:
                items.append(item)
            continue
        if item.get("kind") != "listing" or not item.get("has_video") or len(item.get("images") or []) > 1:
            continue
        if not args.with_sold and (item.get("is_sold") or item.get("removed_at")):
            continue
        if item["id"] in paid:
            continue
        if not args.redo and item["id"] in state:
            continue
        items.append(item)
    items.sort(key=lambda it: it.get("date") or "", reverse=True)

    jobs = []
    for item in items:
        channel = item["source_account"]
        vpost = video_post(channel, item["id"].rsplit("-", 1)[1], cache)
        path = places.raw(channel, vpost)
        if path.exists():
            jobs.append((item, channel, vpost, path))
        if args.limit and len(jobs) >= args.limit:
            break
    print(f"Объявлений только с видео без обложки: {len(items)}, со скачанным роликом в этом запуске: {len(jobs)}", flush=True)
    if not jobs:
        return

    print("Загружаю CLIP и детектор (процессор)...", flush=True)
    classify = vf.load_clip("ViT-B-32", "laion2b_s34b_b79k")
    detect = load_detector()

    done, sheet_rows, page, started = 0, [], 1, time.time()
    for n, (item, channel, vpost, video) in enumerate(jobs, start=1):
        lid = item["id"]
        work = SITE_IMAGES / lid
        work.mkdir(parents=True, exist_ok=True)
        try:
            result = process(item, video, classify, detect, ffmpeg, work)
        except Exception as error:  # noqa: BLE001
            result = {"status": f"ошибка {type(error).__name__}: {str(error)[:120]}"}
        state[lid] = {"at": datetime.now().isoformat(timespec="seconds"), **{k: v for k, v in result.items() if k != "files"}}
        if result["status"] == "ok":
            files = result["files"]
            state[lid]["frames"] = [{"file": f, "view": v, "t": t, "score": s} for f, v, t, s in files]
            overlay[lid] = {"cover": f"/cards/{lid}/{files[0][0]}",
                            "photos": [f"/cards/{lid}/{f[0]}" for f in files],
                            "source": "video_frame"}
            try:  # копия обложки в папку поста на Диске; Диск иногда отказывает, это не страшно
                frames_dir = places.cut(channel, vpost)
                frames_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(work / files[0][0], frames_dir / "cover_frame.jpg")
            except OSError:
                pass
            done += 1
            before = PARSER_DIR / item["images"][0] if item.get("images") else None
            sheet_rows.append((lid, before, work / files[0][0]))
            if len(sheet_rows) == 24:
                check_sheet(sheet_rows, page)
                sheet_rows, page = [], page + 1
        else:
            shutil.rmtree(work, ignore_errors=True) if not any(work.iterdir()) else None
        speed = (time.time() - started) / n
        print(f"  [{n}/{len(jobs)}] {lid}: {result['status']}"
              + (f", кадров {len(result['files'])}" if result["status"] == "ok" else "")
              + f"  (~{speed:.0f} с на ролик)", flush=True)
        if n % SAVE_EVERY == 0:
            save_overlay(overlay)
            save_state(state)
    save_overlay(overlay)
    save_state(state)
    if sheet_rows:
        check_sheet(sheet_rows, page)
    print(f"Готово: новых обложек {done} из {len(jobs)}. На сайте с обложкой из видео: {len(overlay)}. "
          f"Листы для проверки: {CHECK_DIR}", flush=True)


if __name__ == "__main__":
    main()
