"""Проба: выбрать обложку из всех фото альбома и обрезать её в 4:3 по машине, без нейросети-генератора.

Шаг 1. Обложка: из всех фото поста берём то, где машина целиком и под углом спереди
        (ракурс узнаёт CLIP, машину на фото находит детектор из torchvision). Таблицы, баннеры, салон отпадают.
Шаг 2. Обрезка: рамка 4:3 ставится по найденной машине с отступом, а не по центру кадра.
Если машина в рамку 4:3 всё равно не помещается, в итоге пишется «нужна дорисовка» (это шаг 3, платный).

Ничего не меняет в проекте и на сайте. Результат: ~/Movies/uz-avto-lab/cover-test/
  <id>/src_N.jpg  все фото альбома,  before.jpg  как сейчас на сайте,  after.jpg  новая обложка
  _sheet_N.jpg    листы «было / стало»,  _summary.json  решения по каждому объявлению

  .venv/bin/python _cover_test.py                      8 карточек с главной и 16 случайных
  .venv/bin/python _cover_test.py tg-aslauto-3923 ...  конкретные объявления
"""
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from accounts import PARSER_DIR
from tg_parse import TG_DIR
import video_frames as vf

OUT = Path.home() / "Movies" / "uz-avto-lab" / "cover-test"
HOME_IDS = ["tg-aslauto-3923", "tg-aslauto-3920", "tg-autosaleabdulloh-3764", "tg-ciptashkentuz-5867",
            "tg-ciptashkentuz-5859", "tg-ciptashkentuz-5857", "tg-aslauto-3917", "tg-aslauto-3912"]
EXTRA_IDS = ["tg-aslauto-3765", "tg-VTsale-14137", "tg-ciptashkentuz-5180", "tg-autopriceuz_moshinabozor-157983",
             "tg-hamidovauto-4746", "tg-avtuarcha-6250", "tg-aslauto-3410", "tg-autopriceuz_moshinabozor-158765",
             "tg-autopriceuz_moshinabozor-154446", "tg-avtuarcha-6114", "tg-arzon_mash1na-9846",
             "tg-autopriceuz_moshinabozor-159793", "tg-hamidovauto-5376", "tg-arzon_mash1na-9784",
             "tg-aslauto-3459", "tg-A7_Motors_Avto-8367"]
RATIO = 4 / 3
MARGIN = 0.06          # отступ вокруг машины, доля от её размера
MAX_PHOTOS = 10
VEHICLES = {"car", "truck", "bus"}
VIEW_WEIGHT = {"front_3q": 1.0, "front": 0.8, "rear_3q": 0.55, "side": 0.6, "rear": 0.4}
HEADERS = {"User-Agent": "Mozilla/5.0"}


def load_detector():
    # Python с python.org не видит системные сертификаты, из-за этого скачивание весов детектора падало
    # с CERTIFICATE_VERIFY_FAILED. Берём сертификаты из пакета certifi (он ставится вместе с requests).
    import os
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    import torch
    from torchvision.models.detection import (FasterRCNN_MobileNet_V3_Large_FPN_Weights,
                                              fasterrcnn_mobilenet_v3_large_fpn)
    weights = FasterRCNN_MobileNet_V3_Large_FPN_Weights.DEFAULT
    model = fasterrcnn_mobilenet_v3_large_fpn(weights=weights).eval()
    names, to_tensor = weights.meta["categories"], weights.transforms()

    def detect(image: Image.Image):
        """Самая большая машина на фото: (x0, y0, x1, y1) в пикселях или None."""
        with torch.no_grad():
            found = model([to_tensor(image)])[0]
        best, best_area = None, 0.0
        for box, label, score in zip(found["boxes"].tolist(), found["labels"].tolist(), found["scores"].tolist()):
            if score < 0.5 or names[label] not in VEHICLES:
                continue
            area = (box[2] - box[0]) * (box[3] - box[1])
            if area > best_area:
                best, best_area = box, area
        return best
    return detect


