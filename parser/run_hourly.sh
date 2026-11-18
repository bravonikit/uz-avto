#!/bin/bash
# Часовой прогон: только свежие посты Telegram за сутки → разбор → сайт. Занимает несколько минут.
# Нужен, чтобы новая машина появлялась на сайте в течение часа (пик выкладки с 14 до 23).
# Правки, «продано» и удаления за 14 и 90 дней, Instagram, архив делает ежедневный run_daily.sh.
# Замок общий с run_daily.sh: пока идёт ежедневный, часовой пропускается.
# macOS запускает каждый час в :07 (install_schedule.sh). Лог: data/logs/hourly-ГГГГ-ММ-ДД.log

PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PARSER_DIR" || exit 1
source ./lock.sh

mkdir -p data/logs
LOG="data/logs/hourly-$(date +%Y-%m-%d).log"

if ! take_lock daily; then
    echo "$(date '+%H:%M') идёт ежедневный прогон, пропускаю" >> "$LOG"
    exit 0
fi

PYTHON="$PARSER_DIR/.venv/bin/python"
export PYTHONUNBUFFERED=1
{
    echo "===== $(date '+%d.%m.%Y %H:%M') часовой ====="
    caffeinate -i "$PYTHON" tg_download.py --quick | grep --line-buffered -E "готово|ошибка"
    "$PYTHON" tg_parse.py | tail -4
    if ! pgrep -f "tg_video.py" >/dev/null; then
        caffeinate -i "$PYTHON" tg_video.py --only download --light-only --days 2 | grep "^Видео"
    fi
    "$PYTHON" export_to_site.py | grep -E "^Выгружено"
    echo "===== $(date '+%H:%M') конец"
} 2>&1 | tee -a "$LOG"
