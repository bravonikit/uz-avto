#!/bin/bash
# Каждые 15 минут: забрать ответы очереди Google по карточкам (обложки, сетки) и сразу выложить на сайт.
# Пусто в очереди: выходит за секунду, к Google не обращается. Лог: data/logs/collect-ГГГГ-ММ-ДД.log
PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PARSER_DIR" || exit 1
[ -f data/cards.on ] || exit 0
grep -qs '"collected": false' data/_cards/*/state.json || exit 0
mkdir -p data/logs
LOG="data/logs/collect-$(date +%Y-%m-%d).log"
export PYTHONUNBUFFERED=1
{
    echo "===== $(date '+%d.%m.%Y %H:%M') ответы очереди"
    "$PARSER_DIR/.venv/bin/python" cards_daily.py collect | grep -E "^Карточки|^Сайт|пакет|Диск не принял|ошибка"
} >> "$LOG" 2>&1
