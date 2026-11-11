"""Официальный Instagram API (Business Discovery): посты чужих бизнес аккаунтов по имени.

Замена gallery-dl: не нужен вход через Safari, нет риска блокировки аккаунта,
не ломается при изменениях сайта Instagram. Ограничения: видит только бизнес и
авторские аккаунты (личные не отдаёт), у части рилсов нет картинки.

Настройки лежат в .env (в git не попадает):
  IG_ACCESS_TOKEN   длинный токен (живёт 60 дней, продлевается сам)
  IG_USER_ID        id нашего бизнес аккаунта Instagram
  IG_APP_ID, IG_APP_SECRET  приложение Meta, нужны для продления токена
  IG_TOKEN_EXPIRES  до какого дня годен токен

Команды:
  python ig_api.py setup                    первый раз: вписать токен в .env
  python ig_api.py test auto_sale_abdulloh  проверить на одном аккаунте
  python ig_api.py refresh                  продлить токен ещё на 60 дней
  python ig_api.py status                   сколько дней осталось у токена
"""

import sys
from datetime import datetime, timedelta, timezone

import requests

from accounts import PARSER_DIR, clean_name

ENV_FILE = PARSER_DIR / ".env"
GRAPH_URL = "https://graph.facebook.com"
TIMEOUT = 30
TOKEN_DAYS = 60  # столько живёт длинный токен
REFRESH_DAYS = 10  # продлеваем, когда осталось меньше

# Коды ошибок Meta
TOKEN_ERROR = 190  # токен просрочен или отозван
LIMIT_ERRORS = {4, 17, 32, 613, 80002}  # слишком много запросов
BAD_FIELD_ERROR = 100  # API не знает какое-то поле

MEDIA_FIELDS = ("id,caption,media_type,media_product_type,media_url,thumbnail_url,"
                "permalink,timestamp,children{media_type,media_url}")
MEDIA_FIELDS_MIN = "id,caption,media_type,media_url,permalink,timestamp"
_media_fields = MEDIA_FIELDS


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------- .env ----------

def read_env() -> dict:
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    return values


