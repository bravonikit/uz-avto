#!/bin/bash
# Довести сбор до конца без присмотра: дождаться идущего прогона, проверить, все ли каналы Telegram
# прошли обход (посты за 90 дней и все фото альбомов), докачать только недостающие каналы,
# обновить сайт и перенести все фото на Google Диск. Повторяет попытки, пока всё не сойдётся.
# Запуск (в отдельном окне терминала, прогон run_daily.sh при этом может ещё идти):
#   ./run_until_done.sh
# Старые видео (старше 14 дней) не качает: этим занимается run_video.sh и только за свежие дни.
# Лог: data/logs/until-done-ГГГГ-ММ-ДД.log. В конце показывает уведомление macOS с итогом.

PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PARSER_DIR" || exit 1
source ./lock.sh

MAX_ATTEMPTS=6        # сколько раз докачивать недостающие каналы
FRESH_HOURS=30        # канал считается пройденным, если его глубокий обход был не раньше стольких часов назад
PYTHON="$PARSER_DIR/.venv/bin/python"
export PYTHONUNBUFFERED=1
mkdir -p data/logs
LOG="data/logs/until-done-$(date +%Y-%m-%d).log"

# Мак не засыпает, пока жив этот скрипт (при закрытой крышке без питания macOS всё равно уснёт)
caffeinate -dims -w $$ &

say() { echo "$(date '+%H:%M') $*" | tee -a "$LOG"; }

# Каналы из tg_accounts.txt, у которых нет свежего удачного глубокого обхода. Печатает их через пробел.
missing_channels() {
    "$PYTHON" - "$FRESH_HOURS" <<'PY'
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

border = (datetime.now(timezone.utc) - timedelta(hours=int(sys.argv[1]))).strftime("%Y-%m-%dT%H:%M:%SZ")
state_file = Path("data/_tg/state.json")
state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
channels = []
for line in Path("tg_accounts.txt").read_text(encoding="utf-8").splitlines():
    line = line.split("#")[0].strip()
    if line:
        name = line.split()[0].rstrip("/").split("/")[-1].lstrip("@")
        if name not in channels:
            channels.append(name)
missing = [name for name in channels
           if state.get(name, {}).get("status") != "ok" or (state.get(name, {}).get("last_deep") or "") < border]
print(" ".join(missing))
PY
}

# Сколько фото постов ещё лежит на Маке файлом, а не ярлыком на Google Диск
photos_on_mac() {
    find data/_tg -path "*/images/*" -type f 2>/dev/null | wc -l | tr -d " "
}

# Ждём, пока закончится идущий прогон (ежедневный или часовой), и занимаем замок сами
wait_and_lock() {
    local waited=0
    until take_lock daily; do
        [ $((waited % 30)) -eq 0 ] && say "идёт другой прогон, жду (уже $waited мин)"
        sleep 60
        waited=$((waited + 1))
    done
}

say "===== старт: довести сбор до конца ====="
attempt=0
while :; do
    wait_and_lock
    MISSING="$(missing_channels)"
    COUNT=$(echo $MISSING | wc -w | tr -d " ")
    if [ "$COUNT" -eq 0 ]; then
        say "все каналы пройдены"
        break
    fi
    attempt=$((attempt + 1))
    if [ "$attempt" -gt "$MAX_ATTEMPTS" ]; then
        say "после $MAX_ATTEMPTS попыток не пройдены каналы ($COUNT): $MISSING"
        break
    fi
    if ! need_space 5; then
        break
    fi
    say "попытка $attempt из $MAX_ATTEMPTS: докачиваю каналы ($COUNT): $MISSING"
    # shellcheck disable=SC2086
    caffeinate -i "$PYTHON" tg_download.py $MISSING 2>&1 | tee -a "$LOG"
    # Замок отпускаем между попытками: если что то пошло не так, пауза и новая проверка
    rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null
    sleep 120
done

# Разбор и сайт из того, что есть на диске, потом перенос фото на Google Диск
{
    say "разбор постов и выгрузка на сайт"
    "$PYTHON" tg_parse.py | tail -4
    "$PYTHON" export_to_site.py | grep -v "^  [A-Za-z0-9_.]*: [0-9]* объявлений$"
} 2>&1 | tee -a "$LOG"

for round in 1 2 3 4; do
    LEFT="$(photos_on_mac)"
    [ "$LEFT" -eq 0 ] && break
    say "перенос фото на Google Диск, круг $round: на Маке ещё $LEFT"
    "$PYTHON" archive.py 2>&1 | tee -a "$LOG"
    [ "$(photos_on_mac)" -eq 0 ] && break
    sleep 300  # Диск не принял часть файлов: даём ему выгрузить очередь и пробуем снова
done

MISSING="$(missing_channels)"
LEFT="$(photos_on_mac)"
if [ -z "$MISSING" ] && [ "$LEFT" -eq 0 ]; then
    SUMMARY="Готово: все каналы пройдены, все фото на Google Диске"
else
    SUMMARY="Не до конца: не пройдено каналов $(echo $MISSING | wc -w | tr -d ' '), фото на Маке осталось $LEFT"
fi
say "===== конец. $SUMMARY ====="
[ -n "$MISSING" ] && say "не пройдены: $MISSING"
echo "$(date '+%d.%m.%Y %H:%M') | до конца | $SUMMARY" >> data/logs/history.txt
osascript -e "display notification \"$SUMMARY\" with title \"uz-avto: сбор до конца\"" 2>/dev/null || true
