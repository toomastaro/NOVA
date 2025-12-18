"""
Модуль утилит для работы с бэкап-каналом (резервным хранилищем постов).
"""

import asyncio
import logging
from typing import Any

from config import Config
from instance_bot import bot
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from main_bot.database.story.model import Story
from main_bot.keyboards import keyboards
from main_bot.utils.schemas import MessageOptions

logger = logging.getLogger(__name__)


def _prepare_send_options(message_options: MessageOptions) -> tuple[Any, dict]:
    """
    Вспомогательная функция для определения метода отправки и подготовки параметров.

    Аргументы:
        message_options (MessageOptions): Опции сообщения.

    Возвращает:
        tuple[Any, dict]: Метод отправки (coroutine) и словарь параметров.
    """
    if message_options.text:
        cor = bot.send_message
        options = message_options.model_dump(
            exclude={
                "photo",
                "video",
                "animation",
                "show_caption_above_media",
                "has_spoiler",
                "caption",
                "reply_markup",
            }
        )
    elif message_options.photo:
        cor = bot.send_photo
        options = message_options.model_dump(
            exclude={
                "video",
                "animation",
                "text",
                "disable_web_page_preview",
                "reply_markup",
            }
        )
        if hasattr(message_options.photo, "file_id"):
            options["photo"] = message_options.photo.file_id
    elif message_options.video:
        cor = bot.send_video
        options = message_options.model_dump(
            exclude={
                "photo",
                "animation",
                "text",
                "disable_web_page_preview",
                "reply_markup",
            }
        )
        if hasattr(message_options.video, "file_id"):
            options["video"] = message_options.video.file_id
    else:  # animation
        cor = bot.send_animation
        options = message_options.model_dump(
            exclude={
                "photo",
                "video",
                "text",
                "disable_web_page_preview",
                "reply_markup",
            }
        )
        if hasattr(message_options.animation, "file_id"):
            options["animation"] = message_options.animation.file_id

    options["parse_mode"] = "HTML"
    return cor, options


async def send_to_backup(post: Post | Story | BotPost) -> tuple[int | None, int | None]:
    """
    Отправляет пост в резервный канал. Возвращает ID чата и сообщения.

    Аргументы:
        post (Post | Story | BotPost): Объект поста.

    Возвращает:
        tuple[int | None, int | None]: (chat_id, message_id) или (None, None).
    """
    if not Config.BACKUP_CHAT_ID:
        return None, None

    # Определяем тип объекта по наличию специфичных полей
    # Это позволяет поддерживать как SQLAlchemy объекты, так и ObjWrapper (ленивая загрузка)

    # STORY
    if hasattr(post, "story_options") and post.story_options:
        # Фильтрация полей для соответствия MessageOptions
        story_dump = (
            post.story_options.copy()
            if hasattr(post.story_options, "copy")
            else dict(post.story_options)
        )
        valid_fields = MessageOptions.model_fields.keys()
        filtered_story_options = {
            k: v for k, v in story_dump.items() if k in valid_fields
        }

        message_options = MessageOptions(**filtered_story_options)
        reply_markup = keyboards.story_kb(post=post)

    # BOT POST
    elif (
        hasattr(post, "message")
        and post.message
        and not hasattr(post, "message_options")
    ):
        from main_bot.utils.schemas import MessageOptionsHello

        message_options = MessageOptionsHello(**post.message)
        reply_markup = keyboards.bot_post_kb(post=post)

    # POST / PUBLISHED POST
    elif hasattr(post, "message_options") and post.message_options:
        message_options = MessageOptions(**post.message_options)
        reply_markup = keyboards.post_kb(post=post)
    else:
        logger.error(f"Не удалось определить тип поста для бэкапа: {type(post)}")
        return None, None

    cor, options = _prepare_send_options(message_options)
    options["chat_id"] = Config.BACKUP_CHAT_ID
    # reply_markup передается отдельно, чтобы избежать путаницы с pop/clean, если словарь изменяется на месте

    try:
        backup_msg = await cor(**options, reply_markup=reply_markup)
        return Config.BACKUP_CHAT_ID, backup_msg.message_id
    except Exception as e:
        logger.error(f"Ошибка отправки в резервный канал: {e}", exc_info=True)
        return None, None


