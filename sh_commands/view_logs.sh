#!/bin/bash

# Работаем из директории проекта (теперь /root/nova)
cd /root/nova || { echo "❌ Не удалось перейти в /root/nova"; exit 1; }

echo "🪵 Просмотр логов Docker сервисов Nova Bot"
echo "========================================="
echo "1) app   — основное приложение"
echo "2) db    — база данных"
echo "3) nginx — веб-сервер"
echo "4) all   — все сервисы"

read -p "Введите номер (1-4): " choice

case $choice in
    1) docker compose logs -f app ;;
    2) docker compose logs -f db ;;
    3) docker compose logs -f nginx ;;
    4) docker compose logs -f ;;
    *) echo "⚠️  Неверный выбор" ;;
esac
