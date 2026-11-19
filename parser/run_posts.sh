#!/bin/bash
# Автопостинг аналитики дня в Telegram канал: один пост за запуск (post_daily.py).
# macOS запускает три раза в день (install_schedule.sh). Лог: data/logs/posts-ГГГГ-ММ-ДД.log
# Выключить: touch data/posts.off

PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PARSER_DIR" || exit 1
source ./lock.sh

mkdir -p data/logs
LOG="data/logs/posts-$(date +%Y-%m-%d).log"
take_lock posts || exit 0

# launchd запускает с коротким PATH: добавляем обычные места Node.js (Homebrew, nvm)
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then source "$HOME/.nvm/nvm.sh" >/dev/null 2>&1; fi
export PYTHONUNBUFFERED=1
{
    echo "===== $(date '+%d.%m.%Y %H:%M') посты: старт ====="
    caffeinate -i "$PARSER_DIR/.venv/bin/python" post_daily.py "$@"
    echo "===== $(date '+%d.%m.%Y %H:%M') посты: конец ====="
} 2>&1 | tee -a "$LOG"
