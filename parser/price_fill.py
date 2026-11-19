"""Цена из голоса продавца и с надписей на фото для объявлений Telegram, где в тексте цены нет.
В том же запросе модель отдаёт запас хода и состояние батареи, если продавец их называет.

  .venv/bin/python price_fill.py start [--limit 300]   отправить пакет в Gemini (пакетный режим, вдвое дешевле)
  .venv/bin/python price_fill.py check [--wait]        забрать готовые ответы в data/price_fill.json
  .venv/bin/python price_fill.py run [--limit 300]     check, потом start новых (так в run_daily.sh)

Что уходит в Gemini по одному объявлению: до 3 фото поста (обложка первой, уменьшенные до 1024 px),
звук ролика (первые 2 минуты, моно mp3) и текст поста. Около 2–5 тысяч токенов, порядка 0,1–0,2 цента.
Каждое объявление спрашиваем один раз: повторно только после ручного удаления из data/price_fill/state.json.

Результат data/price_fill.json: {"id": {"price_image": {...}|null, "price_voice": {...}|null,
"range_km", "battery_pct", "model": "...", "at": "..."}}. Его применяет export_to_site.py (apply_price_fill):
цену ставит, только если в тексте поста её нет, и помечает источник (price_source: image или voice).
"""
from __future__ import annotations

import base64
import io
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

import _batch_day as bd
from accounts import PARSER_DIR
from tg_video import Places, find_ffmpeg

DATA = PARSER_DIR / "data"
FOLDER = DATA / "price_fill"
RESULT_FILE = DATA / "price_fill.json"
SITE_FILE = PARSER_DIR.parent / "src" / "data" / "instagram-listings.json"
TG_LISTINGS = DATA / "_tg" / "listings.json"
MAX_PHOTOS, PHOTO_SIDE, AUDIO_SECONDS = 3, 1024, 120
DEFAULT_LIMIT = 300

PROMPT = """This is a used car listing from a Telegram channel in Uzbekistan: photos of the post, the seller's audio
from the video (if present) and the post text. The text itself has no price, find it elsewhere.
- price_image: the asking price written ON A PHOTO (overlay text, banner, sticker, price tag).
- price_voice: the asking price the seller SAYS in the audio. Sellers speak Uzbek or Russian.
  Spoken prices are usually in thousands of US dollars: "o'n to'qqiz yarim" or "девятнадцать с половиной" = 19500,
  "yigirma uch besh yuz" or "двадцать три пятьсот" = 23500, "19.9" = 19900. Sums in UZS are millions of sum.
Only the full price of the car. Not a monthly payment, down payment, customs fee, deposit or a price of another car.
If several prices (several cars or trims), return the one for the main car of the post. If unsure, return null.
Also, only if clearly stated anywhere (photo, audio or text):
- range_km: electric driving range in km claimed by the seller (e.g. 605, 520, 150 for a hybrid)
- battery_pct: battery health in percent (e.g. 98)
Answer only JSON:
{"car": "make model as seen or heard",
 "price_image": {"value": number, "currency": "USD"|"UZS"|"EUR", "text": "exact text on the photo"} | null,
 "price_voice": {"value": number, "currency": "USD"|"UZS"|"EUR", "heard": "exact words", "approx": true|false} | null,
 "range_km": number | null, "battery_pct": number | null}

Post text:
"""


def _jpeg(path: Path) -> dict | None:
    try:
        image = Image.open(path).convert("RGB")
    except OSError:
        return None  # файл ещё не скачан с Google Диска
    image.thumbnail((PHOTO_SIDE, PHOTO_SIDE))
    return bd.jpeg_part(image)


def _audio(video: Path, ffmpeg: str | None) -> dict | None:
    if not ffmpeg or not video.exists():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "a.mp3"
        done = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(video), "-t", str(AUDIO_SECONDS), "-vn",
                               "-ac", "1", "-ar", "16000", "-b:a", "32k", str(out)], capture_output=True)
        if done.returncode != 0 or not out.exists() or out.stat().st_size < 2000:
            return None  # в ролике нет звука
        return {"inlineData": {"mimeType": "audio/mp3", "data": base64.b64encode(out.read_bytes()).decode()}}


def _state() -> dict:
    FOLDER.mkdir(parents=True, exist_ok=True)
    state = bd.load_state(FOLDER)
    state.setdefault("jobs", [])
    state.setdefault("asked", {})
    return state