def crop_window(size: tuple[int, int], box) -> tuple[tuple[int, int, int, int], bool, float]:
    """Рамка 4:3 внутри фото, поставленная по машине. Возвращает (рамка, машина влезла целиком, какая доля машины влезла)."""
    w, h = size
    if w / h >= RATIO:
        ch, cw = h, h * RATIO
    else:
        cw, ch = w, w / RATIO
    if box is None:
        cx, cy = w / 2, h / 2
    else:
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    x0 = min(max(cx - cw / 2, 0), w - cw)
    y0 = min(max(cy - ch / 2, 0), h - ch)
    window = (int(x0), int(y0), int(x0 + cw), int(y0 + ch))
    if box is None:
        return window, False, 0.0
    bw, bh = box[2] - box[0], box[3] - box[1]
    need = (box[0] - bw * MARGIN, box[1] - bh * MARGIN, box[2] + bw * MARGIN, box[3] + bh * MARGIN)
    fits = need[0] >= x0 and need[1] >= y0 and need[2] <= x0 + cw and need[3] <= y0 + ch
    ix = max(0.0, min(box[2], x0 + cw) - max(box[0], x0))
    iy = max(0.0, min(box[3], y0 + ch) - max(box[1], y0))
    return window, fits, (ix * iy) / max(bw * bh, 1.0)


def touches_edge(size: tuple[int, int], box) -> bool:
    """Машина упирается в край самого фото: значит, её обрезал ещё продавец."""
    w, h = size
    pad = 0.012
    return box[0] <= w * pad or box[1] <= h * pad or box[2] >= w * (1 - pad) or box[3] >= h * (1 - pad)


def center_crop(image: Image.Image) -> Image.Image:
    window, _, _ = crop_window(image.size, None)
    return image.crop(window)


def album(listing: dict, folder: Path) -> list[Path]:
    """Все фото поста: сохранённые парсером плюс остальные по ссылкам из posts.json."""
    channel, post_id = listing["source_account"], listing["id"].rsplit("-", 1)[1]
    posts = json.loads((TG_DIR / channel / "posts.json").read_text(encoding="utf-8"))
    post = posts.get(post_id) or {}
    if not post.get("photos") and post.get("media_from"):
        post = posts.get(str(post["media_from"])) or post
    saved = [PARSER_DIR / path for path in (listing.get("images") or [])]
    files = []
    for number, url in enumerate((post.get("photos") or [])[:MAX_PHOTOS], start=1):
        target = folder / f"src_{number}.jpg"
        if not target.exists():
            local = saved[number - 1] if number <= len(saved) else None
            try:
                if local is not None and local.exists():
                    target.write_bytes(local.read_bytes())
                else:
                    response = requests.get(url, headers=HEADERS, timeout=30)
                    response.raise_for_status()
                    target.write_bytes(response.content)
            except Exception:  # noqa: BLE001
                continue
        files.append(target)
    if not files:  # ссылок нет: берём то, что сохранил парсер
        for number, local in enumerate(saved, start=1):
            if local.exists():
                target = folder / f"src_{number}.jpg"
                target.write_bytes(local.read_bytes())
                files.append(target)
    return files


