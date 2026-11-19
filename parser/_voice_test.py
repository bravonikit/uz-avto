"""Проба: текст из видео. Gemini слушает звук ролика (frames/audio.m4a в папке поста) и отдаёт
дословную расшифровку, короткую выжимку на русском и факты, сказанные голосом (цена, год, пробег...).

Берёт случайные ролики с речью из разных каналов и рядом кладёт то, что уже есть в объявлении,
чтобы сравнить «что сказали в видео» и «что вышло на сайте». В проект и архив ничего не пишет.

  .venv/bin/python _voice_test.py          10 роликов, по одному на канал
  .venv/bin/python _voice_test.py 20       20 роликов

Результат: ~/Movies/uz-avto-lab/voice-test/
    <канал>-<пост>/transcript.txt, voice.json
    _summary.md    таблица для глаз: пост против голоса
    _summary.json  то же для кода, плюс токены и время
"""
import json
import os
import random
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from accounts import PARSER_DIR
from tg_video import Places, TG_DIR
from _frames_test_gemini import pick_model

OUT = Path.home() / "Movies" / "uz-avto-lab" / "voice-test"
PROMPT = """This is the audio track of a seller's video of a car for sale in Uzbekistan (Tashkent).
People usually speak Uzbek, Russian or a mix of both. Sometimes there is only music.

Report only what is really said. Do not guess and do not use your knowledge of cars or market prices.
1. speech: true if somebody talks about the car, false if there is only music, noise or silence.
2. transcript: everything said, word for word, in the original language(s), as it was spoken.
   Do not translate. Empty string if there is no speech.
3. summary_ru: 2 to 5 short sentences in Russian for a car listing page: what the seller says about this car
   (condition, equipment, history, documents, bargaining, exchange, credit). No price words like "дешево".
   Empty string if there is no speech.
4. Facts said aloud. Null if not said. "heard" is the exact words as spoken.
   Prices are usually in US dollars ("13 500", "13 ming 500", "o'n uch yarim", "тринадцать с половиной"),
   sometimes in Uzbek sum (hundreds of millions).

Answer only JSON:
{"speech": true|false,
 "languages": ["uz"|"ru"|"other"],
 "transcript": "...",
 "summary_ru": "...",
 "price": {"value": number, "currency": "USD"|"UZS", "heard": "..."} | null,
 "year": {"value": number, "heard": "..."} | null,
 "mileage_km": {"value": number, "heard": "..."} | null,
 "model": {"value": "...", "heard": "..."} | null,
 "color": {"value": "...", "heard": "..."} | null,
 "equipment": {"value": "...", "heard": "..."} | null,
 "condition": {"value": "...", "heard": "..."} | null,
 "bargain": {"value": true|false, "heard": "..."} | null,
 "credit_or_exchange": {"value": "...", "heard": "..."} | null,
 "phone": {"value": "...", "heard": "..."} | null}"""

_POSTS: dict[str, dict] = {}


def posts_of(channel: str) -> dict:
    if channel not in _POSTS:
        _POSTS[channel] = json.loads((TG_DIR / channel / "posts.json").read_text(encoding="utf-8"))
    return _POSTS[channel]


def video_post(channel: str, listing_post: str) -> str:
    """Видео и текст часто идут двумя сообщениями: у поста с текстом media_from = пост с видео."""
    post = posts_of(channel).get(str(listing_post)) or {}
    return str(post.get("media_from") or listing_post)


def pick_jobs(listings: dict, places: Places, count: int) -> list[tuple[dict, str, Path]]:
    pool = [item for item in listings.values()
            if item.get("has_video") and not item.get("is_sold") and item.get("brand")]
    random.Random(int(time.time())).shuffle(pool)
    jobs, used_channels = [], set()
    for one_per_channel in (True, False):  # сначала по одному на канал, если каналов мало, добираем
        for item in pool:
            if len(jobs) == count:
                return jobs
            channel = item["source_account"]
            if (one_per_channel and channel in used_channels) or any(j[0] is item for j in jobs):
                continue
            post = video_post(channel, item["id"].rsplit("-", 1)[1])
            audio = places.cut(channel, post) / "audio.m4a"
            if audio.exists():
                jobs.append((item, post, audio))
                used_channels.add(channel)
    return jobs


