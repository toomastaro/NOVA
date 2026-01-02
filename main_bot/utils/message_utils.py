"""
Утилиты для работы с сообщениями и превью постов.

Этот модуль содержит функции для:
- Отправки превью постов, сторис и бот-постов
- Отправки сообщений через ботов
- Работы с медиафайлами в сообщениях
"""

import logging
import os
import pathlib
from typing import Optional, Union

from aiogram import Bot, types
from aiogram.fsm.context import FSMContext

from config import Config
from instance_bot import bot as main_bot_obj
from main_bot.keyboards import keyboards
from main_bot.keyboards.posting import ensure_obj
from main_bot.utils.file_utils import TEMP_DIR
from main_bot.utils.schemas import (
    MessageOptions,
    MessageOptionsCaptcha,
    MessageOptionsHello,
    StoryOptions,
)
from main_bot.database.db import db
from main_bot.utils.lang.language import text


logger = logging.getLogger(__name__)


async def answer_bot_post(
    message: types.Message, state: FSMContext, from_edit: bool = False
) -> types.Message:
    """
    Отправляет превью бот-поста пользователю.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): FSM контекст с данными поста.
        from_edit (bool): Флаг редактирования (влияет на клавиатуру).

    Возвращает:
        types.Message: Отправленное сообщение.
    """
    data = await state.get_data()

    post = ensure_obj(data.get("post"))
    is_edit: bool = data.get("is_edit")
    message_options = MessageOptionsHello(**post.message)

    # Определяем тип сообщения и соответствующую функцию
    if message_options.text:
        cor = message.answer
    elif message_options.photo:
        cor = message.answer_photo
        message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = message.answer_video
        message_options.video = message_options.video.file_id
    else:
        cor = message.answer_animation
        message_options.animation = message_options.animation.file_id

    if not from_edit:
        reply_markup = keyboards.manage_bot_post(post=post, is_edit=is_edit)
        message_options.reply_markup = reply_markup

    post_message = await cor(**message_options.model_dump(), parse_mode="HTML")

    return post_message


async def answer_post(
    message: types.Message, state: FSMContext, from_edit: bool = False
) -> types.Message:
    """
    Отправляет превью поста пользователю.

    Пытается загрузить превью из бэкапа, если доступно.
    В противном случае генерирует локально.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): FSM контекст с данными поста.
        from_edit (bool): Флаг редактирования (влияет на клавиатуру).

    Возвращает:
        types.Message: Отправленное сообщение.
    """
    data = await state.get_data()

    post = ensure_obj(data.get("post"))
    if not post:
        post_id = data.get("post_id")
        if post_id:
            post = await db.post.get_post(post_id)

    if not post:
        logger.error("Не удалось найти пост для превью")
        return await message.answer(text("story_not_found"))

    is_edit: bool = data.get("is_edit")
    message_options = MessageOptions(**post.message_options)

    # Определяем тип сообщения и соответствующую функцию
    if message_options.text:
        cor = message.answer
    elif message_options.photo:
        cor = message.answer_photo
        message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = message.answer_video
        message_options.video = message_options.video.file_id
    else:
        cor = message.answer_animation
        message_options.animation = message_options.animation.file_id

    if from_edit:
        reply_markup = keyboards.post_kb(post=post)
    else:
        reply_markup = keyboards.manage_post(
            post=post, show_more=data.get("show_more"), is_edit=is_edit
        )

    # Логика загрузки превью из бэкапа
    backup_msg_id = getattr(post, "backup_message_id", None)
    if backup_msg_id and Config.BACKUP_CHAT_ID:
        try:
            post_message = await message.bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=Config.BACKUP_CHAT_ID,
                message_id=backup_msg_id,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            logger.info(
                f"Превью для поста {post.id} загружено из бэкапа (msg {backup_msg_id})"
            )
            return post_message
        except Exception as e:
            logger.error(
                f"Не удалось загрузить превью из бэкапа для поста {post.id}: {e}",
                exc_info=True,
            )
            # Возврат к локальной генерации

    post_message = await cor(
        **message_options.model_dump(), reply_markup=reply_markup, parse_mode="HTML"
    )
    logger.info(f"Превью для поста {post.id} сгенерировано локально")

    return post_message


async def answer_story(
    message: types.Message, state: FSMContext, from_edit: bool = False
) -> types.Message:
    """
    Отправляет превью сторис пользователю.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): FSM контекст с данными сторис.
        from_edit (bool): Флаг редактирования (влияет на клавиатуру).

    Возвращает:
        types.Message: Отправленное сообщение.
    """
    data = await state.get_data()

    post = ensure_obj(data.get("post"))
    if not post:
        post_id = data.get("post_id")
        if post_id:
            post = await db.story.get_story(post_id)

    if not post:
        logger.error("Не удалось найти сторис для превью")
        return await message.answer(text("story_not_found"))

    is_edit: bool = data.get("is_edit")
    story_options = StoryOptions(**post.story_options)

    # Сторис может быть только фото или видео
    if story_options.photo:
        cor = message.answer_photo
        story_options.photo = story_options.photo.file_id
    else:
        cor = message.answer_video
        story_options.video = story_options.video.file_id

    if from_edit:
        reply_markup = None
    else:
        reply_markup = keyboards.manage_story(post=post, is_edit=is_edit)

    # Логика загрузки превью из бэкапа
    backup_msg_id = getattr(post, "backup_message_id", None)
    backup_chat_id = getattr(post, "backup_chat_id", None) or Config.BACKUP_CHAT_ID

    if backup_msg_id and backup_chat_id:
        try:
            post_message = await message.bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=backup_chat_id,
                message_id=backup_msg_id,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            logger.info(
                f"Превью для сторис {post.id} загружено из бэкапа (chat {backup_chat_id}, msg {backup_msg_id})"
            )
            return post_message
        except Exception as e:
            logger.error(
                f"Не удалось загрузить превью из бэкапа для сторис {post.id} (chat {backup_chat_id}, msg {backup_msg_id}): {e}"
            )
            # Если не удалось скопировать (например, сообщение удалено) - идем дальше к прямой отправке

    post_message = await cor(**story_options.model_dump(), reply_markup=reply_markup)

    return post_message


