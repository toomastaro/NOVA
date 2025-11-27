#!/usr/bin/env bash
set -euo pipefail

# ===== Переходим в корень проекта (где docker-compose.yml) =====
cd /root/bot

# ===== Опционально подтягиваем .env =====
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# ===== Настройки (можно переопределить через .env) =====
COMPOSE_SERVICE="${COMPOSE_SERVICE:-db}"
PG_USER="${PG_USER:-postgres}"
PG_DATABASE="${PG_DATABASE:-nova_bot_db}"
PG_PASS="${PG_PASS:-}"
BACKUP_DIR="${BACKUP_DIR:-backups}"

# ===== Проверки =====
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker не найден."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "❌ Docker Compose v2 не найден."
  exit 1
fi
if [ -z "${PG_PASS}" ]; then
  echo "❌ PG_PASS не задан. Добавь его в .env или в окружение."
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

print_cfg() {
  echo "📘 Параметры:"
  echo "  Compose service: ${COMPOSE_SERVICE}"
  echo "  DB user: ${PG_USER}"
  echo "  DB name: ${PG_DATABASE}"
  echo "  Backup dir: ${BACKUP_DIR}"
  echo
}

do_backup() {
  print_cfg
  TS="$(date +%F_%H-%M-%S)"
  FILE="${BACKUP_DIR}/backup_${TS}_${PG_DATABASE}.sql.gz"
  echo "→ Создаю бэкап: ${FILE}"
  docker compose exec -T -e "PGPASSWORD=${PG_PASS}" "${COMPOSE_SERVICE}" \
    pg_dump -U "${PG_USER}" "${PG_DATABASE}" | gzip > "${FILE}"
  if [ -s "${FILE}" ]; then
    echo "✅ Бэкап готов: ${FILE}"
  else
    echo "❌ Ошибка — файл пустой!"
    exit 1
  fi
}

do_restore() {
  FILE="${1:-}"
  if [ -z "${FILE}" ]; then
    echo "❌ Укажи файл: $0 restore <backup.sql|backup.sql.gz>"
    exit 1
  fi
  if [ ! -f "${FILE}" ]; then
    echo "❌ Файл не найден: ${FILE}"
    exit 1
  fi

  print_cfg
  echo "→ Завершаю активные подключения..."
  docker compose exec -T -e "PGPASSWORD=${PG_PASS}" "${COMPOSE_SERVICE}" \
    psql -U "${PG_USER}" -d postgres -v ON_ERROR_STOP=1 -c \
"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PG_DATABASE}' AND pid <> pg_backend_pid();"

  echo "→ Пересоздаю базу..."
  docker compose exec -T -e "PGPASSWORD=${PG_PASS}" "${COMPOSE_SERVICE}" dropdb   -U "${PG_USER}" --if-exists "${PG_DATABASE}"
  docker compose exec -T -e "PGPASSWORD=${PG_PASS}" "${COMPOSE_SERVICE}" createdb -U "${PG_USER}" "${PG_DATABASE}"

  echo "→ Накатываю дамп: ${FILE}"
  if [[ "${FILE}" == *.gz ]]; then
    gunzip -c "${FILE}" | docker compose exec -T -e "PGPASSWORD=${PG_PASS}" "${COMPOSE_SERVICE}" \
      psql -U "${PG_USER}" -d "${PG_DATABASE}" -v ON_ERROR_STOP=1
  else
    docker compose exec -T -e "PGPASSWORD=${PG_PASS}" "${COMPOSE_SERVICE}" \
      psql -U "${PG_USER}" -d "${PG_DATABASE}" -v ON_ERROR_STOP=1 < "${FILE}"
  fi
  echo "✅ Восстановление завершено."
}

usage() {
  cat <<EOF
Использование:
  ./pg_backup.sh backup
  ./pg_backup.sh restore <backup.sql|backup.sql.gz>

Настройки берутся из /root/bot/.env (или из окружения):
  COMPOSE_SERVICE=db
  PG_USER=postgres
  PG_DATABASE=nova_bot_db
  PG_PASS=F
EOF
}

CMD="${1:-}"
case "${CMD}" in
  backup)
    do_backup
    ;;
  restore)
    shift || true
    do_restore "${1:-}"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "❌ Неизвестная команда: ${CMD}"
    usage
    exit 1
    ;;
esac
