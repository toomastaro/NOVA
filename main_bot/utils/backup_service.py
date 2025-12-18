import logging
from main_bot.database.db import db
from main_bot.utils.backup_utils import send_to_backup

logger = logging.getLogger(__name__)


async def send_to_backup_task(story_id: int):
    """
    Фоновая задача для отправки истории в backup канал и обновления записи в БД.
    """
    try:
        # Получаем актуальную версию истории
        story = await db.story.get_story(story_id)
        if not story:
            logger.error(f"Story {story_id} not found for backup")
            return

        # Отправляем в бэкап (синхронно внутри таски, но асинхронно для пользователя)
        backup_chat_id, backup_message_id = await send_to_backup(story)

        if backup_chat_id and backup_message_id:
            # Обновляем запись в БД
            await db.story.update_story(
                post_id=story.id,
                backup_chat_id=backup_chat_id,
                backup_message_id=backup_message_id,
            )
            logger.info(
                f"Story {story_id} successfully backed up to {backup_chat_id}:{backup_message_id}"
            )
        else:
            logger.warning(f"Backup failed for story {story_id}: returned empty ids")

    except Exception as e:
        logger.error(
            f"Error in background backup task for story {story_id}: {e}", exc_info=True
        )
