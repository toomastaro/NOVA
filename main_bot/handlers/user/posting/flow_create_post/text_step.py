"""
Модуль обработки ввода текста/сообщения для поста.

Содержит логику:
- Получение первичного сообщения от пользователя
- Отмена создания поста
- Парсинг текста, медиа и кнопок из сообщения
- Создание бекапа поста в резервном канале
"""

import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.utils.message_utils import answer_post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import MessageOptions
from main_bot.utils.media_manager import MediaManager
from main_bot.utils.post_assembler import PostAssembler
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler(
    "Отмена создания поста"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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


@safe_handler(
    "Получение сообщения для поста"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def get_message(message: types.Message, state: FSMContext):
    """
    Получение первичного сообщения для создания поста.

    Обрабатывает текст, медиа и inline-кнопки из сообщения пользователя.
    Создает запись поста в БД и формирует превью.

    Алгоритм:
    1. Проверка длины текста.
    2. Парсинг медиа-вложений (фото, видео, анимация).
    3. Парсинг inline-кнопок в строковый формат.
    4. Создание записи поста в БД.
    5. Создание резервной копии поста (бекапа) в техническом канале.
    6. Обновление состояния FSM и отображение меню управления постом.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
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
    # Лимит зависит от типа контента:
    # - Только текст: 4096 символов
    # - Медиа (фото/видео): 4096 символов (использование невидимых ссылок)
    # - Только текст: 4096 символов

    is_media = bool(
        message.photo or message.video or message.animation or message.document
    )
    limit = 4096

    message_text_length = len(message.caption or message.text or "")
    logger.debug(
        "Длина текста сообщения: %d символов (лимит: %d)", message_text_length, limit
    )

    if message_text_length > limit:
        logger.warning(
            "Пользователь %s: превышена длина текста (%d > %d)",
            message.from_user.id,
            message_text_length,
            limit,
        )
        return await message.answer(text("error_length_text").format(limit))

    # Парсинг сообщения в MessageOptions
    final_html = message.html_text

    # 1. Адаптивная трансформация
    logger.info(f"🔄 Первичная трансформация контента (User: {message.from_user.id})")

    # Решаем, как шлем медиа (file_id vs URL)
    media_value, is_invisible, current_media_type = await MediaManager.process_media_for_post(
        message, final_html
    )

    # Сборка inline кнопок (для ассамблера)
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

    # Собираем MessageOptions через ассамблер
    assembled_options = PostAssembler.assemble_message_options(
        html_text=final_html,
        media_type=current_media_type,
        media_value=media_value,
        is_invisible=is_invisible,
        buttons=buttons_str,
        reaction=None,  # Пока нет реакций
    )

    # Создаем финальный объект для БД
    message_options = MessageOptions(**assembled_options)

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
        return await message.answer(text("error_post_create"))

    # Обновление состояния
    await state.clear()

    # Оптимизация: конвертируем модель в dict для state
    post_dict = {col.name: getattr(post, col.name) for col in post.__table__.columns}
    logger.debug("Пост сконвертирован в dict: %d полей", len(post_dict))

    await state.update_data(show_more=False, post=post_dict, chosen=chosen)

    # Показываем превью поста с возможностью редактирования
    from main_bot.keyboards.common import Reply

    await message.answer(text("content_accepted"), reply_markup=Reply.menu(message.from_user.id))

    await answer_post(message, state)
