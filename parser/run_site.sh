#!/bin/bash
# Держит сайт запущенным (npm run dev, http://localhost:3000): launchd поднимает его снова, если он упал
# или Мак перезагрузился. Если сайт уже запущен вручную в терминале, ничего не делаем и проверяем позже.
PARSER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PARSER_DIR/.." || exit 1
if lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
    sleep 600
    exit 0
fi
echo "$(date '+%d.%m.%Y %H:%M') запускаю сайт"
exec npm run dev