def candidates() -> list[dict]:
    """Объявления Telegram на сайте: в наличии, без цены в тексте, ещё не спрошенные."""
    site = json.loads(SITE_FILE.read_text(encoding="utf-8"))
    raw = {item["id"]: item for item in json.loads(TG_LISTINGS.read_text(encoding="utf-8"))}
    asked = _state()["asked"]
    done = json.loads(RESULT_FILE.read_text(encoding="utf-8")) if RESULT_FILE.exists() else {}
    suspects_file = DATA / "price_suspects.json"
    # Цена в тексте есть, но странная и скрыта: это работа для ручного разбора, а не для голоса
    suspects = {s["id"] for s in json.loads(suspects_file.read_text(encoding="utf-8"))} if suspects_file.exists() else set()
    out = []
    for item in site:
        if (item["id"].startswith("tg-") and item["id"] in raw and item["id"] not in asked and item["id"] not in done
                and item["id"] not in suspects and item.get("price_source") is None and item["price"] is None
                and not item.get("price_type") and not item.get("is_sold")):
            out.append({**raw[item["id"]], "site": item})
    return sorted(out, key=lambda x: x.get("date") or "", reverse=True)  # свежие первыми


def start(limit: int) -> None:
    items = candidates()[:limit]
    if not items:
        print("Цена из голоса и фото: новых объявлений без цены нет")
        return
    places, ffmpeg, cache = Places(), find_ffmpeg(), {}
    lines, keys = [], []
    for item in items:
        parts: list[dict] = []
        for rel in (item.get("images") or [])[:MAX_PHOTOS]:
            part = _jpeg(PARSER_DIR / rel)
            if part:
                parts.append(part)
        if item.get("has_video"):
            channel, post = item["id"][3:].rsplit("-", 1)
            media = bd.video_post(channel, post, cache)
            audio = _audio(places.raw(channel, media), ffmpeg)
            if audio:
                parts.append(audio)
        if not parts:
            continue  # нечего смотреть: ни фото, ни звука
        parts.append({"text": PROMPT + (item.get("description") or "")[:2500]})
        lines.append({"key": item["id"], "request": {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}})
        keys.append(item["id"])
    if not lines:
        print("Цена из голоса и фото: файлов для отправки нет (не скачаны с Диска?)")
        return
    api = bd.client()
    state = _state()
    name = datetime.now().strftime("%Y%m%d-%H%M")
    job = bd.submit(api, FOLDER, f"price_{name}", bd.VIDEO_MODEL, lines)
    state["jobs"].append({**job, "name": name})
    for key in keys:
        state["asked"][key] = name
    bd.save_state(FOLDER, state)


def check(wait: bool) -> None:
    state = _state()
    pending = [job for job in state["jobs"] if not job.get("collected")]
    if not pending:
        print("Цена из голоса и фото: пакетов в работе нет")
        return
    api = bd.client()
    result = json.loads(RESULT_FILE.read_text(encoding="utf-8")) if RESULT_FILE.exists() else {}
    while pending:
        for job_info in list(pending):
            job = api.batches.get(name=job_info["job"])
            status = job.state.name if job.state else "?"
            if status == "JOB_STATE_SUCCEEDED":
                spent, found = 0.0, 0
                for key, item in bd.results(api, job).items():
                    dollars, _ = bd.cost_of(item, job_info["model"])
                    spent += dollars
                    try:
                        answer = json.loads(bd.text_of(item) or "{}")
                    except ValueError:
                        answer = {}
                    if not isinstance(answer, dict):
                        answer = {}
                    found += bool(answer.get("price_image") or answer.get("price_voice"))
                    result[key] = {**{k: answer.get(k) for k in ("car", "price_image", "price_voice", "range_km", "battery_pct")},
                                   "at": job_info["sent"]}
                job_info.update(collected=True, cost=round(spent, 3), found=found)
                print(f"Цена из голоса и фото: пакет {job_info['name']} готов, цена найдена у {found} из "
                      f"{job_info['requests']}, потрачено ${spent:.2f}", flush=True)
                pending.remove(job_info)
            elif status in bd.DONE_STATES:
                job_info.update(collected=True, failed=status)
                pending.remove(job_info)
                print(f"Цена из голоса и фото: пакет {job_info['name']} не выполнен: {status}", flush=True)
        RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        bd.save_state(FOLDER, state)
        if not pending or not wait:
            break
        time.sleep(180)
    if pending:
        print(f"Цена из голоса и фото: ещё в работе {len(pending)} пакет(а), заберём при следующем запуске")


def main() -> None:
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else DEFAULT_LIMIT
    if args[:1] == ["start"]:
        start(limit)
    elif args[:1] == ["check"]:
        check("--wait" in args)
    elif args[:1] == ["run"]:
        check(False)
        start(limit)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
