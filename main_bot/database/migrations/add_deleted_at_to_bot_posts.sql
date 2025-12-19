-- SQL для pgAdmin: Добавление колонки deleted_at в таблицу bot_posts
ALTER TABLE bot_posts ADD COLUMN IF NOT EXISTS deleted_at BIGINT;

-- Комментарий к колонке
COMMENT ON COLUMN bot_posts.deleted_at IS 'Время автоматического удаления сообщений рассылки';
