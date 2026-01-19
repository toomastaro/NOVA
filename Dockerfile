# 🐍 Официальный образ Python 3.11
FROM python:3.11-slim

# 🧩 Системные зависимости
RUN apt-get update && apt-get install -y \
  curl \
  && rm -rf /var/lib/apt/lists/*

# 📁 Рабочая директория внутри контейнера
WORKDIR /app

# 🧾 Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 📦 Вспомогательные файлы
COPY wait-for-db.py .
RUN chmod +x wait-for-db.py

# 🧠 Код проекта
COPY . .

# 📶 Открытый порт
EXPOSE 8099

# 🏁 entrypoint — запуск от root (UID/GID по умолчанию 0:0)
RUN cat > entrypoint.sh << 'SCRIPT'
#!/bin/bash
set -Eeuo pipefail

echo "🔄 Starting Nova Bot application..."

# UID/GID можно переопределить через переменные окружения,
# по умолчанию — root (0:0), чтобы не требовались 1000:1000.
APP_UID="${APP_UID:-0}"
APP_GID="${APP_GID:-0}"

# Каталоги, где могут понадобиться права на запись (раскомментируй при необходимости)
DIRS=(
#  /app/main_bot/utils/temp
#  /app/main_bot/utils/sessions
#  /app/logs
#  /app
)

for d in "${DIRS[@]}"; do
mkdir -p "$d"
chown -R "${APP_UID}:${APP_GID}" "$d"
chmod -R g+rwX "$d"
done

# --- Ожидание базы данных ---
echo "⏳ Waiting for database..."
python3 /app/wait-for-db.py
if [ $? -ne 0 ]; then
echo "❌ Database connection failed"
exit 1
fi
echo "✅ Database is ready"

# --- Запуск приложения ---
echo "🚀 Starting application..."
exec uvicorn main_api:app --host 0.0.0.0 --port 8099 --log-level debug --no-access-log
SCRIPT

# Права на исполнение entrypoint
RUN chmod +x entrypoint.sh

# 🏃 Команда запуска контейнера
CMD ["./entrypoint.sh"]
