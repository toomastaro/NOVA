#!/bin/bash

echo "🧪 Тестирование Docker команд..."

# Работаем из директории проекта (теперь /root/nova)
cd /root/nova || { echo "❌ Не удалось перейти в /root/nova"; exit 1; }

echo "1️⃣ Проверка docker:"
docker --version || echo "❌ docker не найден"

echo "2️⃣ Проверка docker-compose:"
docker-compose --version 2>/dev/null || echo "⚠️ docker-compose (classic) не найден"

echo "3️⃣ Проверка docker compose (plugin):"
docker compose version 2>/dev/null || echo "⚠️ docker compose plugin не найден"

echo "4️⃣ Текущая директория:"
pwd

echo "5️⃣ Статус контейнеров:"
if command -v docker-compose &> /dev/null; then
    docker-compose ps
else
    docker compose ps
fi

echo "✅ Тестирование завершено!"
