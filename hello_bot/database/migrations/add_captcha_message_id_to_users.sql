-- Добавление поля captcha_message_id в таблицу users для всех схем hello_bot
-- Дата: 2026-01-16
-- Автоматически применяется ко всем схемам, начинающимся с 'hello_'

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    -- Перебираем все схемы, начинающиеся с 'hello_'
    FOR schema_name IN 
        SELECT nspname 
        FROM pg_namespace 
        WHERE nspname LIKE 'hello_%'
    LOOP
        -- Добавляем колонку в таблицу users для каждой схемы
        EXECUTE format('ALTER TABLE %I.users ADD COLUMN IF NOT EXISTS captcha_message_id BIGINT DEFAULT NULL', schema_name);
        
        -- Добавляем комментарий к колонке
        EXECUTE format('COMMENT ON COLUMN %I.users.captcha_message_id IS ''ID сообщения с капчей для последующего удаления''', schema_name);
        
        RAISE NOTICE 'Обновлена схема: %', schema_name;
    END LOOP;
END $$;
