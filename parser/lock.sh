# Общая «табличка занято» для run_daily.sh и run_video.sh. Подключается через source.
# take_lock ИМЯ: занять, если свободно. Внутри папки замка лежит pid владельца:
# если этого процесса уже нет (Мак перезагрузили, прогон убили), замок считается брошенным и снимается сам.
# need_space ГБ: хватает ли свободного места на диске Мака. Если нет: строка в лог, уведомление macOS и код 1.
# Нужна, чтобы прогон останавливался заранее с понятным сообщением, а не падал посередине (как 18.11.2026).
# Вызывать после того, как задана переменная LOG.
need_space() {
    local need_gb="$1" free_kb free_gb text
    free_kb="$(df -k "$PWD" | awk 'NR==2 {print $4}')"
    free_gb=$(( ${free_kb:-0} / 1024 / 1024 ))
    if [ "$free_gb" -lt "$need_gb" ]; then
        text="Прогон остановлен: на диске свободно ${free_gb} ГБ, нужно не меньше ${need_gb} ГБ. Освободите место и запустите снова"
        echo "$(date '+%d.%m.%Y %H:%M') $text" | tee -a "$LOG"
        osascript -e "display notification \"$text\" with title \"uz-avto: мало места\"" 2>/dev/null || true
        return 1
    fi
}

take_lock() {
    local dir="data/.$1.lock"
    if ! mkdir "$dir" 2>/dev/null; then
        local pid
        pid="$(cat "$dir/pid" 2>/dev/null)"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 1  # владелец жив: идёт настоящий прогон
        fi
        rm -f "$dir/pid"; rmdir "$dir" 2>/dev/null
        mkdir "$dir" 2>/dev/null || return 1
    fi
    echo $$ > "$dir/pid"
    LOCK_DIR="$dir"
    trap 'rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR"' EXIT
}