def ask(client, types, model: str, audio: Path):
    uploaded = client.files.upload(file=str(audio), config={"mime_type": "audio/mp4"})
    while uploaded.state and uploaded.state.name == "PROCESSING":
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)
    try:
        response = client.models.generate_content(
            model=model, contents=[uploaded, PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
    finally:
        client.files.delete(name=uploaded.name)
    return json.loads(response.text), getattr(response, "usage_metadata", None)


def value(fact):
    return fact.get("value") if isinstance(fact, dict) else None


def cell(text) -> str:
    return str(text if text not in (None, "") else "·").replace("|", "/").replace("\n", " ")


def main() -> None:
    load_dotenv(PARSER_DIR / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Нет GEMINI_API_KEY в .env")
        return
    from google import genai
    from google.genai import types

    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    listings = {item["id"]: item for item in json.loads((TG_DIR / "listings.json").read_text(encoding="utf-8"))}
    places = Places()
    jobs = pick_jobs(listings, places, count)
    if not jobs:
        print("Не нашёл роликов со звуком. Раскадровка (tg_video.py --only cut) уже прошла?")
        return
    client = genai.Client(api_key=key)
    model = os.environ.get("GEMINI_MODEL", "").strip() or pick_model(client)
    if not model:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Модель {model}, роликов: {len(jobs)}")

    rows, totals = [], {"prompt_tokens": 0, "total_tokens": 0, "seconds": 0.0}
    for item, post, audio in jobs:
        channel = item["source_account"]
        row = {"listing": item["id"], "channel": channel, "video_post": post,
               "post": {"title": item.get("title"), "price": item.get("price"), "year": item.get("year"),
                        "mileage_km": item.get("mileage_km"),
                        "text": (item.get("description") or "")[:400]}}
        started = time.time()
        try:
            answer, usage = ask(client, types, model, audio)
        except Exception as error:  # noqa: BLE001  один плохой ролик не должен ронять пробу
            row["error"] = str(error)[:300]
            print(f"  {item['id']}: ошибка {row['error']}")
            rows.append(row)
            continue
        row["voice"] = answer
        row["seconds"] = round(time.time() - started, 1)
        row["tokens"] = {"prompt": getattr(usage, "prompt_token_count", None),
                         "total": getattr(usage, "total_token_count", None)}
        totals["prompt_tokens"] += row["tokens"]["prompt"] or 0
        totals["total_tokens"] += row["tokens"]["total"] or 0
        totals["seconds"] += row["seconds"]

        folder = OUT / f"{channel}-{post}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "transcript.txt").write_text(answer.get("transcript") or "", encoding="utf-8")
        (folder / "voice.json").write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding="utf-8")
        rows.append(row)
        print(f"  {item['id']}: речь {'да' if answer.get('speech') else 'нет'}, "
              f"цена голосом {value(answer.get('price'))}, {row['seconds']} с")

    (OUT / "_summary.json").write_text(
        json.dumps({"model": model, "totals": totals, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    with_speech = [r for r in rows if r.get("voice", {}).get("speech")]
    lines = [f"# Проба: текст из видео ({time.strftime('%d.%m.%Y %H:%M')})", "",
             f"Модель {model}. Роликов {len(rows)}, с речью {len(with_speech)}, "
             f"токенов всего {totals['total_tokens']}, время {round(totals['seconds'])} с.", "",
             "| Объявление | Цена: пост / голос | Год: пост / голос | Пробег: пост / голос | Выжимка для сайта |",
             "|---|---|---|---|---|"]
    for r in rows:
        voice, post = r.get("voice") or {}, r["post"]
        summary = r.get("error") or (voice.get("summary_ru") if voice.get("speech") else "речи нет")
        lines.append(f"| {r['listing']}<br>{cell(post['title'])} "
                     f"| {cell(post['price'])} / {cell(value(voice.get('price')))} "
                     f"| {cell(post['year'])} / {cell(value(voice.get('year')))} "
                     f"| {cell(post['mileage_km'])} / {cell(value(voice.get('mileage_km')))} "
                     f"| {cell(summary)} |")
    lines += ["", "## Подробно", ""]
    for r in rows:
        voice = r.get("voice") or {}
        lines += [f"### {r['listing']}", "", f"Текст поста: {cell(r['post']['text'])}", "",
                  f"Расшифровка: {cell(voice.get('transcript'))}", ""]
    (OUT / "_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Готово: {OUT / '_summary.md'}")


if __name__ == "__main__":
    main()
