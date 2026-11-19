"""Проба: 4 ракурса одной картинкой (сетка 2 на 2), потом режем на 4 фото. В 3 раза дешевле, чем 4 запроса.

Исходники: кадры раскадровки в ~/Movies/uz-avto-lab/frames-test/<ролик>/picks_gemini и picks.
Результат: <ролик>/generated_grid/grid.jpg (как вернула модель) и main.jpg, front.jpg, side.jpg, interior.jpg.
Если кадров салона нет, четвёртая клетка это зад 3/4 (rear_3q.jpg). В проект и архив ничего не пишет.

  .venv/bin/python _frames_test_grid.py            все ролики из frames-test
  .venv/bin/python _frames_test_grid.py 3          первые 3
  .venv/bin/python _frames_test_grid.py avto_sroj-1050     конкретные ролики

Модель: GEMINI_IMAGE_MODEL в .env, по умолчанию gemini-nano-banana-2.1. Размер сетки: GEMINI_GRID_SIZE, по умолчанию 2K.
"""
import io
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

from accounts import PARSER_DIR

OUT = Path.home() / "Movies" / "uz-avto-lab" / "frames-test"
DEFAULT_MODEL = "gemini-nano-banana-2.1"
GRID_SIZE = os.environ.get("GEMINI_GRID_SIZE", "2K")
EXTERIOR = ["front_3q_1", "front_3q_2", "front", "rear_3q_1", "rear_3q_2", "rear"]
INTERIOR = ["interior_1", "interior_2", "interior_3"]
MAX_EXTERIOR, MAX_INTERIOR = 5, 3
TRIM = 0.012  # срезаем по 1.2% с каждого края клетки: там бывает шов между кадрами

PROMPT = """You are given reference frames from a seller's video of ONE used car for sale{car}.
Some frames may be circular (round video messages) with white corners: ignore the circular mask and the white area.

Create ONE image: a contact sheet of exactly four photos of this car arranged in a 2x2 grid.
The image is split exactly in half horizontally and exactly in half vertically into four equal rectangles.
Each rectangle is a complete, separate photo with the same 4:3 landscape shape.
No borders, no gaps, no frames, no captions, no numbers and no text anywhere: the four photos touch each other directly.

Top-left: FRONT THREE-QUARTER view. The camera stands at the front corner of the car at headlight height,
the whole front and one whole side are visible.
Top-right: STRAIGHT FRONT view. The camera is exactly on the car's centre line at headlight height,
the front is symmetrical, both headlights, the whole grille and bumper are visible.
Bottom-left: EXACT SIDE PROFILE. The camera is perpendicular to the car at door-handle height,
the whole car from front bumper to rear bumper, both wheels of this side fully visible, the car is level.
Bottom-right: {fourth}

Rules for every photo:
- Exactly the same car as in the references: same make, model, generation, body colour, wheels and rims, grille,
  headlights, tail lights, window tint, roof rails, stickers or damage if visible. Do not restyle, upgrade or clean it.
  The car must be identical in all four photos.
- In each exterior photo the whole car is inside its rectangle with free space around it,
  the car takes about 70% of the rectangle width. Nothing is cut off by the rectangle edge.
- Keep the same place, ground, buildings, weather and time of day as in the references, so it looks like
  real photos taken by the seller at that location. Do not move the car to a studio or another place.
- Licence plates: keep them exactly as they are in the references. Do not blur, blank, hide, change or invent
  plate characters. If the plate is covered by a seller's logo or sticker in the references, keep that same
  logo or sticker on the plate. If a plate is not readable in the references, leave it unreadable.
- All doors, the bonnet and the boot are closed in the exterior photos, even if they are open in the references.
- No people, no hands, no added logos or watermarks.
- Natural phone-camera look, sharp, correct proportions, no distortion."""

FOURTH_INTERIOR = """INTERIOR. A wide photo of the cabin taken from the rear seat centre looking forward:
the whole dashboard, steering wheel, centre console, screen and both front seats. Exactly the same interior as in
the references (seat colour and material, steering wheel, screens, trim, gear selector). Same time of day as in
the references. Do not add or remove equipment."""
FOURTH_REAR = """REAR THREE-QUARTER view. The camera stands at the rear corner of the car at tail-light height,
the whole rear and one whole side are visible."""


def refs(folder: Path, names: list[str], limit: int) -> list[Path]:
    """Сначала кадры, выбранные Gemini (чище), потом локальные (CLIP)."""
    found = []
    for sub in ("picks_gemini", "picks"):
        for name in names:
            path = folder / sub / f"{name}.jpg"
            if path.exists() and len(found) < limit:
                found.append(path)
    return found