async def answer_message_bot(
    bot: Bot,
    chat_id: int,
    message_options: Union[MessageOptionsHello, MessageOptionsCaptcha],
) -> Optional[types.Message]:
    """
    Отправляет сообщение через бота в указанный чат.

    Скачивает медиафайлы если необходимо, отправляет сообщение,
    затем удаляет временные файлы.

    Аргументы:
        bot (Bot): Экземпляр бота для отправки.
        chat_id (int): ID чата для отправки.
        message_options (Union[MessageOptionsHello, MessageOptionsCaptcha]): Опции сообщения.

    Возвращает:
        Optional[types.Message]: Отправленное сообщение или None при ошибке.
    """
    # Определяем тип сообщения
    if message_options.text:
        cor = bot.send_message
    elif message_options.photo:
        cor = bot.send_photo
    elif message_options.video:
        cor = bot.send_video
    else:
        cor = bot.send_animation

    # Ищем file_id медиафайла
    attrs = ["photo", "video", "animation"]
    file_id = next(
        (
            getattr(message_options, attr).file_id
            for attr in attrs
            if getattr(message_options, attr)
        ),
        None,
    )

    # Скачиваем медиафайл если есть
    filepath = None
    try:
        if file_id:
            get_file = await main_bot_obj.get_file(file_id)
            # Используем pathlib для формирования безопасного пути
            filename = f"hello_message_media_{pathlib.Path(get_file.file_path).name}"
            # Используем общий TEMP_DIR
            filepath_obj = TEMP_DIR / filename
            filepath = str(filepath_obj)

            await main_bot_obj.download(file_id, filepath)
    except Exception as e:
        logger.error(f"Ошибка при скачивании медиафайла: {e}")
        return None

    dump = message_options.model_dump()
    dump["chat_id"] = chat_id
    dump["parse_mode"] = "HTML"

    # Удаляем специфичные поля для капчи
    if isinstance(message_options, MessageOptionsCaptcha):
        dump.pop("resize_markup", None)

    # Удаляем неиспользуемые поля в зависимости от типа сообщения
    if message_options.text:
        dump.pop("photo", None)
        dump.pop("video", None)
        dump.pop("animation", None)
        dump.pop("caption", None)

    elif message_options.photo:
        if filepath:
            dump["photo"] = types.FSInputFile(filepath)

        dump.pop("video", None)
        dump.pop("animation", None)
        dump.pop("text", None)

    elif message_options.video:
        if filepath:
            dump["video"] = types.FSInputFile(filepath)

        dump.pop("photo", None)
        dump.pop("animation", None)
        dump.pop("text", None)
    # animation
    else:
        if filepath:
            dump["animation"] = types.FSInputFile(filepath)

        dump.pop("photo", None)
        dump.pop("video", None)
        dump.pop("text", None)

    # Отправляем сообщение
    post_message = None
    try:
        post_message = await cor(**dump)
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        # Не возвращаем сразу, чтобы сработал finally/cleanup (здесь явного finally нет, но есть блок ниже)

    # Удаляем временный файл
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {filepath}: {e}")

    return post_message


async def answer_message(
    message: types.Message,
    message_options: Union[MessageOptionsHello, MessageOptionsCaptcha],
) -> types.Message:
    """
    Отвечает на сообщение пользователя с указанными опциями.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        message_options (Union[MessageOptionsHello, MessageOptionsCaptcha]): Опции сообщения.

    Возвращает:
        types.Message: Отправленное сообщение.
    """
    # Определяем тип сообщения
    if message_options.text:
        cor = message.answer
    elif message_options.photo:
        cor = message.answer_photo
        message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = message.answer_video
        message_options.video = message_options.video.file_id
    else:
        cor = message.answer_animation
        message_options.animation = message_options.animation.file_id

    post_message = await cor(**message_options.model_dump(), parse_mode="HTML")

    return post_message

async def reload_main_menu(message: types.Message) -> None:
    """
    Обновляет главное меню (Reply Keyboard) и удаляет сервисное сообщение.
    Это позволяет избежать накопления лишних сообщений 'Главное меню' в чате.

    Аргументы:
        message (types.Message): Сообщение, от которого вызывается ответ.
    """
    from main_bot.keyboards.common import Reply
    import asyncio

    # Используем bot.send_message напрямую к ID чата для большей стабильности
    try:
        msg = await message.bot.send_message(
            chat_id=message.chat.id,
            text=text("main_menu:reload"),
            reply_markup=Reply.menu()
        )
        # Небольшая пауза, чтобы клиент успел получить и отобразить новую клавиатуру
        await asyncio.sleep(0.5)
        await msg.delete()
    except Exception as e:
        logger.error(f"Ошибка при обновлении главного меню: {e}")
