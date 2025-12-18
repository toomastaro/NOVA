"""
Планировщик задач для отправки сторис в каналы.

Этот модуль содержит функции для:
- Отправки отложенных сторис
- Управления сторис через Telegram MT клиенты
"""

import asyncio
import logging
import time
import html
import os
from pathlib import Path

from telethon.errors import FloodWaitError

from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.db_types import Status
from main_bot.database.story.model import Story
from main_bot.utils.file_utils import get_path, get_path_video
from main_bot.utils.tg_utils import set_channel_session
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import StoryOptions
from main_bot.utils.session_manager import SessionManager
from main_bot.utils.support_log import send_support_alert, SupportAlert
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


async def send_story(story: Story):
    """
    Отправить сторис в каналы.

    Обрабатывает отправку одного сторис во все указанные каналы.
    Использует MT клиенты для отправки, так как Bot API не поддерживает сторис.

    Args:
        story: Объект сторис для отправки
    """
    logger.info(
        f"🚀 Начинаем отправку сторис {story.id} для {len(story.chat_ids)} каналов"
    )
    options = StoryOptions(**story.story_options)

    if options.photo:
        options.photo = options.photo.file_id
    if options.video:
        options.video = options.video.file_id

    error_send = []
    success_send = []

    for chat_id in story.chat_ids:
        channel = await db.channel.get_channel_by_chat_id(chat_id)
        if not channel:
            logger.warning(f"⚠️ Канал {chat_id} не найден в БД")
            continue

        if not channel.subscribe:
            logger.warning(
                f"⚠️ Канал {chat_id} ({channel.title}) не имеет активной подписки"
            )
            continue

        # Получение пути к сессии MT клиента
        if channel.session_path:
            session_path = Path(channel.session_path)
        else:
            res = await set_channel_session(chat_id)
            if isinstance(res, dict) and res.get("success"):
                session_path = Path(res.get("session_path"))
            elif isinstance(res, Path):
                session_path = res
            else:
                session_path = None

        logger.info(f"Путь к сессии для {chat_id}: {session_path}")
        if isinstance(session_path, dict):
            session_path["chat_id"] = chat_id
            error_send.append(session_path)
            continue

        if not session_path:
            logger.error(f"❌ Ошибка: сессия для {chat_id} не найдена")
            error_send.append({"chat_id": chat_id, "error": "Ошибка сессии"})
            continue

        # Инициализация MT клиента
        path_obj = Path(session_path)

        try:
            # Используем менеджер сессий
            async with SessionManager(path_obj) as manager:
                if not manager.client:
                    logger.error(
                        f"Не удалось инициализировать клиент для сессии {session_path}"
                    )
                    error_send.append(
                        {"chat_id": chat_id, "error": "Init client error"}
                    )
                    continue

                # Проверка прав на отправку сторис
                try:
                    can_post = await manager.can_send_stories(chat_id)
                    if not can_post:
                        logger.warning(f"⛔️ Нет прав на отправку сторис в {chat_id}")
                        error_send.append(
                            {"chat_id": chat_id, "error": "Нет прав администратора"}
                        )
                        continue
                except Exception as e:
                    logger.error(
                        f"Ошибка при предварительной проверке для {chat_id}: {e}",
                        exc_info=True,
                    )
                    error_send.append(
                        {"chat_id": chat_id, "error": f"Ошибка проверки: {e}"}
                    )
                    continue

                # Скачивание медиафайла
                input_file = None
                filepath = None
                try:
                    # Проверка TEMP_DIR
                    temp_dir = Path("main_bot/utils/temp")
                    if not temp_dir.exists():
                        temp_dir.mkdir(parents=True, exist_ok=True)

                    if options.video:
                        file_info = await bot.get_file(options.video)
                        input_file = str(temp_dir / file_info.file_path.split("/")[-1])

                    media_bytes = await bot.download(
                        file=options.video or options.photo, destination=input_file
                    )

                    if options.photo:
                        filepath = await get_path(media_bytes, chat_id)
                    else:
                        filepath = await get_path_video(input_file, chat_id)
                except Exception as e:
                    logger.error(f"❌ Ошибка скачивания медиа: {e}", exc_info=True)
                    error_send.append(
                        {"chat_id": chat_id, "error": "Ошибка скачивания медиа"}
                    )
                    continue

                # Замена тегов эмодзи для совместимости с MT
                if options.caption:
                    caption = options.caption
                    options.caption = caption.replace(
                        "<tg-emoji emoji-id", "<emoji id"
                    ).replace("</tg-emoji>", "</emoji>")

                # Отправка сторис
                try:
                    logger.info(f"📤 Отправляем сторис в {chat_id}...")
                    await manager.send_story(
                        chat_id=chat_id, file_path=filepath, options=options
                    )
                    success_send.append({"chat_id": chat_id})
                    logger.info(f"✅ Сторис успешно отправлена в {chat_id}")

                except FloodWaitError as err_flood:
                    logger.warning(
                        f"⏳ FloodWait {err_flood.seconds}s для {chat_id}. Ждем..."
                    )
                    await asyncio.sleep(err_flood.seconds)
                    # Повторная попытка (один раз)
                    try:
                        logger.info(f"🔄 Повторная попытка отправки в {chat_id}...")
                        await manager.send_story(
                            chat_id=chat_id, file_path=filepath, options=options
                        )
                        success_send.append({"chat_id": chat_id})
                        logger.info(
                            f"✅ Сторис успешно отправлена в {chat_id} (после FloodWait)"
                        )
                    except Exception as e_retry:
                        logger.error(
                            f"❌ Ошибка после FloodWait в {chat_id}: {e_retry}"
                        )
                        error_send.append({"chat_id": chat_id, "error": str(e_retry)})

                except Exception as e:
                    logger.error(
                        f"❌ Ошибка при отправке сторис в {chat_id}: {e}", exc_info=True
                    )
                    error_str = str(e)
                    error_send.append({"chat_id": chat_id, "error": error_str})

                    # Отправка алерта в поддержку при критических ошибках
                    if (
                        "CHAT_ADMIN_REQUIRED" in error_str
                        or "STORIES_DISABLED" in error_str
                        or "USER_NOT_PARTICIPANT" in error_str
                    ):
                        found_client = None
                        if session_path:
                            clients = await db.mt_client.get_mt_clients_by_pool(
                                "internal"
                            )
                            for c in clients:
                                if Path(c.session_path) == path_obj:
                                    found_client = c
                                    break
                        # Попытка отправить алерт, но не падать, если не вышло
                        try:
                            await send_support_alert(
                                bot,
                                SupportAlert(
                                    event_type=(
                                        "STORIES_PERMISSION_DENIED"
                                        if "ADMIN" in error_str
                                        else "INTERNAL_ACCESS_LOST"
                                    ),
                                    client_id=found_client.id if found_client else None,
                                    client_alias=(
                                        found_client.alias if found_client else None
                                    ),
                                    pool_type="internal",
                                    channel_id=chat_id,
                                    channel_username=channel.icon if channel else None,
                                    is_our_channel=True,
                                    task_id=story.id,
                                    task_type="send_story",
                                    error_code=(
                                        error_str.split("(")[0].strip()
                                        if "(" in error_str
                                        else error_str[:50]
                                    ),
                                    error_text=f"Не удалось отправить сторис: {error_str[:100]}",
                                ),
                            )
                        except Exception as e_alert:
                            logger.error(f"Не удалось отправить алерт: {e_alert}")

                # Очистка ресурса
                try:
                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла {filepath}: {e}")

        except Exception as e:
            logger.error(f"Global error for {chat_id}: {e}", exc_info=True)
            error_send.append({"chat_id": chat_id, "error": str(e)})

    logger.info(
        f"🏁 Завершение обработки сторис {story.id}. Успешно: {len(success_send)}, Ошибок: {len(error_send)}"
    )

    # Обновление статуса сторис и времени отправки (для истории)
    update_data = {"status": Status.FINISH}
    if not story.send_time:
        update_data["send_time"] = int(time.time())

    await db.story.update_story(post_id=story.id, **update_data)

    # Отправка отчета пользователю
    if not story.report:
        return

    objects = await db.channel.get_user_channels(
        user_id=story.admin_id, from_array=story.chat_ids
    )

    success_str = "\n".join(
        text("resource_title").format(html.escape(obj.title))
        for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in success_send[:10]]
    )

    error_str = "\n".join(
        text("resource_title").format(html.escape(obj.title))
        + " \n{}".format(
            "".join(
                row.get("error")
                for row in error_send[:10]
                if row.get("chat_id") == obj.chat_id
            )
        )
        for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in error_send[:10]]
    )

    if success_send and error_send:
        message_text = text("success_error:story:public").format(
            success_str,
            error_str,
        )
    elif success_send:
        message_text = text("manage:story:success:public").format(
            success_str,
        )
    elif error_send:
        message_text = text("error:story:public").format(
            error_str,
        )
    else:
        message_text = "Неизвестное сообщение уведомления о сторис"

    try:
        await bot.send_message(chat_id=story.admin_id, text=message_text)
    except Exception as e:
        logger.error(
            f"Ошибка при отправке отчета о сторис админу {story.admin_id}: {e}",
            exc_info=True,
        )


@safe_handler("Сторис: отправка отложенных (Background)", log_start=False)
async def send_stories():
    """
    Периодическая задача: отправка отложенных сторис.

    Получает все сторис, готовые к отправке, и запускает их обработку.
    """
    stories = await db.story.get_story_for_send()

    # Фильтрация черновиков (send_time=0)
    valid_stories = [s for s in stories if s.send_time != 0]

    if valid_stories:
        logger.info(f"🔍 Найдено {len(valid_stories)} сторис для отправки")

    for story in valid_stories:
        asyncio.create_task(send_story(story))
