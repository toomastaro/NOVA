"""
Модуль обработки ввода текста/сообщения для поста.

Содержит логику:
- Получение первичного сообщения от пользователя
- Отмена создания поста
- Парсинг текста, медиа и кнопок из сообщения
"""

import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.utils.message_utils import answer_post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import MessageOptions, Media
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Отмена создания поста")
async def cancel_message(call: types.CallbackQuery, state: FSMContext):
    """
    Отмена создания поста - очистка состояния и возврат в меню постинга.

    Args:
        call: Callback query от кнопки отмены
        state: FSM контекст
    """
    logger.info("Пользователь %s отменил создание поста", call.from_user.id)
    await state.clear()
    await call.message.delete()
    await start_posting(call.message)


@safe_handler("Получение сообщения для поста")
async def get_message(message: types.Message, state: FSMContext):
    """
    Получение первичного сообщения для создания поста.

    Обрабатывает:
    - Текст сообщения (с проверкой длины)
    - Медиа (фото, видео, анимация)
    - Inline кнопки (парсинг в строковый формат)

    Создает запись поста в БД и показывает финальные параметры.

    Производительность:
    - TODO: добавить индексы на posts(admin_id, created_timestamp, status)
    - TODO: фоновая очистка "висячих" постов (драфты > 24ч)

    Args:
        message: Сообщение от пользователя
        state: FSM контекст
    """
    # Получаем выбранные каналы из state
    data = await state.get_data()
    chosen = data.get("chosen", [])
    logger.info(
        "Пользователь %s: ввод контента поста для %d каналов",
        message.from_user.id,
        len(chosen),
    )

    # Проверка длины текста
    message_text_length = len(message.caption or message.text or "")
    logger.debug("Длина текста сообщения: %d символов", message_text_length)
    if message_text_length > 1024:
        logger.warning(
            "Пользователь %s: превышена длина текста (%d > 1024)",
            message.from_user.id,
            message_text_length,
        )
        return await message.answer(text("error_length_text"))

    # Парсинг сообщения в MessageOptions
    dump_message = message.model_dump()
    if dump_message.get("photo"):
        logger.debug("Обнаружено фото: file_id=%s", message.photo[-1].file_id)
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)
    if dump_message.get("video"):
        logger.debug("Обнаружено видео")
    if dump_message.get("animation"):
        logger.debug("Обнаружена анимация")

    message_options = MessageOptions(**dump_message)
    if message_text_length:
        if message_options.text:
            message_options.text = message.html_text
        if message_options.caption:
            message_options.caption = message.html_text

    # Парсинг inline кнопок
    buttons_str = None
    if message.reply_markup and message.reply_markup.inline_keyboard:
        rows = []
        for row in message.reply_markup.inline_keyboard:
            buttons = []
            for button in row:
                if button.url:
                    buttons.append(f"{button.text} — {button.url}")
            if buttons:
                rows.append("|".join(buttons))
        if rows:
            buttons_str = "\n".join(rows)
            logger.debug("Обнаружены inline-кнопки: %d строк", len(rows))

    # Создание поста в БД с выбранными каналами
    try:
        post = await db.post.add_post(
            return_obj=True,
            chat_ids=chosen,
            admin_id=message.from_user.id,
            message_options=message_options.model_dump(),
            buttons=buttons_str,
        )
        logger.info(
            "Пользователь %s: создан пост ID=%s для %d каналов",
            message.from_user.id,
            post.id,
            len(chosen),
        )
    except Exception as e:
        logger.error(
            "Ошибка создания поста для пользователя %s: %s",
            message.from_user.id,
            str(e),
            exc_info=True,
        )
        return await message.answer("❌ Ошибка создания поста. Попробуйте позже.")

    # Обновление состояния
    await state.clear()

    # Оптимизация: конвертируем модель в dict для state
    post_dict = {col.name: getattr(post, col.name) for col in post.__table__.columns}
    logger.debug("Пост сконвертирован в dict: %d полей", len(post_dict))

    await state.update_data(show_more=False, post=post_dict, chosen=chosen)

    # Показываем превью поста с возможностью редактирования
    await answer_post(message, state)