async def edit_backup_message(
    post: Post | PublishedPost | Story | BotPost, message_options: MessageOptions = None
) -> None:
    """
    Обновляет сообщение в резервном канале в соответствии с текущим состоянием поста.

    Если редактирование не удается, пытается удалить и отправить заново.

    Аргументы:
        post (Post | PublishedPost | Story | BotPost): Объект поста.
        message_options (MessageOptions): Опции сообщения (опционально).
    """
    if not post or not post.backup_chat_id or not post.backup_message_id:
        return

    if not message_options:
        # STORY
        if hasattr(post, "story_options") and post.story_options:
            # Фильтрация полей
            story_dump = (
                post.story_options.copy()
                if hasattr(post.story_options, "copy")
                else dict(post.story_options)
            )
            valid_fields = MessageOptions.model_fields.keys()
            filtered = {k: v for k, v in story_dump.items() if k in valid_fields}

            message_options = MessageOptions(**filtered)
            reply_markup = keyboards.story_kb(post=post)

        # BOT POST
        elif (
            hasattr(post, "message")
            and post.message
            and not hasattr(post, "message_options")
        ):
            from main_bot.utils.schemas import MessageOptionsHello

            message_options = MessageOptionsHello(**post.message)
            reply_markup = keyboards.bot_post_kb(post=post)

        # POST / PUBLISHED POST
        elif hasattr(post, "message_options") and post.message_options:
            message_options = MessageOptions(**post.message_options)
            reply_markup = keyboards.post_kb(post=post)

    else:
        # Если message_options передан, нам все равно нужна правильная клавиатура
        if hasattr(post, "story_options") and post.story_options:
            reply_markup = keyboards.story_kb(post=post)
        elif (
            hasattr(post, "message")
            and post.message
            and not hasattr(post, "message_options")
        ):
            reply_markup = keyboards.bot_post_kb(post=post)
        elif hasattr(post, "message_options") and post.message_options:
            reply_markup = keyboards.post_kb(post=post)
        else:
            reply_markup = None

    if not message_options:
        logger.error(
            f"Не удалось определить message_options для поста типа {type(post)}"
        )
        return

    chat_id = post.backup_chat_id
    message_id = post.backup_message_id

    try:
        if message_options.text:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_options.text,
                parse_mode="HTML",
                disable_web_page_preview=message_options.disable_web_page_preview,
                reply_markup=reply_markup,
            )
        else:
            # Медиа сообщение
            if message_options.caption is not None:
                await bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=message_options.caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            else:
                # Обновляем только клавиатуру, если подпись не изменилась
                await bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id, reply_markup=reply_markup
                )

    except Exception as e:
        logger.error(
            f"Ошибка редактирования сообщения бэкапа {message_id} в {chat_id}: {e}. Попытка отката (удаление и повторная отправка)."
        )
        try:
            # Откат: Удаление и повторная отправка в бэкап
            try:
                await bot.delete_message(chat_id, message_id)
            except Exception as del_e:
                logger.warning(
                    f"Не удалось удалить сообщение бэкапа {message_id}: {del_e}"
                )

            # Отправка нового сообщения в бэкап с использованием хелпера
            cor, send_options = _prepare_send_options(message_options)
            send_options["chat_id"] = chat_id

            new_backup_msg = await cor(**send_options, reply_markup=reply_markup)
            new_backup_message_id = new_backup_msg.message_id

            # Обновление БД
            post_id = post.post_id if isinstance(post, PublishedPost) else post.id

            # Обновление поста
            if isinstance(post, Story):
                await db.story.update_story(
                    post.id, backup_message_id=new_backup_message_id
                )
            elif isinstance(post, BotPost):
                await db.bot_post.update_bot_post(
                    post.id, backup_message_id=new_backup_message_id
                )
            elif isinstance(post, (Post, PublishedPost)):
                # Обновление поста
                await db.post.update_post(
                    post_id=post_id, backup_message_id=new_backup_message_id
                )

                # Обновление всех опубликованных постов
                await db.published_post.update_published_posts_by_post_id(
                    post_id=post_id, backup_message_id=new_backup_message_id
                )

            logger.info(
                f"Откат бэкапа успешен: Заменено {message_id} на {new_backup_message_id} для поста {post_id}"
            )

        except Exception as fallback_e:
            logger.error(
                f"Ошибка отката бэкапа для поста {post.id if hasattr(post, 'id') else '?'}: {fallback_e}",
                exc_info=True,
            )


