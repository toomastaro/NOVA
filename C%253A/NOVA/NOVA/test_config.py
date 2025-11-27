#!/usr/bin/env python3
"""
Скрипт для диагностики ошибки загрузки конфигурации ADMINS
"""
import os

# Устанавливаем переменные окружения как на сервере  
os.environ.update({
    'ADMINS': '455244768,6723934020',
    'BOT_TOKEN': '6471752078:TEST',
    'ADMIN_SUPPORT': '-1002049832561',
    'PG_USER': 'postgres',
    'PG_PASS': 'F',
    'PG_HOST': 'db', 
    'PG_DATABASE': 'nova_bot_db',
    'WEBHOOK_DOMAIN': 'https://bot.nova.tg',
    'API_ID': '20121073',
    'API_HASH': '967f46e1a95229ad82c3053bd4042ef5'
})

def test_parsing():
    """Тестируем парсинг ADMINS"""
    print("=== Тест парсинга ADMINS ===")
    
    admins_str = '455244768,6723934020'
    print(f"Исходная строка: {repr(admins_str)}")
    
    # Тестируем нашу логику
    result = [int(x.strip()) for x in admins_str.split(",") if x.strip()]
    print(f"Результат парсинга: {result}")
    print(f"Типы: {[type(x) for x in result]}")

def test_config():
    """Тестируем загрузку конфигурации"""
    print("=== Тест загрузки конфигурации ===")
    
    try:
        from config import Settings
        settings = Settings()
        print(f"SUCCESS! settings.ADMINS = {settings.ADMINS}")
    except Exception as e:
        print(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parsing()
    test_config()