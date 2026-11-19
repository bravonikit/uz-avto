#!/bin/bash
# Ежедневный прогон: скачать новые посты Instagram и Telegram → разобрать → выгрузить на сайт → статус.
# Тяжёлое (видео целиком через аккаунт, раскадровка, кадры) сюда не входит: это run_video.sh,
# он идёт отдельно и не держит обновление сайта.
# Запуск вручную:  ./run_daily.sh
# Каждый день его запускает macOS сама (см. install_schedule.sh).
# Лог каждого дня: data/logs/ГГГГ-ММ-ДД.log

PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PARSER_DIR" || exit 1
source ./lock.sh

mkdir -p data/logs
LOG="data/logs/$(date +%Y-%m-%d).log"

# Не запускать второй раз, если предыдущий прогон ещё идёт
if ! take_lock daily; then
    echo "$(date '+%H:%M') прогон уже идёт, выхожу" | tee -a "$LOG"
    exit 0
fi

# Меньше 5 ГБ свободно: не начинаем, иначе прогон упадёт посередине
if ! need_space 5; then
    echo "$(date '+%d.%m.%Y %H:%M') | мало места | Прогон остановлен: на диске меньше 5 ГБ" >> data/logs/history.txt
    exit 0
fi

PYTHON="$PARSER_DIR/.venv/bin/python"
# Без этого Python копит вывод и лог заполняется только в конце прогона
export PYTHONUNBUFFERED=1
STARTED="$(date '+%d.%m.%Y %H:%M')"
# Кто запустил: launchd (автозапуск) или человек из терминала
if [ -t 1 ]; then HOW="вручную"; else HOW="авто"; fi
# Этап закончился: короткое сообщение в Telegram бот без звука (tg_bot.py). Бот не настроен: ничего
notify_stage() { "$PYTHON" tg_bot.py stage "$1" --log "$LOG" >/dev/null 2>&1 || true; }
{
    echo "===== $STARTED старт ($HOW) ====="
    # caffeinate не даёт Маку уснуть, пока идёт скачивание
    # Instagram: если скачать не вышло (нет входа, API закрыт), разбор старых постов всё равно не трогаем
    caffeinate -i "$PYTHON" download.py \
        && "$PYTHON" extract_price.py \
        && "$PYTHON" enrich.py
    echo
    # Telegram качается и разбирается отдельно: работает, даже когда Instagram недоступен
    caffeinate -i "$PYTHON" tg_download.py
    notify_stage raw
    "$PYTHON" tg_parse.py | tail -4
    notify_stage parse
    # Лёгкие видео и кружки сразу, пока ссылки со страницы свежие (через пару часов они протухают).
    # Без аккаунта Telegram, быстро. Тяжёлые и раскадровку делает run_video.sh
    # Если видеопрогон сейчас идёт, он сам скачает и лёгкие: два процесса на одни файлы не пускаем
    if pgrep -f "tg_video.py" >/dev/null; then
        echo "Видео: лёгкие скачает идущий видеопрогон"
    else
        caffeinate -i "$PYTHON" tg_video.py --only download --light-only | grep "^Видео"
    fi
    notify_stage video
    echo
    # Цена из голоса и с фото (price_fill.py): забираем готовые ответы Gemini до сборки сайта
    if [ -f data/cards.on ]; then
        "$PYTHON" price_fill.py check
    fi
    # Сайт собираем всегда из того, что есть на диске
    "$PYTHON" export_to_site.py | grep -v "^  [A-Za-z0-9_.]*: [0-9]* объявлений$"
    notify_stage site
    echo
    "$PYTHON" status.py
    echo
    # Резервная копия данных и переезд всех фото на Google Диск (на Маке остаются ссылки). Диск не подключён: шаг пропускается
    "$PYTHON" archive.py
    notify_stage archive
    # Обработка карточек за вчера: обложки, фото из видео, описания. Платные шаги идут в очередь Google.
    # Включается файлом data/cards.on (touch data/cards.on), выключается его удалением.
    if [ -f data/cards.on ]; then
        echo
        # Добор за 3 дня: что не успели часовые запуски (ролик скачался поздно, упёрлись в потолок)
        caffeinate -i "$PYTHON" cards_daily.py fresh --days 3
        notify_stage cards
        # Объявления без цены в тексте: спрашиваем Gemini (фото и звук ролика), ответ заберём в следующий прогон
        caffeinate -i "$PYTHON" price_fill.py start --limit 300
    fi
    echo "===== $(date '+%d.%m.%Y %H:%M') конец ====="
    echo
} 2>&1 | tee -a "$LOG"

# Итог одной строкой: в журнал запусков и в уведомление macOS, чтобы автозапуск было видно
SUMMARY="$(grep -E 'Готово:|Прогон остановлен' "$LOG" | tail -1)"
[ -z "$SUMMARY" ] && SUMMARY="прогон не дошёл до конца, смотрите $LOG"
echo "$STARTED - $(date '+%H:%M') | $HOW | $SUMMARY" >> data/logs/history.txt
osascript -e "display notification \"$SUMMARY\" with title \"uz-avto: парсер ($HOW)\"" 2>/dev/null || true
# Итог прогона в Telegram бот: статус и воронка за вчера и за сегодня (python tg_bot.py setup)
"$PYTHON" tg_bot.py report "$LOG" --how "$HOW" --started "$STARTED" >> "$LOG" 2>&1 || true
