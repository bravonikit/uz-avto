"""Лучшие кадры машины из видео обзора: перед 3/4, бок, зад 3/4, салон.

Берёт ролик из сырого слоя (его качает tg_video.py), режет на кадры 3 раза в секунду, для каждого кадра:
  * ракурс: модель CLIP сравнивает кадр с описаниями ракурсов (без обучения, «zero-shot»);
  * чёткость: насколько резкий кадр (дисперсия лапласиана), смазанные при повороте камеры отсеиваются;
  * яркость: слишком тёмные и пересвеченные отсеиваются.
Для каждого слота берётся самый резкий кадр среди уверенно узнанных и сохраняется в полном размере.

Результат рядом с раскадровкой: <ARCHIVE_DIR>/videos/<канал>/tg-<канал>-<id>/picks/
  front_3q.jpg, side.jpg, rear_3q.jpg, interior.jpg   лучшие кадры (каких нет, тех нет)
  picks.json                                            что выбрано, время в ролике, уверенность
  sheet.jpg                                             все кадры с подписями, чтобы проверить глазами

  python video_frames.py azaavtoo 5123        один пост
  python video_frames.py azaavtoo --limit 5   первые 5 скачанных роликов канала
  python video_frames.py --all --limit 50     по всем каналам

Нужны torch и open_clip_torch (pip install -r requirements.txt). Первый запуск скачивает модель (~600 МБ).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from tg_video import Places, find_ffmpeg, run, TG_DIR

FPS = 3
MAX_SECONDS = 180
SLOTS = ["front_3q", "side", "rear_3q", "interior"]

# Описания ракурсов для CLIP. Несколько фраз на ракурс, их ответы усредняются.
VIEWS = {
    "front_3q": ["a photo of a car from the front three-quarter angle",
                 "a car photographed diagonally from the front corner, showing the front and one side"],
    "front": ["a photo of the front of a car, head-on view of the grille and headlights"],
    "side": ["a side profile photo of a car, the whole car seen exactly from the side",
             "a car seen from the side, all wheels on one side visible"],
    "rear_3q": ["a photo of a car from the rear three-quarter angle",
                "a car photographed diagonally from the back corner, showing the rear and one side"],
    "rear": ["a photo of the back of a car, rear lights and trunk lid, straight behind"],
    "interior": ["a photo of a car interior with the dashboard, steering wheel and front seats",
                 "inside a car, the driver's seat and the center console"],
    "rear_seats": ["the rear seats inside a car"],
    "detail": ["a close-up of a car wheel or headlight", "a close-up detail of a car"],
    "engine": ["the engine bay of a car under the open hood"],
    "trunk": ["an open car trunk"],
    "person": ["a person talking to the camera", "a selfie of a man"],
    "junk": ["a blurry photo", "text and numbers on a screen", "a photo of a street without cars"],
}
MIN_PROB = 0.35        # ниже этого ракурс считаем неуверенным
MIN_SHARP_SHARE = 0.4  # кадр должен быть не мутнее 40% самого резкого кадра ролика


def load_clip(name: str, pretrained: str):
    import open_clip
    import torch
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(name, pretrained=pretrained, device=device)
    tokenizer = open_clip.get_tokenizer(name)
    labels, texts = [], []
    for view, phrases in VIEWS.items():
        for phrase in phrases:
            labels.append(view)
            texts.append(phrase)
    with torch.no_grad():
        emb = model.encode_text(tokenizer(texts).to(device))
        emb = emb / emb.norm(dim=-1, keepdim=True)
    # одна строка на ракурс: среднее по его фразам
    views = list(VIEWS)
    text = torch.stack([emb[[i for i, l in enumerate(labels) if l == v]].mean(0) for v in views])
    text = text / text.norm(dim=-1, keepdim=True)

    def classify(images: list[Image.Image]) -> list[dict]:
        out = []
        with torch.no_grad():
            for start in range(0, len(images), 32):
                batch = torch.stack([preprocess(im) for im in images[start:start + 32]]).to(device)
                feats = model.encode_image(batch)
                feats = feats / feats.norm(dim=-1, keepdim=True)
                probs = (100.0 * feats @ text.T).softmax(dim=-1).cpu().numpy()
                out += [dict(zip(views, map(float, row))) for row in probs]
        return out
    return classify


def sharpness(im: Image.Image) -> float:
    g = np.asarray(im.convert("L").resize((512, int(512 * im.height / im.width))), dtype=np.float32)
    lap = g[1:-1, 2:] + g[1:-1, :-2] + g[2:, 1:-1] + g[:-2, 1:-1] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def brightness(im: Image.Image) -> float:
    return float(np.asarray(im.convert("L").resize((64, 64))).mean())


def extract(ffmpeg: str, video: Path, folder: Path) -> list[Path]:
    run(ffmpeg, "-i", str(video), "-t", str(MAX_SECONDS), "-vf", f"fps={FPS},scale='min(960,iw)':-2",
        "-q:v", "3", str(folder / "f_%04d.jpg"))
    return sorted(folder.glob("f_*.jpg"))


def full_frame(ffmpeg: str, video: Path, seconds: float, target: Path) -> None:
    run(ffmpeg, "-ss", f"{seconds:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(target))


def choose(frames: list[dict]) -> dict:
    """Для каждого слота: самый резкий кадр среди тех, где этот ракурс уверенно узнан."""
    top = max((f["sharp"] for f in frames), default=0) or 1
    picks = {}
    for slot in SLOTS:
        good = [f for f in frames
                if f["view"] == slot and f["probs"][slot] >= MIN_PROB
                and f["sharp"] >= MIN_SHARP_SHARE * top and 35 <= f["bright"] <= 225]
        if good:
            # резкость важнее, уверенность как добавка
            best = max(good, key=lambda f: (f["sharp"] / top) * 0.6 + f["probs"][slot] * 0.4)
            picks[slot] = best
    return picks


def contact_sheet(frames: list[dict], picks: dict, target: Path) -> None:
    chosen = {f["i"]: slot for slot, f in picks.items()}
    step = max(1, len(frames) // 60)  # не больше ~60 миниатюр
    shown = [f for f in frames if f["i"] % step == 0 or f["i"] in chosen]
    tw, th, cols = 240, 135, 6
    rows = (len(shown) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 30)), "white")
    draw = ImageDraw.Draw(sheet)
    for n, f in enumerate(shown):
        im = Image.open(f["path"]).convert("RGB")
        im.thumbnail((tw, th))
        x, y = (n % cols) * tw, (n // cols) * (th + 30)
        sheet.paste(im, (x, y))
        slot = chosen.get(f["i"])
        if slot:
            draw.rectangle([x, y, x + im.width - 1, y + im.height - 1], outline="red", width=4)
        label = f"{f['t']:.1f}s {f['view']} {f['probs'][f['view']]:.2f} s{f['sharp']:.0f}"
        draw.text((x + 3, y + th + 3), ("★" + slot + " " if slot else "") + label, fill="red" if slot else "black")
    sheet.save(target, quality=85)


def process(classify, ffmpeg: str, places: Places, channel: str, post_id: str) -> str:
    video = places.raw(channel, post_id)
    if not video.exists():
        return "нет ролика (сначала tg_video.py --only download)"
    out = places.cut(channel, post_id) / "picks"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        paths = extract(ffmpeg, video, Path(tmp))
        if not paths:
            return "ffmpeg не дал кадров"
        images = [Image.open(p).convert("RGB") for p in paths]
        probs = classify(images)
        frames = []
        for i, (p, im, pr) in enumerate(zip(paths, images, probs)):
            view = max(pr, key=pr.get)
            frames.append({"i": i, "t": i / FPS, "path": p, "view": view, "probs": pr,
                           "sharp": sharpness(im), "bright": brightness(im)})
        picks = choose(frames)
        for slot, f in picks.items():
            full_frame(ffmpeg, video, f["t"], out / f"{slot}.jpg")
        contact_sheet(frames, picks, out / "sheet.jpg")
    summary = {slot: {"t": round(f["t"], 2), "prob": round(f["probs"][slot], 3), "sharp": round(f["sharp"], 1)}
               for slot, f in picks.items()}
    views = {}
    for f in frames:
        views[f["view"]] = views.get(f["view"], 0) + 1
    (out / "picks.json").write_text(json.dumps({"video": video.name, "frames": len(frames), "views": views,
                                                "picks": summary}, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = [s for s in SLOTS if s not in picks]
    return f"кадров {len(frames)}, выбрано {', '.join(picks) or 'ничего'}" + (f"; нет {', '.join(missing)}" if missing else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("channel", nargs="?")
    parser.add_argument("post", nargs="?")
    parser.add_argument("--all", action="store_true", help="все каналы")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--model", default="ViT-B-32")
    parser.add_argument("--pretrained", default="laion2b_s34b_b79k")
    args = parser.parse_args()
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("нет ffmpeg: pip install -r requirements.txt")
        return
    places = Places()
    jobs = []
    if args.channel and args.post:
        jobs = [(args.channel, args.post)]
    else:
        channels = [args.channel] if args.channel else sorted(p.name for p in TG_DIR.iterdir() if (p / "posts.json").exists())
        for channel in channels:
            folder = places.raw(channel, 0).parent
            if folder.exists():
                jobs += [(channel, p.stem) for p in sorted(folder.glob("*.mp4"), reverse=True)]
        jobs = jobs[: args.limit]
    if not jobs:
        print("Роликов не нашлось. Сначала: python tg_video.py <канал> --only download")
        return
    print(f"Модель {args.model} ({args.pretrained}), роликов: {len(jobs)}")
    classify = load_clip(args.model, args.pretrained)
    for channel, post in jobs:
        try:
            status = process(classify, ffmpeg, places, channel, post)
        except Exception as error:  # noqa: BLE001
            status = f"ошибка {type(error).__name__}: {str(error)[:150]}"
        print(f"  {channel} {post}: {status}")
    print(f"Готово. Листы кадров: {places.cut_root or TG_DIR}/<канал>/tg-<канал>-<id>/picks/sheet.jpg")


if __name__ == "__main__":
    main()
