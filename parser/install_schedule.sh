#!/bin/bash
# Включает ежедневный автозапуск парсера (один раз). Выключить: ./install_schedule.sh off
# Время запуска: HOUR:MINUTE ниже. Если Мак в это время спал, macOS запустит прогон, когда он проснётся.

HOUR=12
MINUTE=37

LABEL="com.bravonikit.uzavto.parser"
PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "off" ]; then
    launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null
    rm -f "$PLIST"
    echo "Автозапуск выключен."
    exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$PARSER_DIR/data/logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PARSER_DIR/run_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PARSER_DIR/data/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$PARSER_DIR/data/logs/launchd.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" && \
    echo "Готово: парсер будет запускаться каждый день в $HOUR:$MINUTE." && \
    echo "Проверить: launchctl print gui/$(id -u)/$LABEL | grep state" && \
    echo "Запустить прямо сейчас через расписание: launchctl kickstart gui/$(id -u)/$LABEL"
