#!/bin/bash
# Включает автозапуск парсера (один раз). Выключить: ./install_schedule.sh off
# Два задания macOS:
#   1) run_daily.sh каждый день в HOUR:MINUTE: посты, разбор, сайт. Если Мак в это время спал,
#      macOS запустит прогон, когда он проснётся.
#   2) run_video.sh каждые VIDEO_EVERY_MIN минут: видео, раскадровка, кадры. Если прошлый ещё идёт,
#      новый сразу выходит, так что работа просто продолжается.

HOUR=12
MINUTE=37
VIDEO_EVERY_MIN=120

LABEL="com.bravonikit.uzavto.parser"
VIDEO_LABEL="com.bravonikit.uzavto.video"
PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
VIDEO_PLIST="$HOME/Library/LaunchAgents/$VIDEO_LABEL.plist"

if [ "$1" = "off" ]; then
    for p in "$PLIST" "$VIDEO_PLIST"; do
        launchctl bootout "gui/$(id -u)" "$p" 2>/dev/null
        rm -f "$p"
    done
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

cat > "$VIDEO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$VIDEO_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PARSER_DIR/run_video.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>$((VIDEO_EVERY_MIN * 60))</integer>
    <key>StandardOutPath</key>
    <string>$PARSER_DIR/data/logs/launchd-video.log</string>
    <key>StandardErrorPath</key>
    <string>$PARSER_DIR/data/logs/launchd-video.log</string>
</dict>
</plist>
PLIST

for p in "$PLIST" "$VIDEO_PLIST"; do
    launchctl bootout "gui/$(id -u)" "$p" 2>/dev/null
    launchctl bootstrap "gui/$(id -u)" "$p" || { echo "Не получилось включить $p"; exit 1; }
done
echo "Готово: посты и сайт каждый день в $HOUR:$MINUTE, видео каждые $VIDEO_EVERY_MIN мин."
echo "Проверить: launchctl print gui/$(id -u)/$LABEL | grep state"
echo "Запустить прямо сейчас: launchctl kickstart gui/$(id -u)/$LABEL  (видео: .../$VIDEO_LABEL)"
