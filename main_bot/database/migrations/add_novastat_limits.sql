-- Миграция: Добавление суточного лимита для NOVASTAT
ALTER TABLE novastat_settings ADD COLUMN IF NOT EXISTS daily_check_count INTEGER DEFAULT 0;
ALTER TABLE novastat_settings ADD COLUMN IF NOT EXISTS last_check_reset BIGINT DEFAULT 0;
