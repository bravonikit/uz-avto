"""Проба: читает ли Gemini цену с видео (надпись на кадре и голос продавца).

Берёт те же ролики, что в ~/Movies/uz-avto-lab/frames-test, и для сравнения показывает цену из текста поста.
Результат: frames-test/_price_summary.json и <ролик>/price_gemini.json. В проект и архив ничего не пишет.

  .venv/bin/python _frames_test_price.py              те же 10 роликов
  .venv/bin/python _frames_test_price.py --noprice 10 ещё 10 случайных скачанных роликов, у постов которых нет цены
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

OUT = Path.home() / "Movies" / "uz-avto-lab" / "frames-test"
PROMPT = """This is a seller's video of a used car for sale in Uzbekistan. Sellers often show the price as text
overlaid on the video, and often say the price aloud (in Uzbek or Russian). Prices are usually in US dollars
(for example "13 500", "13.5", "13 ming 500", "o'n uch yarim"), sometimes in Uzbek sum (hundreds of millions).

Report only what is really in the video. Do not guess and do not use your knowledge of market prices.
1. overlay_texts: every piece of text overlaid on the video by the editor (captions, stickers, banners),
   exactly as written, with the second where it appears. Do not include text that is physically on the car,
   on number plates, on buildings or on screens inside the car.
2. price_overlay: the price written in overlaid text, or null if there is none.
3. price_voice: the price said aloud, or null if nobody says a price. Give the exact words you heard.
4. Other facts written in overlay text or said aloud: year, mileage in km, model. Null if not stated.

Answer only JSON:
{"car": "make model colour as seen",
 "overlay_texts": [{"t": seconds, "text": "..."}],
 "price_overlay": {"value": number, "currency": "USD"|"UZS", "t": seconds, "text": "exact overlay text"} | null,
 "price_voice": {"value": number, "currency": "USD"|"UZS", "t": seconds, "heard": "exact words", "language": "uz"|"ru"} | null,
 "year": {"value": number, "source": "overlay"|"voice"} | null,
 "mileage_km": {"value": number, "source": "overlay"|"voice"} | null,
 "model_stated": {"value": "...", "source": "overlay"|"voice"} | null,
 "speech": true|false}"""


_POSTS: dict[str, dict] = {}


def posts_of(channel: str) -> dict:
    if channel not in _POSTS:
        _POSTS[channel] = json.loads((TG_DIR / channel / "posts.json").read_text(encoding="utf-8"))
    return _POSTS[channel]


def text_post(channel: str, video_post: str) -> str:
    """Видео и текст часто идут двумя сообщениями: объявление это пост с текстом, у него media_from = пост с видео."""
    for number, post in posts_of(channel).items():
        if str(post.get("media_from")) == str(video_post):
            return str(number)
    return str(video_post)


def video_post(channel: str, listing_post: str) -> str:
    post = posts_of(channel).get(str(listing_post)) or {}
    return str(post.get("media_from") or listing_post)


def main() -> None:
    load_dotenv(PARSER_DIR / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Нет GEMINI_API_KEY в .env")
        return
    from google import genai
    from google.genai import types

    listings = {item["id"]: item for item in json.loads((TG_DIR / "listings.json").read_text(encoding="utf-8"))}
    places = Places()
    args = sys.argv[1:]
    if args[:1] == ["--noprice"]:
        count = int(args[1]) if len(args) > 1 else 10
        pool = [item for item in listings.values()
                if item.get("has_video") and not item.get("price") and not item.get("is_sold") and item.get("brand")]
        random.Random(18).shuffle(pool)
        jobs = []
        for item in pool:
            channel = item["source_account"]
            post = video_post(channel, item["id"].rsplit("-", 1)[1])
            if places.raw(channel, post).exists():
                jobs.append((channel, post))
            if len(jobs) == count:
                break
        summary_file = OUT / "_price_summary_noprice.json"
    else:
        jobs = sorted(tuple(p.name.rsplit("-", 1)) for p in OUT.iterdir() if (p / "picks").is_dir())
        summary_file = OUT / "_price_summary.json"
    client = genai.Client(api_key=key)
    model = os.environ.get("GEMINI_MODEL", "").strip() or pick_model(client)
    if not model:
        return
    print(f"Модель {model}, роликов: {len(jobs)}")
    summary, total_tokens = [], 0
    for channel, post in jobs:
        listing_post = text_post(channel, post)
        item = listings.get(f"tg-{channel}-{listing_post}") or {}
        raw_text = (posts_of(channel).get(listing_post) or {}).get("text") or ""
        row = {"channel": channel, "post": post, "listing": f"tg-{channel}-{listing_post}",
               "post_price": item.get("price"), "post_year": item.get("year"),
               "post_mileage": item.get("mileage_km"), "post_title": item.get("title"),
               "post_text": (item.get("description") or raw_text)[:300]}
        try:
            video = places.raw(channel, post)
            started = time.time()
            uploaded = client.files.upload(file=str(video))
            while uploaded.state and uploaded.state.name == "PROCESSING":
                time.sleep(2)
                uploaded = client.files.get(name=uploaded.name)
            response = client.models.generate_content(
                model=model, contents=[uploaded, PROMPT],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            answer = json.loads(response.text)
            client.files.delete(name=uploaded.name)
            usage = getattr(response, "usage_metadata", None)
            tokens = getattr(usage, "total_token_count", None) or 0
            total_tokens += tokens
            row.update({"answer": answer, "seconds": round(time.time() - started, 1), "tokens": tokens})
            folder = OUT / f"{channel}-{post}"
            if folder.is_dir():
                (folder / "price_gemini.json").write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
            overlay, voice = answer.get("price_overlay"), answer.get("price_voice")
            show = lambda p: f"{p.get('value')} {p.get('currency')}" if p else "нет"  # noqa: E731
            print(f"  {channel} {post}: в посте {row['post_price'] or 'нет'} | надпись {show(overlay)} | голос {show(voice)}",
                  flush=True)
        except Exception as error:  # noqa: BLE001
            row["error"] = f"{type(error).__name__}: {str(error)[:200]}"
            print(f"  {channel} {post}: ошибка {row['error']}", flush=True)
        summary.append(row)
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Готово. Всего токенов: {total_tokens}. Итог: {summary_file}")


if __name__ == "__main__":
    main()
