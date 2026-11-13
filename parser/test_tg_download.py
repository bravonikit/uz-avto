"""Проверка разбора страницы Telegram и слияния постов. Запуск: python test_tg_download.py"""

from tg_download import days_ago, glue_media, is_deep_due, merge_posts, parse_page, parse_views

FOOT = ('<div class="tgme_widget_message_footer"><div class="tgme_widget_message_info">'
        '<span class="tgme_widget_message_views">{views}</span><span class="tgme_widget_message_meta">{edited}'
        '<a class="tgme_widget_message_date" href="#"><time datetime="{dt}" class="time">09:54</time></a></span></div></div>')


def message(post_id, body, dt, views="1.16K", edited=""):
    return (f'<div class="tgme_widget_message js-widget_message" data-post="azaavtoo/{post_id}">'
            f'<div class="tgme_widget_message_bubble">{body}{FOOT.format(views=views, edited=edited, dt=dt)}</div></div>')


ROUND = ('<div class="tgme_widget_message_roundvideo_player"><i class="tgme_widget_message_roundvideo_thumb" '
         'style="background-image:url(\'https://cdn4.telesco.pe/file/thumb.jpg\')"></i>'
         '<video class="tgme_widget_message_roundvideo" src="https://cdn4.telesco.pe/file/v.mp4"></video>'
         '<time class="tgme_widget_message_roundvideo_duration">0:52</time></div>')
TEXT = '<div class="tgme_widget_message_text js-message_text" dir="auto">Li 9 Livis<br>Yili: 2026<br>Narxi: {price}$<br><i class="emoji"><b>☎️</b></i>+998(94)662-11-27</div>'
ALBUM = ('<div class="tgme_widget_message_grouped_wrap">'
         + "".join(f'<a class="tgme_widget_message_photo_wrap" style="left:0px;background-image:url(\'https://cdn4.telesco.pe/file/p{n}.jpg\')" href="#"></a>' for n in range(6))
         + '</div><div class="tgme_widget_message_text">XPENG GX<br>Gibrid Max 44000$</div>')
BIG_VIDEO = ('<a class="tgme_widget_message_video_player not_supported"><i class="tgme_widget_message_video_thumb" '
             'style="background-image:url(\'https://cdn4.telesco.pe/file/t2.jpg\')"></i><time class="message_video_duration">1:24</time></a>')

page = "<html><body>" + "".join([
    message(1376, ROUND, "2026-11-09T09:53:34+00:00", views="1.2K"),
    message(1377, TEXT.format(price="104 500"), "2026-11-09T09:54:18+00:00"),
    message(1380, ALBUM, "2026-11-10T03:06:00+00:00", views="225"),
    message(1386, BIG_VIDEO, "2026-11-10T05:00:00+00:00", views="2.3M"),
]) + "</body></html>"

posts = parse_page(page, "azaavtoo")
assert [post["id"] for post in posts] == [1376, 1377, 1380, 1386]
assert [post["type"] for post in posts] == ["video", "text", "album", "video"]
assert posts[0]["video_url"].endswith("v.mp4") and posts[0]["video_durations"] == ["0:52"]
assert posts[1]["text"] == "Li 9 Livis\nYili: 2026\nNarxi: 104 500$\n☎️+998(94)662-11-27", posts[1]["text"]
assert posts[1]["date"] == "2026-11-09T09:54:18Z" and posts[1]["views"] == 1160
assert len(posts[2]["photos"]) == 6 and posts[2]["photos"][0].endswith("p0.jpg")
assert posts[3]["video_url"] is None and posts[3]["video_thumbs"] and posts[3]["views"] == 2_300_000
assert parse_views("580") == 580 and parse_views(None) is None

# Первый прогон: всё новое, кружок склеен с текстом
old_text = posts[1]["text"]
known = {}
assert merge_posts(known, posts, "2026-11-10T06:00:00Z", 1376) == {"new": 4, "changed": 0, "removed": 0}
glue_media(known)
assert known["1377"]["media_from"] == 1376 and known["1376"]["text_in"] == 1377
assert "media_from" not in known["1380"]

# Второй прогон: цена изменена и дописано «продано», альбом удалён
page2 = "<html><body>" + "".join([
    message(1376, ROUND, "2026-11-09T09:53:34+00:00"),
    message(1377, TEXT.format(price="107 000") .replace("</div>", "<br>‼️SOTILDI‼️</div>"), "2026-11-09T09:54:18+00:00", edited="edited "),
    message(1386, BIG_VIDEO, "2026-11-10T05:00:00+00:00"),
]) + "</body></html>"
counts = merge_posts(known, parse_page(page2, "azaavtoo"), "2026-11-11T06:00:00Z", 1376)
assert counts == {"new": 0, "changed": 1, "removed": 1}, counts
assert "107 000" in known["1377"]["text"] and "SOTILDI" in known["1377"]["text"] and known["1377"]["edited"]
assert known["1377"]["history"] == [{"until": "2026-11-11T06:00:00Z", "text": old_text}]
assert known["1380"]["removed_at"] == "2026-11-11T06:00:00Z" and known["1377"]["first_seen"] == "2026-11-10T06:00:00Z"

# Если страницы прочитаны не подряд (ошибка сети), удалёнными никого не помечаем
known2 = {}
merge_posts(known2, posts, "2026-11-10T06:00:00Z", 1376)
assert merge_posts(known2, parse_page(page2, "azaavtoo"), "2026-11-11T06:00:00Z", None)["removed"] == 0

# Глубокий обход: первый запуск, ни разу не делали, делали давно
assert is_deep_due({}, days_ago(1)) and is_deep_due(known, None) and is_deep_due(known, days_ago(8))
assert not is_deep_due(known, days_ago(2))

print("ok: разбор страницы, склейка видео с текстом, история правок, удалённые посты")
