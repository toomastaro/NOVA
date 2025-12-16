-- Миграция: Индексы для оптимизации запросов каналов
-- Дата создания: 2025-12-16
-- Цель: ускорить запросы get_user_channels при нагрузке 1000+ админов

-- Индекс для быстрого поиска каналов пользователя с активной подпиской
-- Используется в: posting/menu.py::show_create_post
CREATE INDEX IF NOT EXISTS idx_channels_admin_subscribe 
ON channels(admin_id, subscribe) 
WHERE subscribe IS NOT NULL;

-- Индекс для сортировки по подписке (используется в sort_by="posting")
CREATE INDEX IF NOT EXISTS idx_channels_admin_subscribe_desc 
ON channels(admin_id) 
INCLUDE (subscribe, chat_id, title, emoji_id, created_timestamp);

-- Проверка созданных индексов
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'channels';
