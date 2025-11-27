#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Работаем из директории проекта (раньше была /home/adminuser/nova)
cd /root/nova || { echo -e "${RED}❌ Не найден каталог /root/nova${NC}"; exit 1; }

echo -e "${YELLOW}🔍 Мониторинг Nova Bot${NC}"
echo "================================"

# Статус контейнеров
echo -e "${YELLOW}📊 Статус контейнеров:${NC}"
docker compose ps

echo -e "\n${YELLOW}💾 Использование ресурсов:${NC}"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

echo -e "\n${YELLOW}🌐 Сетевое подключение:${NC}"
if curl -s -f http://localhost/health > /dev/null; then
    echo -e "${GREEN}✅ HTTP healthcheck: OK${NC}"
else
    echo -e "${RED}❌ HTTP healthcheck: FAILED${NC}"
fi

if curl -s -f -k https://bot.nova.tg/health > /dev/null; then
    echo -e "${GREEN}✅ HTTPS healthcheck: OK${NC}"
else
    echo -e "${RED}❌ HTTPS healthcheck: FAILED${NC}"
fi

echo -e "\n${YELLOW}📈 Последние события:${NC}"
docker compose logs --tail=5 app | grep -v "INFO"
