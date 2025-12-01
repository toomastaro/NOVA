#!/bin/bash

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Простая проверка доступности команд без рекурсии
DOCKER_COMPOSE_CMD="docker compose"

if [ "$DOCKER_COMPOSE_CMD" = "ERROR" ]; then
    echo -e "${RED}❌ Docker Compose не найден${NC}"
    exit 1
fi

echo -e "${YELLOW}🤖 Статус Nova Bot (используем: $DOCKER_COMPOSE_CMD)${NC}"
echo "=================================================="

# Переходим в директорию проекта
cd /root/nova

# Статус контейнера
echo -e "${YELLOW}📦 Контейнер app:${NC}"
$DOCKER_COMPOSE_CMD ps app

# Использование ресурсов
echo -e "\n${YELLOW}💾 Использование ресурсов:${NC}"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep app || echo "Контейнер app не найден"

# Healthcheck
echo -e "\n${YELLOW}🏥 Healthcheck:${NC}"
if curl -s -f http://localhost:8099/health > /dev/null; then
    echo -e "${GREEN}✅ Приложение доступно${NC}"
else
    echo -e "${RED}❌ Приложение недоступно${NC}"
fi

# Последние логи
echo -e "\n${YELLOW}📋 Последние логи (10 строк):${NC}"
$DOCKER_COMPOSE_CMD logs --tail=10 app
