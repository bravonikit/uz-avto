#!/bin/bash
# Полный прогон парсера: скачать новые посты → найти цены → выгрузить на сайт → показать статус.
# Запуск вручную:  ./run_daily.sh
# Каждый день его запускает macOS сама (см. install_schedule.sh).
# Лог каждого дня: data/logs/ГГГГ-ММ-ДД.log

PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PARSER_DIR" || exit 1

mkdir -p data/logs
LOG="data/logs/$(date +%Y-%m-%d).log"
LOCK="data/.run.lock"

# Не запускать второй раз, если предыдущий прогон ещё идёт
if ! mkdir "$LOCK" 2>/dev/null; then
    echo "$(date '+%H:%M') прогон уже идёт, выхожу" | tee -a "$LOG"
    exit 0
fi
trap 'rmdir "$LOCK"' EXIT

PYTHON="$PARSER_DIR/.venv/bin/python"
# Без этого Python копит вывод и лог заполняется только в конце прогона
export PYTHONUNBUFFERED=1
STARTED="$(date '+%d.%m.%Y %H:%M')"
# Кто запустил: launchd (автозапуск) или человек из терминала
if [ -t 1 ]; then HOW="вручную"; else HOW="авто"; fi
{
    echo "===== $STARTED старт ($HOW) ====="
    # caffeinate не даёт Маку уснуть, пока идёт скачивание
    caffeinate -i "$PYTHON" download.py \
        && "$PYTHON" extract_price.py \
        && "$PYTHON" export_to_site.py
    echo
    "$PYTHON" status.py
    echo "===== $(date '+%d.%m.%Y %H:%M') конец ====="
    echo
} 2>&1 | tee -a "$LOG"

# Итог одной строкой: в журнал запусков и в уведомление macOS, чтобы автозапуск было видно
SUMMARY="$(grep -E 'Готово:|Прогон остановлен' "$LOG" | tail -1)"
[ -z "$SUMMARY" ] && SUMMARY="прогон не дошёл до конца, смотрите $LOG"
echo "$STARTED - $(date '+%H:%M') | $HOW | $SUMMARY" >> data/logs/history.txt
osascript -e "display notification \"$SUMMARY\" with title \"uz-avto: парсер ($HOW)\"" 2>/dev/null || true
