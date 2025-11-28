"""
Интеграция бэкап системы в основной процесс бота
"""
import logging
from aiogram import Bot

from main_bot.utils.backup_scheduler import BackupScheduler

logger = logging.getLogger(__name__)

# Глобальная переменная для планировщика
backup_scheduler: BackupScheduler = None


async def init_backup_system(bot: Bot):
    """Инициализация системы бэкапов"""
    global backup_scheduler
    
    try:
        backup_scheduler = BackupScheduler(bot)
        await backup_scheduler.start()
        logger.info("Система бэкапов успешно инициализирована")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации системы бэкапов: {e}")


async def shutdown_backup_system():
    """Корректное завершение работы системы бэкапов"""
    global backup_scheduler
    
    try:
        if backup_scheduler:
            await backup_scheduler.stop()
            logger.info("Система бэкапов корректно завершена")
            
    except Exception as e:
        logger.error(f"Ошибка завершения системы бэкапов: {e}")


def get_backup_scheduler() -> BackupScheduler:
    """Получить экземпляр планировщика бэкапов"""
    return backup_scheduler