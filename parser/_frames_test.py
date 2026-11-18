"""Проба раскадровки: 10 случайных скачанных роликов с разных каналов.

Результат НЕ в проект и НЕ в архив, а во временную папку ~/Movies/uz-avto-lab/frames-test
(её можно удалить целиком). Сырые ролики не меняются.

  .venv/bin/python _frames_test.py        10 роликов
  .venv/bin/python _frames_test.py 5      5 роликов
"""
import random
import shutil
import subprocess
import sys
from pathlib import Path

import video_frames as vf
from tg_video import Places, find_ffmpeg

OUT = Path.home() / "Movies" / "uz-avto-lab" / "frames-test"
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 10


class TestPlaces(Places):
    def cut(self, channel, post_id):  # раскадровка во временную папку, а не на Диск
        return OUT / f"{channel}-{post_id}"


def main() -> None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("нет ffmpeg: pip install -r requirements.txt")
        return
    places = TestPlaces()
    by_channel = {}
    for folder in sorted(places.raw_root.glob("*/videos")):
        videos = [p for p in folder.glob("*.mp4") if p.stat().st_size > 1_000_000]
        if videos:
            by_channel[folder.parent.name] = videos
    if not by_channel:
        print(f"Роликов не нашлось в {places.raw_root}")
        return
    channels = random.sample(sorted(by_channel), min(COUNT, len(by_channel)))
    jobs = [(c, random.choice(by_channel[c]).stem) for c in channels]
    for _ in range(200):  # каналов с видео меньше, чем нужно роликов: добираем из тех же
        if len(jobs) >= COUNT:
            break
        c = random.choice(channels)
        job = (c, random.choice(by_channel[c]).stem)
        if job not in jobs:
            jobs.append(job)
    print(f"Каналов с видео: {len(by_channel)}, берём роликов: {len(jobs)}. Папка: {OUT}")
    sheets = OUT / "_sheets"
    sheets.mkdir(parents=True, exist_ok=True)
    classify = vf.load_clip("ViT-B-32", "laion2b_s34b_b79k")
    for channel, post in jobs:
        try:
            status = vf.process(classify, ffmpeg, places, channel, post)
            sheet = places.cut(channel, post) / "picks" / "sheet.jpg"
            if sheet.exists():
                shutil.copyfile(sheet, sheets / f"{channel}-{post}.jpg")
        except Exception as error:  # noqa: BLE001
            status = f"ошибка {type(error).__name__}: {str(error)[:150]}"
        print(f"  {channel} {post}: {status}")
    print(f"Готово. Листы всех роликов: {sheets}")
    subprocess.run(["open", str(OUT)], check=False)


if __name__ == "__main__":
    main()
