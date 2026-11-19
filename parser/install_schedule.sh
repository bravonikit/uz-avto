#!/bin/bash
# Включает автозапуск парсера (один раз). Выключить: ./install_schedule.sh off
# Два задания macOS:
#   1) run_daily.sh каждый день в HOUR:MINUTE: посты, разбор, сайт. Если Мак в это время спал,
#      macOS запустит прогон, когда он проснётся.
#   2) run_hourly.sh каждый час в :HOURLY_MINUTE: свежие посты за сутки и сайт.
#   3) run_video.sh каждые VIDEO_EVERY_MIN минут: видео, раскадровка, кадры. Если прошлый ещё идёт,
#      новый сразу выходит, так что работа просто продолжается.
#   4) run_posts.sh в POST_TIMES: по одному посту аналитики дня в Telegram канал (post_daily.py).

# Полный прогон (перечитывание 90 дней, «продано», смены цен) ночью: днём новые посты идут часовым прогоном
HOUR=3
MINUTE=37
COLLECT_EVERY_MIN=15  # ответы очереди Google по карточкам
VIDEO_EVERY_MIN=120
HOURLY_MINUTE=7
POST_TIMES="10:05 14:05 19:05 21:35"  # три поста в день (ниже рынка, самые красивые, подборка) и страховочный запуск

LABEL="com.bravonikit.uzavto.parser"
VIDEO_LABEL="com.bravonikit.uzavto.video"
HOURLY_LABEL="com.bravonikit.uzavto.hourly"
POSTS_LABEL="com.bravonikit.uzavto.posts"
COLLECT_LABEL="com.bravonikit.uzavto.collect"
WATCH_LABEL="com.bravonikit.uzavto.watchdog"
MORNING_LABEL="com.bravonikit.uzavto.morning"
SITE_LABEL="com.bravonikit.uzavto.site"
WATCH_MINUTE=45         # сторож каждый час (watchdog.py): тревоги в Telegram бот
MORNING_TIME="9:12"     # утренняя сводка за сутки
PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
VIDEO_PLIST="$HOME/Library/LaunchAgents/$VIDEO_LABEL.plist"
HOURLY_PLIST="$HOME/Library/LaunchAgents/$HOURLY_LABEL.plist"
POSTS_PLIST="$HOME/Library/LaunchAgents/$POSTS_LABEL.plist"
COLLECT_PLIST="$HOME/Library/LaunchAgents/$COLLECT_LABEL.plist"
WATCH_PLIST="$HOME/Library/LaunchAgents/$WATCH_LABEL.plist"
MORNING_PLIST="$HOME/Library/LaunchAgents/$MORNING_LABEL.plist"
SITE_PLIST="$HOME/Library/LaunchAgents/$SITE_LABEL.plist"

if [ "$1" = "off" ]; then
    for p in "$PLIST" "$VIDEO_PLIST" "$HOURLY_PLIST" "$POSTS_PLIST" "$COLLECT_PLIST" "$WATCH_PLIST" "$MORNING_PLIST" "$SITE_PLIST"; do
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

cat > "$HOURLY_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$HOURLY_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PARSER_DIR/run_hourly.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Minute</key>
        <integer>$HOURLY_MINUTE</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PARSER_DIR/data/logs/launchd-hourly.log</string>
    <key>StandardErrorPath</key>
    <string>$PARSER_DIR/data/logs/launchd-hourly.log</string>
</dict>
</plist>
PLIST

cat > "$COLLECT_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$COLLECT_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PARSER_DIR/run_collect.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>$((COLLECT_EVERY_MIN * 60))</integer>
    <key>StandardOutPath</key>
    <string>$PARSER_DIR/data/logs/launchd-collect.log</string>
    <key>StandardErrorPath</key>
    <string>$PARSER_DIR/data/logs/launchd-collect.log</string>
</dict>
</plist>
PLIST

cat > "$WATCH_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$WATCH_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PARSER_DIR/.venv/bin/python</string>
        <string>$PARSER_DIR/watchdog.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PARSER_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Minute</key>
        <integer>$WATCH_MINUTE</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PARSER_DIR/data/logs/launchd-watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>$PARSER_DIR/data/logs/launchd-watchdog.log</string>
</dict>
</plist>
PLIST

cat > "$MORNING_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$MORNING_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PARSER_DIR/.venv/bin/python</string>
        <string>$PARSER_DIR/watchdog.py</string>
        <string>--morning</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PARSER_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${MORNING_TIME%%:*}</integer>
        <key>Minute</key>
        <integer>${MORNING_TIME##*:}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PARSER_DIR/data/logs/launchd-watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>$PARSER_DIR/data/logs/launchd-watchdog.log</string>
</dict>
</plist>
PLIST

# launchd запускает с коротким PATH и не видит Node.js: запоминаем, где он у вас сейчас
NODE_DIR="$(dirname "$(command -v node 2>/dev/null || echo /opt/homebrew/bin/node)")"
POST_INTERVALS=""
for t in $POST_TIMES; do
    POST_INTERVALS="$POST_INTERVALS        <dict><key>Hour</key><integer>$((10#${t%%:*}))</integer><key>Minute</key><integer>$((10#${t##*:}))</integer></dict>
"
done
cat > "$SITE_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$SITE_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PARSER_DIR/run_site.sh</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$NODE_DIR:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>60</integer>
    <key>StandardOutPath</key>
    <string>$PARSER_DIR/data/logs/launchd-site.log</string>
    <key>StandardErrorPath</key>
    <string>$PARSER_DIR/data/logs/launchd-site.log</string>
</dict>
</plist>
PLIST

cat > "$POSTS_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$POSTS_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PARSER_DIR/run_posts.sh</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$NODE_DIR:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>StartCalendarInterval</key>
    <array>
$POST_INTERVALS    </array>
    <key>StandardOutPath</key>
    <string>$PARSER_DIR/data/logs/launchd-posts.log</string>
    <key>StandardErrorPath</key>
    <string>$PARSER_DIR/data/logs/launchd-posts.log</string>
</dict>
</plist>
PLIST

for p in "$PLIST" "$VIDEO_PLIST" "$HOURLY_PLIST" "$POSTS_PLIST" "$COLLECT_PLIST" "$WATCH_PLIST" "$MORNING_PLIST" "$SITE_PLIST"; do
    launchctl bootout "gui/$(id -u)" "$p" 2>/dev/null
    launchctl bootstrap "gui/$(id -u)" "$p" || { echo "Не получилось включить $p"; exit 1; }
done
echo "Готово: полный прогон каждый день в $HOUR:$MINUTE, свежие посты и сайт каждый час в :$HOURLY_MINUTE, видео каждые $VIDEO_EVERY_MIN мин., посты в канал в $POST_TIMES, ответы по карточкам каждые $COLLECT_EVERY_MIN мин., сторож каждый час в :$WATCH_MINUTE, утренняя сводка в $MORNING_TIME, сайт поднимается сам."
echo "Проверить: launchctl print gui/$(id -u)/$LABEL | grep state"
echo "Запустить прямо сейчас: launchctl kickstart gui/$(id -u)/$LABEL  (видео: .../$VIDEO_LABEL)"
