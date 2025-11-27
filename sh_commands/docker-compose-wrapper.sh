#!/bin/bash
# Обертка для Docker Compose команд

if command -v docker-compose &> /dev/null; then
    docker-compose "$@"
elif docker compose version &> /dev/null; then
    docker compose "$@"
else
    echo "❌ Docker Compose не найден!"
    echo "Попробуйте установить docker-compose или проверьте установку Docker"
    exit 1
fi
