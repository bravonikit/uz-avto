# Общая «табличка занято» для run_daily.sh и run_video.sh. Подключается через source.
# take_lock ИМЯ: занять, если свободно. Внутри папки замка лежит pid владельца:
# если этого процесса уже нет (Мак перезагрузили, прогон убили), замок считается брошенным и снимается сам.
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
