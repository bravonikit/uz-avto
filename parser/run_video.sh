#!/bin/bash
# Видеопрогон, отдельно от ежедневного: тяжёлые видео через аккаунт Telegram, раскадровка и звук,
# лучшие кадры (перед 3/4, бок, зад, салон). Может идти часами и не мешает обновлению сайта.
# macOS запускает его каждые 2 часа (install_schedule.sh). Если прошлый ещё идёт, новый сразу выходит,
# поэтому после сна Мака или обрыва сети работа просто продолжается со следующего запуска.
# Всё скачанное не качается повторно, недокачанное лежит как .part и перекачивается.
# Лог: data/logs/video-ГГГГ-ММ-ДД.log

PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PARSER_DIR" || exit 1
source ./lock.sh

mkdir -p data/logs
LOG="data/logs/video-$(date +%Y-%m-%d).log"

take_lock video || exit 0
# Старый общий прогон (до разделения) ещё качает видео: не мешаем ему
if pgrep -f "tg_video.py|video_frames.py" >/dev/null; then
    echo "$(date '+%H:%M') видео уже качает другой процесс, выхожу" >> "$LOG"
    exit 0
fi

# Ролики пишутся на Google Диск, но сначала ложатся на диск Мака и ждут выгрузки: нужен запас
need_space 8 || exit 0

PYTHON="$PARSER_DIR/.venv/bin/python"
export PYTHONUNBUFFERED=1
{
    echo "===== $(date '+%d.%m.%Y %H:%M') видео: старт ====="
    caffeinate -i "$PYTHON" tg_video.py --only download
    caffeinate -i "$PYTHON" tg_video.py --only cut
    caffeinate -i "$PYTHON" video_frames.py --all --limit 300 | grep --line-buffered -E "^Видео|^Готово|ошибка"
    echo "===== $(date '+%d.%m.%Y %H:%M') видео: конец ====="
    echo
} 2>&1 | grep --line-buffered -vE "^Attempt [0-9]+ at connecting|Security error while unpacking|very old message" | tee -a "$LOG"
# Итог видеопрогона в Telegram бот без звука (выключить: TG_VIDEO=0)
"$PYTHON" tg_bot.py videorun "$LOG" >/dev/null 2>&1 || true
