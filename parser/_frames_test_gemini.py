"""Проба: те же ролики, что разобрал _frames_test.py, но кадры выбирает Gemini API.

Берёт ролики по папкам в ~/Movies/uz-avto-lab/frames-test и кладёт рядом с локальными кадрами:
  <ролик>/picks_gemini/  front_3q_1.jpg ... interior_3.jpg, answer.json
В проект и в архив ничего не пишет. Ключ: GEMINI_API_KEY в parser/.env.

  .venv/bin/python _frames_test_gemini.py
"""
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from accounts import PARSER_DIR
from tg_video import Places, find_ffmpeg, run

OUT = Path.home() / "Movies" / "uz-avto-lab" / "frames-test"
SLOTS = {"front_3q": 2, "front": 1, "side": 2, "rear_3q": 2, "rear": 1, "interior": 3}  # как в video_frames.py
PROMPT = """You are a photo editor of a car marketplace. Watch this car review video.
For each slot find the best moments for a listing photo. Slots and how many moments to return at most:
- front_3q (up to 2): the whole car diagonally from the front corner (front and one side visible)
- front (1): the whole car straight from the front
- side (up to 2): the whole car exactly from the side
- rear_3q (up to 2): the whole car diagonally from the back corner
- rear (1): the whole car straight from behind
- interior (up to 3): wide views of the cabin: dashboard, steering wheel and front seats
Most important rule: for every slot choose the moment filmed from as FAR AWAY as possible, where the car
looks smallest in the frame, is fully visible with all its edges inside the frame, and as much of the
surroundings (ground, buildings, sky) as possible is visible. Never choose a close-up when a wider moment
of the same view exists. For interior choose the widest view of the whole cabin, not a close-up of a detail.
After distance prefer: steady camera, sharp image, no person or hand blocking the car, no text overlay.
Try to fill all 11 moments (2+1+2+2+1+3) whenever the video really shows these views.
Moments of one slot must look clearly different from each other (at least 2 seconds apart, different framing).
Do not put the same view into two slots. If the video never shows a slot well, return an empty list for it:
a missing slot is better than a wrong one.
Answer only JSON: {"car": "make model color", "front_3q": [{"t": seconds_float, "why": "..."}], "front": [...],
"side": [...], "rear_3q": [...], "rear": [...], "interior": [...], "people_talking": true|false}"""


def pick_model(client) -> str:
    """Спрашиваем у Google, какие модели доступны этому ключу, и берём самую новую flash (не lite)."""
    import re
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(m.name.split("/")[-1])
    print("Доступные модели:", ", ".join(sorted(names)))
    skip = ("lite", "image", "tts", "live", "audio", "embedding", "robotics", "computer")

    def version(name: str) -> float:
        found = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
        return float(found.group(1)) if found else 0.0

    flash = [n for n in names if "flash" in n and not any(word in n for word in skip)]
    if not flash:
        print("Среди доступных нет модели flash. Впишите нужную в .env: GEMINI_MODEL=...")
        return ""
    # новее версия лучше, при равной версии стабильная лучше preview, короткое имя лучше длинного
    flash.sort(key=lambda n: (-version(n), "preview" in n or "exp" in n, len(n)))
    return flash[0]


def main() -> None:
    load_dotenv(PARSER_DIR / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Нет GEMINI_API_KEY в .env")
        return
    from google import genai
    from google.genai import types

    jobs = sorted(p.name.rsplit("-", 1) for p in OUT.iterdir() if (p / "picks").is_dir())
    if not jobs:
        print(f"Нет роликов в {OUT}: сначала _frames_test.py")
        return
    places, ffmpeg = Places(), find_ffmpeg()
    client = genai.Client(api_key=key)
    model = os.environ.get("GEMINI_MODEL", "").strip() or pick_model(client)
    if not model:
        return
    print(f"Модель {model}, роликов: {len(jobs)}")
    total_tokens = 0
    for channel, post in jobs:
        try:
            video = places.raw(channel, post)
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
            out = OUT / f"{channel}-{post}" / "picks_gemini"
            out.mkdir(parents=True, exist_ok=True)
            for old in out.glob("*.jpg"):
                old.unlink()
            got = []
            for slot, count in SLOTS.items():
                picks = answer.get(slot) or []
                if isinstance(picks, dict):
                    picks = [picks]
                for n, pick in enumerate(picks[:count], start=1):
                    if pick.get("t") is None:
                        continue
                    name = slot if count == 1 else f"{slot}_{n}"
                    run(ffmpeg, "-ss", f"{float(pick['t']):.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2",
                        str(out / f"{name}.jpg"))
                    got.append(name)
            usage = getattr(response, "usage_metadata", None)
            tokens = getattr(usage, "total_token_count", None) or 0
            total_tokens += tokens
            answer["_meta"] = {"model": model, "seconds": round(time.time() - started, 1), "tokens": tokens}
            (out / "answer.json").write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding="utf-8")
            status = f"{answer.get('car')}: кадров {len(got)}, {answer['_meta']['seconds']} с, токенов {tokens}"
        except Exception as error:  # noqa: BLE001
            status = f"ошибка {type(error).__name__}: {str(error)[:200]}"
        print(f"  {channel} {post}: {status}", flush=True)
    print(f"Готово. Всего токенов: {total_tokens}. Кадры: {OUT}/<ролик>/picks_gemini/")


if __name__ == "__main__":
    main()
