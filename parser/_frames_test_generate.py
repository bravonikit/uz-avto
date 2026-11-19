"""Проба: из кадров раскадровки (frames-test) сгенерировать через Gemini API 4 фото на машину.

  main      перед 3/4 (главное фото)
  front     ровно спереди
  side      ровно сбоку
  interior  салон общим планом

Исходники: <ролик>/picks_gemini и <ролик>/picks. Результат: <ролик>/generated/*.jpg и generated.json.
В проект и в архив ничего не пишет. Каждая картинка платная (см. цену модели), поэтому по умолчанию
берутся только первые 3 ролика.

  .venv/bin/python _frames_test_generate.py            первые 3 ролика
  .venv/bin/python _frames_test_generate.py 10         все 10
  .venv/bin/python _frames_test_generate.py avtosotvordiuz-1947 autovitauz-2523    конкретные ролики

Модель: GEMINI_IMAGE_MODEL в .env, по умолчанию gemini-nano-banana-2.1 (около 3 центов за фото 1K).
Самая сильная и дорогая: GEMINI_IMAGE_MODEL=gemini-3-pro-image (13 центов за фото).
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
IMAGE_SIZE = os.environ.get("GEMINI_IMAGE_SIZE", "1K")  # 1K около 1024 px: самое дешёвое
EXTERIOR = ["front_3q_1", "front_3q_2", "front", "rear_3q_1", "rear_3q_2", "rear", "side_1", "side_2"]
INTERIOR = ["interior_1", "interior_2", "interior_3"]
MAX_REFS = 6

COMMON = """You are given reference frames from a seller's video of ONE used car for sale{car}.
Some frames may be circular (round video messages) with white corners: ignore the circular mask and the white area.
Create ONE photorealistic photo for a car marketplace listing, like on auto.ru or drom.ru.
Strict rules:
- It must be exactly the same car as in the references: same make, model, generation, body colour, wheels and rims,
  grille, headlights, tail lights, tint, roof rails, damage or stickers if visible. Do not restyle, upgrade or clean it.
- Keep the same place and lighting as in the references (same ground, buildings, time of day) so it looks like
  a real photo taken by the seller at that location. Do not move the car to a studio or another place.
- No people, no hands, no text, no captions, no logos or watermarks added. Licence plate blurred or blank.
- Natural phone-camera look, sharp, correct proportions, no distortion. Landscape 4:3, the car fills about 80% of the frame width.
"""
SLOTS = {
    "main": COMMON + """View: front three-quarter. The camera stands at the front corner of the car at about headlight height,
so the whole front and one whole side are visible. The whole car is in frame with some space around it.""",
    "front": COMMON + """View: straight from the front, the camera exactly on the car's centre line at headlight height.
The front is symmetrical: both headlights and the whole grille and bumper are visible. The whole car is in frame.""",
    "side": COMMON + """View: exact side profile, the camera perpendicular to the car at door-handle height.
The whole car from front bumper to rear bumper is in frame, both wheels of this side fully visible, the car is level.""",
    "interior": """You are given reference frames of the interior of ONE used car for sale{car}.
Some frames may be circular (round video messages) with white corners: ignore the circular mask and the white area.
Create ONE photorealistic wide photo of the cabin for a car marketplace listing, taken from the rear seat centre
looking forward: the whole dashboard, steering wheel, centre console, screen and both front seats are visible.
Strict rules: exactly the same interior as in the references (same seat colour and material, steering wheel, screens,
trim, gear selector, mats). Do not add or remove equipment. No people, no hands, no text, no watermarks.
Natural daylight as in the references. Landscape 4:3, sharp, no distortion.""",
}


def refs(folder: Path, names: list[str]) -> list[Path]:
    """Сначала кадры, выбранные Gemini (чище), потом локальные (CLIP); бок от CLIP не берём, там мусор."""
    found = []
    for sub in ("picks_gemini", "picks"):
        for name in names:
            if sub == "picks" and name.startswith("side"):
                continue
            path = folder / sub / f"{name}.jpg"
            if path.exists() and len(found) < MAX_REFS:
                found.append(path)
    return found


def load(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    im.thumbnail((1280, 1280))
    return im


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
    else:
        folders = folders[: int(args[0]) if args else 3]
    model = os.environ.get("GEMINI_IMAGE_MODEL", "").strip() or DEFAULT_MODEL
    client = genai.Client(api_key=key)
    print(f"Модель {model}, размер {IMAGE_SIZE}, роликов: {len(folders)}, до {len(folders) * 4} картинок")
    made = 0
    for folder in folders:
        answer = folder / "picks_gemini" / "answer.json"
        car = ""
        if answer.exists():
            car = json.loads(answer.read_text(encoding="utf-8")).get("car") or ""
        exterior, interior = refs(folder, EXTERIOR), refs(folder, INTERIOR)
        out = folder / "generated"
        out.mkdir(exist_ok=True)
        log = {"model": model, "car": car, "slots": {}}
        print(f"{folder.name} ({car}): внешних кадров {len(exterior)}, салона {len(interior)}", flush=True)
        for slot, prompt in SLOTS.items():
            sources = interior if slot == "interior" else exterior
            need = 1 if slot == "interior" else 2
            if len(sources) < need:
                log["slots"][slot] = {"status": "пропуск: мало исходных кадров"}
                print(f"  {slot}: пропуск, мало исходных кадров")
                continue
            started = time.time()
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt.replace("{car}", f" ({car})" if car else "")] + [load(p) for p in sources],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(aspect_ratio="4:3", image_size=IMAGE_SIZE)))
                data = None
                for part in (response.candidates[0].content.parts if response.candidates else []):
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        data = part.inline_data.data
                if not data:
                    reason = getattr(response.candidates[0], "finish_reason", None) if response.candidates else "нет ответа"
                    raise RuntimeError(f"модель не вернула картинку ({reason})")
                Image.open(io.BytesIO(data)).convert("RGB").save(out / f"{slot}.jpg", quality=92)
                usage = getattr(response, "usage_metadata", None)
                log["slots"][slot] = {"status": "ok", "seconds": round(time.time() - started, 1),
                                      "tokens": getattr(usage, "total_token_count", None),
                                      "sources": [f"{p.parent.name}/{p.name}" for p in sources]}
                made += 1
                print(f"  {slot}: готово, {log['slots'][slot]['seconds']} с", flush=True)
            except Exception as error:  # noqa: BLE001
                log["slots"][slot] = {"status": f"ошибка {type(error).__name__}: {str(error)[:300]}"}
                print(f"  {slot}: ошибка {type(error).__name__}: {str(error)[:300]}", flush=True)
        (out / "generated.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Готово. Картинок: {made}. Папки: {OUT}/<ролик>/generated/")


if __name__ == "__main__":
    main()