def pick_cover(listing: dict, folder: Path, classify, detect) -> dict | None:
    """Шаги 1 и 2 для одного объявления: выбор обложки из альбома и рамка 4:3 по машине.
    Пишет в folder файлы src_N.jpg, before.jpg, after.jpg и возвращает решение (или None, если фото нет)."""
    folder.mkdir(parents=True, exist_ok=True)
    files = album(listing, folder)
    if not files:
        return None
    images = [Image.open(path).convert("RGB") for path in files]
    views = classify(images)
    candidates = []
    for number, (image, probs) in enumerate(zip(images, views), start=1):
        view = max(vf.VIEWS, key=probs.get)
        box = detect(image)
        window, fits, inside = crop_window(image.size, box)
        cut_by_seller = box is not None and touches_edge(image.size, box)
        score = 0.0
        if box is not None and view in VIEW_WEIGHT:
            share = ((box[2] - box[0]) * (box[3] - box[1])) / (image.width * image.height)
            score = (VIEW_WEIGHT[view] * (0.5 + 0.5 * probs[view]) + (0.6 if fits else 0.3 * inside)
                     + (0.0 if cut_by_seller else 0.3) + (0.2 if 0.15 <= share <= 0.75 else 0.0))
        candidates.append({"n": number, "view": view, "prob": round(probs[view], 2), "car": box is not None,
                           "fits_4x3": fits, "inside": round(inside, 2), "cut_by_seller": cut_by_seller,
                           "score": round(score, 3), "window": window, "size": list(image.size)})
    best = max(candidates, key=lambda c: c["score"])
    if best["score"] <= 0:
        best = candidates[0]  # машину нигде не нашли: оставляем первую, как сейчас
    center_crop(images[0]).save(folder / "before.jpg", quality=90)
    images[best["n"] - 1].crop(tuple(best["window"])).save(folder / "after.jpg", quality=90)
    if not best["car"]:
        verdict = "машина не найдена"
    elif best["fits_4x3"] and not best["cut_by_seller"]:
        verdict = "готово"
    else:
        verdict = "нужна дорисовка"
    return {"id": listing["id"], "title": listing.get("title"), "photos": len(files), "chosen": best["n"],
            "view": best["view"], "changed_photo": best["n"] != 1, "verdict": verdict, "candidates": candidates}


def main() -> None:
    listings = {item["id"]: item for item in json.loads((TG_DIR / "listings.json").read_text(encoding="utf-8"))}
    ids = sys.argv[1:] or HOME_IDS + EXTRA_IDS
    OUT.mkdir(parents=True, exist_ok=True)
    print("Загружаю модели (первый раз детектор скачивает около 75 МБ)...", flush=True)
    classify = vf.load_clip("ViT-B-32", "laion2b_s34b_b79k")
    detect = load_detector()
    summary = []
    for listing_id in ids:
        listing = listings.get(listing_id)
        if not listing:
            print(f"  {listing_id}: нет в listings.json")
            continue
        row = pick_cover(listing, OUT / listing_id, classify, detect)
        if not row:
            print(f"  {listing_id}: нет фото")
            continue
        summary.append(row)
        print(f"  {listing_id}: фото {row['photos']}, обложка №{row['chosen']} ({row['view']}), {row['verdict']}", flush=True)

    (OUT / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    tw, th = 440, 330
    for page, start in enumerate(range(0, len(summary), 8), start=1):
        rows = summary[start:start + 8]
        sheet = Image.new("RGB", (4 * (tw + 10), 2 * (2 * th + 80)), "white")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(rows):
            x, y = (index % 4) * (tw + 10), (index // 4) * (2 * th + 80)
            for k, name in enumerate(("before.jpg", "after.jpg")):
                tile = Image.open(OUT / row["id"] / name).convert("RGB").resize((tw, th))
                sheet.paste(tile, (x, y + 34 + k * (th + 6)))
            draw.text((x + 4, y + 4), f"{start + index + 1}. {(row['title'] or '')[:30]}", fill="black", font=font)
            note = f"фото №{row['chosen']} из {row['photos']}: {row['verdict']}"
            draw.text((x + 4, y + 34 + 2 * th + 10), note, fill=(0, 120, 0) if row["verdict"] == "готово" else (190, 0, 0), font=font)
        sheet.save(OUT / f"_sheet_{page}.jpg", quality=88)
    done = sum(1 for row in summary if row["verdict"] == "готово")
    print(f"Готово: {done} из {len(summary)} обложек получились без дорисовки. Листы: {OUT}/_sheet_N.jpg")


if __name__ == "__main__":
    main()
