#!/bin/bash
set -Eeuo pipefail

# Работаем из директории проекта (теперь /root/bot)
cd /root/bot || { echo "❌ Не удалось перейти в /root/bot"; exit 1; }

# Получаем токен бота из .env
if [[ -f .env ]]; then
  BOT_TOKEN=$(grep -m1 '^BOT_TOKEN=' .env | cut -d '=' -f2- | tr -d "\"'[:space:]\r")
else
  echo "❌ Файл .env не найден в /root/bot"
  exit 1
fi

if [[ -z "${BOT_TOKEN:-}" ]]; then
  echo "❌ BOT_TOKEN не найден в .env"
  exit 1
fi

echo "🔍 Проверка webhook для бота"
echo "Токен: ${BOT_TOKEN:0:10}..."

# Проверяем статус webhook
if command -v jq >/dev/null 2>&1; then
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq .
else
  echo "ℹ️ jq не установлен, показываю сырой вывод:"
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
  echo
fi

echo -e "\n🔍 Проверка информации о боте"
if command -v jq >/dev/null 2>&1; then
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | jq .
else
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe"
  echo
fi
