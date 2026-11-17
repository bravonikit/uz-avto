"""Лучшие кадры машины из видео через Gemini API: модель смотрит ролик целиком и называет секунды.

  python gemini_frames.py autovitauz 2535

Ключ: GEMINI_API_KEY в parser/.env (aistudio.google.com → Get API key). Модель: GEMINI_MODEL, по умолчанию gemini-flash-latest.
Результат: <ARCHIVE_DIR>/videos/<канал>/tg-<канал>-<id>/picks_gemini/  front_3q.jpg, side.jpg, rear_3q.jpg, interior.jpg, answer.json
"""

from __future__ import annotations

import json
import os
import sys
import time

from dotenv import load_dotenv

from accounts import PARSER_DIR
from tg_video import Places, find_ffmpeg, run

SLOTS = ["front_3q", "side", "rear_3q", "interior"]
PROMPT = """You are a photo editor of a car marketplace. Watch this car review video.
For each slot find the single moment where the car is shown best for a listing photo:
- front_3q: the whole car diagonally from the front corner (front and one side visible)
- side: the whole car exactly from the side
- rear_3q: the whole car diagonally from the back corner
- interior: the dashboard, steering wheel and front seats
Prefer moments where the camera is steady, the image is sharp, the whole car is in frame and no person blocks it.
If the video never shows a slot well, return null for it.
Answer only JSON: {"car": "make model color", "front_3q": {"t": seconds_float, "why": "..."} | null, "side": ..., "rear_3q": ..., "interior": ..., "people_talking": true|false}"""


def main() -> None:
    channel, post = sys.argv[1], sys.argv[2]
    load_dotenv(PARSER_DIR / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Нет GEMINI_API_KEY в .env")
        return
    from google import genai
    from google.genai import types

    places = Places()
    video = places.raw(channel, post)
    if not video.exists():
        print(f"Нет ролика {video}. Сначала скачайте его через tg_video.py")
        return
    client = genai.Client(api_key=key)
    model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    started = time.time()
    uploaded = client.files.upload(file=str(video))
    while uploaded.state and uploaded.state.name == "PROCESSING":  # Google сначала обрабатывает видео
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)
    response = client.models.generate_content(
        model=model, contents=[uploaded, PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
    answer = json.loads(response.text)
    client.files.delete(name=uploaded.name)

    out = places.cut(channel, post) / "picks_gemini"
    out.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    for slot in SLOTS:
        pick = answer.get(slot)
        if pick and pick.get("t") is not None:
            run(ffmpeg, "-ss", f"{float(pick['t']):.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out / f"{slot}.jpg"))
    usage = getattr(response, "usage_metadata", None)
    answer["_meta"] = {"model": model, "seconds": round(time.time() - started, 1),
                       "tokens": getattr(usage, "total_token_count", None)}
    (out / "answer.json").write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(answer, ensure_ascii=False, indent=1))
    print(f"Кадры: {out}")


if __name__ == "__main__":
    main()