def write_env(updates: dict) -> None:
    """Меняет или дописывает строки KEY=value, остальное в .env не трогает."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    left = dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in left and not line.strip().startswith("#"):
            lines[i] = f"{key}={left.pop(key)}"
    lines += [f"{key}={value}" for key, value in left.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_configured() -> bool:
    env = read_env()
    return bool(env.get("IG_ACCESS_TOKEN") and env.get("IG_USER_ID"))


# ---------- запросы ----------

def api_get(path: str, **params) -> dict:
    version = read_env().get("IG_GRAPH_VERSION", "")  # пусто = версия приложения по умолчанию
    url = "/".join(part for part in (GRAPH_URL, version, path) if part)
    try:
        data = requests.get(url, params=params, timeout=TIMEOUT).json()
    except (requests.RequestException, ValueError) as error:
        # Текст ошибки requests содержит адрес с токеном, в лог его не пишем
        raise ApiError(0, f"нет связи с Instagram API ({type(error).__name__})")
    if "error" in data:
        error = data["error"]
        raise ApiError(error.get("code", 0), error.get("error_user_msg") or error.get("message", ""))
    return data


def fetch_media(account: str, limit: int, env: dict) -> list[dict]:
    global _media_fields
    while True:
        query = f"business_discovery.username({account}){{media.limit({limit}){{{_media_fields}}}}}"
        try:
            data = api_get(env["IG_USER_ID"], fields=query, access_token=env["IG_ACCESS_TOKEN"])
            return data["business_discovery"].get("media", {}).get("data", [])
        except ApiError as error:
            if error.code == BAD_FIELD_ERROR and _media_fields != MEDIA_FIELDS_MIN:
                _media_fields = MEDIA_FIELDS_MIN  # пробуем с коротким набором полей
                continue
            raise


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pick_image(media: dict) -> str | None:
    """Ссылка на картинку поста: у видео превью, у карусели первая картинка."""
    if media.get("media_type") == "VIDEO":
        return media.get("thumbnail_url")
    if media.get("media_type") == "CAROUSEL_ALBUM":
        for child in media.get("children", {}).get("data", []):
            if child.get("media_type") == "IMAGE" and child.get("media_url"):
                return child["media_url"]
    return media.get("media_url")


def to_post(media: dict, account: str) -> dict:
    """Запись в том же виде, что делает gallery-dl в download.py."""
    shortcode = media["permalink"].rstrip("/").split("/")[-1]
    date = datetime.strptime(media["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)
    if media.get("media_product_type") == "REELS" or media.get("media_type") == "VIDEO":
        kind = "reel"
    elif media.get("media_type") == "CAROUSEL_ALBUM":
        kind = "carousel"
    else:
        kind = "photo"
    image_url = pick_image(media)
    return {
        "account": account,
        "shortcode": shortcode,
        "url": media["permalink"],
        "date": date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "downloaded_at": now_iso(),
        "type": kind,
        "description": media.get("caption") or "",
        "image_url": image_url,
        "image": f"data/{account}/images/{shortcode}.jpg" if image_url else None,
    }


def fetch_posts(account: str, limit: int) -> tuple[list[dict], str, bool]:
    """Возвращает (посты, текст ошибки, остановить ли весь прогон).

    Остановить: токен не работает или кончился лимит запросов, дальше пробовать бессмысленно.
    """
    try:
        media = fetch_media(account, limit, read_env())
    except ApiError as error:
        stop = error.code == TOKEN_ERROR or error.code in LIMIT_ERRORS
        return [], f"[{error.code}] {error.message}"[:200], stop
    return [to_post(item, account) for item in media], "", False


# ---------- токен ----------

def days_left() -> int | None:
    expires = read_env().get("IG_TOKEN_EXPIRES")
    if not expires:
        return None
    return (datetime.fromisoformat(expires).date() - datetime.now().date()).days


def exchange_token(app_id: str, app_secret: str, token: str) -> tuple[str, str]:
    """Меняет токен на длинный. Возвращает (токен, день окончания)."""
    data = api_get("oauth/access_token", grant_type="fb_exchange_token",
                   client_id=app_id, client_secret=app_secret, fb_exchange_token=token)
    seconds = data.get("expires_in") or TOKEN_DAYS * 86400
    expires = (datetime.now() + timedelta(seconds=seconds)).date().isoformat()
    return data["access_token"], expires


def refresh() -> bool:
    env = read_env()
    try:
        token, expires = exchange_token(env["IG_APP_ID"], env["IG_APP_SECRET"], env["IG_ACCESS_TOKEN"])
    except KeyError:
        print("В .env нет IG_APP_ID, IG_APP_SECRET или IG_ACCESS_TOKEN. Запустите: python ig_api.py setup")
        return False
    except ApiError as error:
        print(f"Не удалось продлить токен: [{error.code}] {error.message}")
        print("Получите новый токен и запустите: python ig_api.py setup")
        return False
    write_env({"IG_ACCESS_TOKEN": token, "IG_TOKEN_EXPIRES": expires})
    print(f"Токен продлён до {expires}")
    return True


def refresh_if_needed() -> None:
    left = days_left()
    if left is not None and left < REFRESH_DAYS:
        print(f"Токену осталось {left} дн., продлеваю...")
        refresh()


def setup() -> None:
    print("Настройка Instagram API. Всё берётся на developers.facebook.com, значения сохранятся в .env\n")
    env = read_env()
    app_id = input(f"App ID [{env.get('IG_APP_ID', '')}]: ").strip() or env.get("IG_APP_ID", "")
    app_secret = input("App Secret (Enter, если уже сохранён): ").strip() or env.get("IG_APP_SECRET", "")
    short_token = input("Токен из Graph API Explorer: ").strip()
    if not (app_id and app_secret and short_token):
        sys.exit("Нужны все три значения.")
    try:
        token, expires = exchange_token(app_id, app_secret, short_token)
        pages = api_get("me/accounts", fields="name,instagram_business_account{id,username}",
                        access_token=token).get("data", [])
    except ApiError as error:
        sys.exit(f"Ошибка: [{error.code}] {error.message}")
    linked = [page for page in pages if page.get("instagram_business_account")]
    if not linked:
        # Токен рабочий, сохраняем его и ключи приложения, чтобы не вводить заново
        write_env({"IG_APP_ID": app_id, "IG_APP_SECRET": app_secret})
        print("\nНе нашёл Instagram аккаунт, привязанный к странице Facebook. Что видит токен:")
        try:
            granted = api_get("me/permissions", access_token=token).get("data", [])
            print("  разрешения: " + ", ".join(
                f"{item['permission']}" + ("" if item.get("status") == "granted" else " (ОТКЛОНЕНО)")
                for item in granted))
        except ApiError as error:
            print(f"  разрешения узнать не удалось: [{error.code}] {error.message}")
        if pages:
            print("  страницы: " + ", ".join(f"«{page['name']}» (Instagram не привязан)" for page in pages))
            print("Страница есть, но Instagram к ней не привязан или не отмечен в окне входа Facebook.")
        else:
            print("  страницы: ни одной")
            print("Токен не видит страницу: отметьте business_management и pages_show_list, а в окне "
                  "входа Facebook выберите страницу и аккаунт Instagram.")
        sys.exit(1)
    for n, page in enumerate(linked, start=1):
        print(f"  {n}. @{page['instagram_business_account'].get('username')} (страница «{page['name']}»)")
    choice = 1 if len(linked) == 1 else int(input("Номер аккаунта: "))
    ig_account = linked[choice - 1]["instagram_business_account"]
    write_env({"IG_APP_ID": app_id, "IG_APP_SECRET": app_secret, "IG_ACCESS_TOKEN": token,
               "IG_USER_ID": ig_account["id"], "IG_TOKEN_EXPIRES": expires})
    print(f"\nГотово: запросы идут от @{ig_account.get('username')}, токен годен до {expires}.")
    print("Проверка: python ig_api.py test auto_sale_abdulloh")


def test(account: str) -> None:
    if not is_configured():
        sys.exit("API не настроен. Запустите: python ig_api.py setup")
    posts, error, _ = fetch_posts(clean_name(account), 5)
    if error:
        sys.exit(f"Ошибка: {error}")
    print(f"@{account}: получено постов: {len(posts)}")
    for post in posts:
        text = post["description"].replace("\n", " ")[:70]
        print(f"  {post['date'][:10]} {post['type']:8} {'фото' if post['image_url'] else 'без фото':8} {text}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "setup":
        setup()
    elif command == "test":
        test(sys.argv[2] if len(sys.argv) > 2 else "auto_sale_abdulloh")
    elif command == "refresh":
        refresh()
    else:
        left = days_left()
        print("API настроен" if is_configured() else "API не настроен: python ig_api.py setup")
        if left is not None:
            print(f"Токену осталось {left} дн.")
