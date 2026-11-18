"""Проверка чтения канала через аккаунт Telegram (api_posts): без сети, на поддельных сообщениях.
Запуск: python test_tg_account.py"""

from datetime import datetime, timezone
from types import SimpleNamespace

from tg_download import api_posts, merge_posts, text_hash


def message(number, text="", photo=False, video=False, group=None, minute=0, duration=None, **extra):
    fields = dict(id=number, message=text, photo=photo or None, video=video or None, video_note=None, gif=None,
                  grouped_id=group, date=datetime(2026, 11, 16, 5, minute, 0, tzinfo=timezone.utc), action=None,
                  file=SimpleNamespace(duration=duration), views=1100, edit_date=None, forward=None,
                  reply_to_msg_id=None)
    fields.update(extra)
    return SimpleNamespace(**fields)


# Как в a721_motors: альбом из 3 фото без текста, следом видео с описанием. API отдаёт новые сообщения первыми
messages = [
    message(4405, "Baraka boldi", reply_to_msg_id=4402, minute=40),
    message(4404, action="pinned"),
    message(4402, "Infiniti QX 80\nNarxi - 34.900$ ", video=True, duration=134, minute=28),
    message(4393, photo=True, group=77, minute=17),
    message(4392, photo=True, group=77, minute=17),
    message(4391, photo=True, group=77, minute=17),
]
posts = api_posts(messages, "a721_motors")
assert [post["id"] for post in posts] == [4391, 4402, 4405], posts
album, video, sold = posts
assert album["type"] == "album" and album["text"] == "" and album["photos"] == ["tg://4391", "tg://4392", "tg://4393"]
assert video["type"] == "video" and video["video_thumbs"] == ["tg://4402"] and video["video_durations"] == ["2:14"]
assert video["text"] == "Infiniti QX 80\nNarxi - 34.900$" and video["date"] == "2026-11-16T05:28:00Z"
assert video["url"] == "https://t.me/a721_motors/4402" and video["views"] == 1100 and video["video_url"] is None
assert sold["type"] == "text" and sold["reply_to"] == 4402

# Пост, сохранённый раньше из веб версии, остаётся тем же постом: номер совпал, скачанные картинки на месте
known = {"4391": {"id": 4391, "text": "", "text_hash": text_hash(""), "history": [], "photos": ["https://cdn/1.jpg"],
                  "images": ["data/_tg/a721_motors/images/4391_1.jpg"], "last_seen": "x"}}
counts = merge_posts(known, posts, "2026-11-18T12:00:00Z", posts[0]["id"])
assert counts == {"new": 2, "changed": 0, "removed": 0}, counts
assert known["4391"]["photos"][0] == "tg://4391" and known["4391"]["images"] == ["data/_tg/a721_motors/images/4391_1.jpg"]

print("ok: альбом одним постом, видео, ответ «продано», слияние с постами из веб версии")
