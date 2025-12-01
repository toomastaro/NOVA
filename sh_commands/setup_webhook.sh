#!/bin/bash
set -Eeuo pipefail

# Работаем из директории проекта (теперь /root/nova)
cd /root/nova || { echo "❌ Не найден каталог /root/nova"; exit 1; }

# Получаем токен из .env (берём первую строку BOT_TOKEN=..., убираем кавычки и пробелы)
if [[ -f .env ]]; then
  BOT_TOKEN=$(grep -m1 '^BOT_TOKEN=' .env | cut -d '=' -f2- | tr -d "\"'[:space:]\r")
else
  echo "❌ Файл .env не найден в /root/nova"
  exit 1
fi

if [[ -z "${BOT_TOKEN:-}" ]]; then
    echo "❌ BOT_TOKEN не найден в .env файле"
    exit 1
fi

echo "🔗 Настройка webhook для бота..."

# Удаляем старый webhook
echo "🗑️ Удаление старого webhook..."
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true" >/dev/null || true

# Устанавливаем новый webhook
echo "📡 Установка нового webhook..."
RESPONSE=$(curl -s -F "url=https://bot.nova.tg/webhook/main" "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook")
echo "Ответ: $RESPONSE"

# Проверяем статус webhook
echo "🔍 Проверка статуса webhook..."
if command -v jq >/dev/null 2>&1; then
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq .
else
  echo "ℹ️ jq не установлен, показываю сырой вывод:"
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
  echo
fi

echo "✅ Настройка webhook завершена!"
