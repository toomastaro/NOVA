"""
Модуль инициализации основного бота.

Создает и настраивает экземпляр бота (aiogram.Bot) с использованием
токена из конфигурации и настроек по умолчанию (ParseMode.HTML).

Экспорт:
    bot (Bot): Глобальный экземпляр бота.
"""

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config

# Инициализация бота с HTML парсингом по умолчанию
bot = Bot(
    token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
