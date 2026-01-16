-- Добавление поля start_delay в таблицу channel_captcha
-- Дата: 2026-01-16

ALTER TABLE channel_captcha
ADD COLUMN IF NOT EXISTS start_delay INTEGER DEFAULT 0;
