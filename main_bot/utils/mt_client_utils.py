import logging
from pathlib import Path

from main_bot.database.db import db
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


async def reset_client_task(client_id: int):
    """
    Задача полного сброса клиента (MTProto).
    
    1. Устанавливает статус RESETTING
    2. Выходит из всех каналов
    3. Удаляет записи о каналах
    4. Сбрасывает поля клиента (статус NEW)
    """
    logger.info(f"Запуск сброса клиента {client_id}")
    
    # 1. Устанавливаем статус RESETTING
    await db.mt_client.update_mt_client(
        client_id=client_id,
        status='RESETTING',
        is_active=False
    )
    
    client = await db.mt_client.get_mt_client(client_id)
    if not client:
        logger.error(f"Клиент {client_id} не найден во время сброса")
        return

    # 2. Получаем все каналы
    channels = await db.mt_client_channel.get_channels_by_client(client_id)
    
    # 3. Выходим из каналов
    if Path(client.session_path).exists():
        async with SessionManager(Path(client.session_path)) as manager:
            for channel in channels:
                try:
                    logger.info(f"Клиент {client_id} покидает канал {channel.channel_id}")
                    await manager.leave_channel(channel.channel_id)
                except Exception as e:
                    logger.error(f"Ошибка выхода из канала {channel.channel_id} для клиента {client_id}: {e}")
    else:
        logger.warning(f"Файл сессии не найден для клиента {client_id}, пропуск выхода из каналов")

    # 4. Удаляем записи MtClientChannel
    await db.mt_client_channel.delete_channels_by_client(client_id)
    
    # 5. Сбрасываем поля MtClient
    await db.mt_client.update_mt_client(
        client_id=client_id,
        status='NEW',
        is_active=False,
        last_error_code=None,
        last_error_at=None,
        flood_wait_until=None
    )
    
    logger.info(f"Сброс клиента {client_id} завершен")
