"""Проба шага 3: дорисовать края обложки через Gemini, чтобы машина была в кадре 4:3 целиком и с отступами.

Берёт из ~/Movies/uz-avto-lab/cover-test объявления, где _cover_test.py написал «нужна дорисовка»,
отправляет выбранное фото целиком и просит «отдалить» кадр. Машина должна остаться настоящей:
дорисовываются только края и срезанные части. Результат: <id>/after_ai.jpg и листы _ai_sheet_N.jpg.
Каждая картинка платная (около 5 центов). В проект и на сайт ничего не пишет.

  .venv/bin/python _cover_test_outpaint.py             все «нужна дорисовка» из пробы
  .venv/bin/python _cover_test_outpaint.py 3           первые 3
"""
import io
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from accounts import PARSER_DIR

OUT = Path.home() / "Movies" / "uz-avto-lab" / "cover-test"
MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "").strip() or "gemini-nano-banana-2.1"
PROMPT = """This is a seller's photo of a used car for sale{car}. The car is too close to the camera or cut off by the
edge of the photo. Zoom out: produce the same photo as if it was taken from a few steps further back,
as a 4:3 landscape picture for a car marketplace cover.

Result:
- The whole car is inside the frame with free space on every side. The car takes about 70% of the frame width.
  Nothing of the car is cut off by the frame edge.
- Everything visible in the original stays exactly the same: the same car, body colour, wheels, grille, lights,
  tint, the same camera angle and perspective, the same place, ground, buildings, other cars, light and time of day.
  Do not restyle, clean, repaint or re-light anything. Do not rotate the car or change the viewpoint.
- Add only what is missing: the parts of the car hidden by the frame edge (continue them consistently with the
  visible parts of this exact car model) and more of the surroundings around the original frame.
- Licence plates stay exactly as in the photo. If a plate is covered by a seller's logo or sticker, keep it as is.
- Remove price tags, captions and stickers that were overlaid on the photo by an editor (for example "68500$"),
  and fill that area with the natural background. Do not add any text, logos or watermarks.
- No new people or objects. Photorealistic, natural phone-camera look."""


def main() -> None:
    load_dotenv(PARSER_DIR / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Нет GEMINI_API_KEY в .env")
        return
    from google import genai
    from google.genai import types

    summary = json.loads((OUT / "_summary.json").read_text(encoding="utf-8"))
    rows = [row for row in summary if row["verdict"] == "нужна дорисовка"]
    if len(sys.argv) > 1:
        rows = rows[: int(sys.argv[1])]
    client = genai.Client(api_key=key)
    print(f"Модель {MODEL}, обложек: {len(rows)}")
    made, total_tokens = [], 0
    for row in rows:
        folder = OUT / row["id"]
        source = Image.open(folder / f"src_{row['chosen']}.jpg").convert("RGB")
        source.thumbnail((1280, 1280))
        car = f" ({row['title']})" if row.get("title") else ""
        started = time.time()
        try:
            data = None
            for attempt in range(3):
                response = client.models.generate_content(
                    model=MODEL, contents=[PROMPT.replace("{car}", car), source],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(aspect_ratio="4:3", image_size="1K")))
                candidate = response.candidates[0] if response.candidates else None
                for part in ((candidate.content.parts if candidate and candidate.content else None) or []):
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        data = part.inline_data.data
                if data:
                    break
                print(f"  {row['id']}: ответ без картинки, попытка {attempt + 1} из 3", flush=True)
            if not data:
                raise RuntimeError("модель не вернула картинку")
            Image.open(io.BytesIO(data)).convert("RGB").save(folder / "after_ai.jpg", quality=92)
            tokens = getattr(getattr(response, "usage_metadata", None), "total_token_count", None) or 0
            total_tokens += tokens
            made.append(row)
            print(f"  {row['id']}: готово, {round(time.time() - started, 1)} с, токенов {tokens}", flush=True)
        except Exception as error:  # noqa: BLE001
            print(f"  {row['id']}: ошибка {type(error).__name__}: {str(error)[:200]}", flush=True)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    tw, th = 440, 330
    for page, start in enumerate(range(0, len(made), 4), start=1):
        part = made[start:start + 4]
        sheet = Image.new("RGB", (4 * (tw + 10), 3 * (th + 6) + 40), "white")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(part):
            x = index * (tw + 10)
            draw.text((x + 4, 6), f"{(row['title'] or '')[:32]}", fill="black", font=font)
            for k, name in enumerate(("before.jpg", "after.jpg", "after_ai.jpg")):
                tile = Image.open(OUT / row["id"] / name).convert("RGB").resize((tw, th))
                sheet.paste(tile, (x, 36 + k * (th + 6)))
        sheet.save(OUT / f"_ai_sheet_{page}.jpg", quality=88)
    print(f"Готово. Дорисовано: {len(made)}, всего токенов: {total_tokens}. Листы: {OUT}/_ai_sheet_N.jpg "
          "(сверху как сейчас, в середине рамка по машине, снизу дорисовка)")


if __name__ == "__main__":
    main()
