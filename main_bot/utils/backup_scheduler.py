"""
Планировщик для автоматической очистки бэкап канала
"""
import asyncio
import logging
from datetime import datetime, time

from aiogram import Bot

from main_bot.utils.backup_manager import BackupManager

logger = logging.getLogger(__name__)


class BackupScheduler:
    """Планировщик задач для бэкап системы"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.backup_manager = BackupManager(bot)
        self._running = False
        self._task = None

    async def start(self):
        """Запускает планировщик"""
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("Планировщик очистки бэкапов запущен")

    async def stop(self):
        """Останавливает планировщик"""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Планировщик очистки бэкапов остановлен")

    async def _cleanup_loop(self):
        """Основной цикл очистки - запускается каждые 24 часа в 3:00"""
        try:
            while self._running:
                now = datetime.now()
                
                # Вычисляем время следующего запуска (3:00 ночи)
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now >= next_run:
                    # Если уже прошло 3:00, то следующий запуск завтра
                    next_run = next_run.replace(day=now.day + 1)
                
                # Ждем до следующего запуска
                sleep_time = (next_run - now).total_seconds()
                await asyncio.sleep(sleep_time)
                
                if self._running:
                    await self._perform_cleanup()
                    
        except asyncio.CancelledError:
            logger.info("Цикл очистки бэкапов отменен")
        except Exception as e:
            logger.error(f"Ошибка в цикле очистки бэкапов: {e}")

    async def _perform_cleanup(self):
        """Выполняет очистку старых бэкапов"""
        try:
            logger.info("Начинается очистка старых бэкапов...")
            cleaned_count = await self.backup_manager.cleanup_old_backups()
            logger.info(f"Очистка завершена. Удалено {cleaned_count} старых бэкапов")
        except Exception as e:
            logger.error(f"Ошибка при очистке бэкапов: {e}")

    async def force_cleanup(self) -> int:
        """Принудительная очистка (для админских команд)"""
        return await self.backup_manager.cleanup_old_backups()