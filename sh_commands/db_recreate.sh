# Остановить контейнер
docker compose down

# Удалить volume с данными PostgreSQL (очистка под 0)
docker volume rm имя_volume
# или если в compose используется volume postgres_data:
docker volume rm $(docker volume ls -q | grep postgres_data)

# Удалить volume с данными Redis (полная очистка кэша)
docker volume rm $(docker volume ls -q | grep redis_data)

# Перезапустить всё заново
docker compose up -d