def load(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    im.thumbnail((1024, 1024))
    return im


def split(grid: Image.Image, names: list[str], out: Path) -> None:
    """Режем ровно пополам по ширине и высоте, с каждой клетки снимаем узкую кромку."""
    w, h = grid.size
    cw, ch = w // 2, h // 2
    dx, dy = int(cw * TRIM), int(ch * TRIM)
    for index, name in enumerate(names):
        x, y = (index % 2) * cw, (index // 2) * ch
        grid.crop((x + dx, y + dy, x + cw - dx, y + ch - dy)).save(out / f"{name}.jpg", quality=92)


def main() -> None:
    load_dotenv(PARSER_DIR / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Нет GEMINI_API_KEY в .env")
        return
    from google import genai
    from google.genai import types

    folders = sorted(p for p in OUT.iterdir() if (p / "picks").is_dir())
    args = sys.argv[1:]
    if args and not args[0].isdigit():
        folders = [p for p in folders if p.name in args]
    elif args:
        folders = folders[: int(args[0])]
    model = os.environ.get("GEMINI_IMAGE_MODEL", "").strip() or DEFAULT_MODEL
    client = genai.Client(api_key=key)
    print(f"Модель {model}, сетка {GRID_SIZE}, роликов: {len(folders)} (одна картинка на ролик)")
    made, total_tokens = 0, 0
    for folder in folders:
        answer = folder / "picks_gemini" / "answer.json"
        car = ""
        if answer.exists():
            car = json.loads(answer.read_text(encoding="utf-8")).get("car") or ""
        exterior = refs(folder, EXTERIOR, MAX_EXTERIOR)
        interior = refs(folder, INTERIOR, MAX_INTERIOR)
        out = folder / "generated_grid"
        out.mkdir(exist_ok=True)
        for old in out.glob("*.jpg"):
            old.unlink()
        names = ["main", "front", "side", "interior" if interior else "rear_3q"]
        log = {"model": model, "size": GRID_SIZE, "car": car, "tiles": names,
               "sources": [f"{p.parent.name}/{p.name}" for p in exterior + interior]}
        if len(exterior) < 2:
            log["status"] = "пропуск: мало внешних кадров"
            print(f"{folder.name}: пропуск, мало внешних кадров")
        else:
            prompt = (PROMPT.replace("{car}", f" ({car})" if car else "")
                      .replace("{fourth}", FOURTH_INTERIOR if interior else FOURTH_REAR))
            started = time.time()
            try:
                data, response = None, None
                for attempt in range(3):  # модель иногда отвечает без картинки: пробуем ещё раз
                    response = client.models.generate_content(
                        model=model,
                        contents=[prompt] + [load(p) for p in exterior + interior],
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            image_config=types.ImageConfig(aspect_ratio="4:3", image_size=GRID_SIZE)))
                    candidate = response.candidates[0] if response.candidates else None
                    parts = (candidate.content.parts if candidate and candidate.content else None) or []
                    for part in parts:
                        if getattr(part, "inline_data", None) and part.inline_data.data:
                            data = part.inline_data.data
                    if data:
                        break
                    print(f"{folder.name}: ответ без картинки, попытка {attempt + 1} из 3", flush=True)
                if not data:
                    reason = getattr(response.candidates[0], "finish_reason", None) if response.candidates else "нет ответа"
                    raise RuntimeError(f"модель не вернула картинку ({reason})")
                grid = Image.open(io.BytesIO(data)).convert("RGB")
                grid.save(out / "grid.jpg", quality=92)
                split(grid, names, out)
                usage = getattr(response, "usage_metadata", None)
                tokens = getattr(usage, "total_token_count", None) or 0
                total_tokens += tokens
                made += 1
                log.update({"status": "ok", "seconds": round(time.time() - started, 1), "tokens": tokens,
                            "grid_size": list(grid.size)})
                print(f"{folder.name} ({car}): готово, сетка {grid.size[0]}x{grid.size[1]}, "
                      f"{log['seconds']} с, токенов {tokens}", flush=True)
            except Exception as error:  # noqa: BLE001
                log["status"] = f"ошибка {type(error).__name__}: {str(error)[:300]}"
                print(f"{folder.name}: {log['status']}", flush=True)
        (out / "generated.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Готово. Сеток: {made}, всего токенов: {total_tokens}. Папки: {OUT}/<ролик>/generated_grid/")


if __name__ == "__main__":
    main()