async def _update_single_live_message(
    post: PublishedPost,
    message_options: MessageOptions,
    reply_markup,
    semaphore: asyncio.Semaphore,
) -> None:
    """
    Хелпер для обновления одного живого сообщения с семафором.

    Если обновление не удается, пытается восстановить сообщение из бэкапа.

    Аргументы:
        post (PublishedPost): Опубликованный пост.
        message_options (MessageOptions): Опции сообщения.
        reply_markup: Клавиатура.
        semaphore (asyncio.Semaphore): Семафор для ограничения конкурентности.
    """
    async with semaphore:
        try:
            if message_options.text:
                await bot.edit_message_text(
                    chat_id=post.chat_id,
                    message_id=post.message_id,
                    text=message_options.text,
                    parse_mode="HTML",
                    disable_web_page_preview=message_options.disable_web_page_preview,
                    reply_markup=reply_markup,
                )
            else:
                if message_options.caption is not None:
                    await bot.edit_message_caption(
                        chat_id=post.chat_id,
                        message_id=post.message_id,
                        caption=message_options.caption,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                    )
                else:
                    await bot.edit_message_reply_markup(
                        chat_id=post.chat_id,
                        message_id=post.message_id,
                        reply_markup=reply_markup,
                    )
        except Exception as e:
            logger.error(
                f"Ошибка обновления живого сообщения {post.message_id} в {post.chat_id}: {e}. Попытка отката (удаление и репост)."
            )
            try:
                # Откат: Удаление и копирование из бэкапа
                try:
                    await bot.delete_message(post.chat_id, post.message_id)
                except Exception as del_e:
                    logger.warning(
                        f"Не удалось удалить сообщение {post.message_id} в {post.chat_id}: {del_e}"
                    )

                if post.backup_chat_id and post.backup_message_id:
                    new_msg = await bot.copy_message(
                        chat_id=post.chat_id,
                        from_chat_id=post.backup_chat_id,
                        message_id=post.backup_message_id,
                        reply_markup=reply_markup,
                        parse_mode="HTML",
                    )

                    # Обновление PublishedPost с новым message_id
                    await db.published_post.update_published_post(
                        post_id=post.id, message_id=new_msg.message_id
                    )
                    logger.info(
                        f"Откат успешен: Заменено сообщение {post.message_id} на {new_msg.message_id} в {post.chat_id}"
                    )
                else:
                    logger.error(
                        f"Ошибка отката: Нет информации о бэкапе для поста {post.id}"
                    )

            except Exception as fallback_e:
                logger.error(
                    f"Ошибка отката для {post.chat_id}: {fallback_e}", exc_info=True
                )


async def update_live_messages(
    post_id: int, message_options: MessageOptions, reply_markup=None
) -> None:
    """
    Обновляет все опубликованные сообщения (live/channels) для указанного поста.

    Аргументы:
        post_id (int): ID родительского поста.
        message_options (MessageOptions): Опции сообщения.
        reply_markup: Клавиатура (опционально).
    """
    published_posts = await db.published_post.get_published_posts_by_post_id(post_id)
    if not published_posts:
        return

    # Ограничение конкурентности чтобы избежать флуда API Telegram
    semaphore = asyncio.Semaphore(10)

    tasks = [
        _update_single_live_message(post, message_options, reply_markup, semaphore)
        for post in published_posts
    ]

    await asyncio.gather(*tasks)

    logger.info(f"Обновлено {len(published_posts)} живых сообщений для поста {post_id}")
