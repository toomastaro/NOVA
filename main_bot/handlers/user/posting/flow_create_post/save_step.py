"""
Модуль подтверждения и сохранения поста.

Содержит логику:
- Подтверждение публикации поста
- Сохранение поста в БД с выбранными каналами и временем
- Отправка в backup канал
"""

import logging
import time
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.utils.lang.language import text
from main_bot.utils.backup_utils import send_to_backup
from main_bot.keyboards import keyboards
from main_bot.keyboards.posting import safe_post_from_dict
from main_bot.states.user import Posting
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Подтверждение публикации")
async def accept(call: types.CallbackQuery, state: FSMContext):
    """
    Подтверждение и сохранение поста.

    Действия:
    - cancel: возврат к предыдущему шагу
    - send_time: сохранение с отложенной публикацией
    - public: немедленная публикация

    Сохраняет пост в БД с выбранными каналами и временем отправки.
    Отправляет копию поста в backup канал.

    Args:
        call: Callback query с действием
        state: FSM контекст
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post = safe_post_from_dict(data.get("post"))
    chosen: list = data.get("chosen", post.chat_ids)
    send_time: int = data.get("send_time")
    is_edit: bool = data.get("is_edit")
    objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="posting"
    )

    # Отмена - возврат к предыдущему шагу
    if temp[1] == "cancel":
        logger.info(
            "Пользователь %s отменил подтверждение публикации", call.from_user.id
        )
        if send_time:
            # Возврат к вводу времени
            await state.update_data(send_time=None)
            message_text = text("manage:post:new:send_time")
            reply_markup = keyboards.back(data="BackSendTimePost")
            await state.set_state(Posting.input_send_time)
        else:
            # Возврат к финальным параметрам
            message_text = text("manage:post:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
            )
            reply_markup = keyboards.finish_params(obj=post)

        # Если редактируем опубликованный пост
        if is_edit:
            message_text = text("post:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title,
            )
            reply_markup = keyboards.manage_remain_post(
                post=data.get("post"), is_published=data.get("is_published")
            )

        return await call.message.edit_text(message_text, reply_markup=reply_markup)

    # Подготовка данных для сохранения
    kwargs = {"chat_ids": chosen}

    post_type_log = (
        "scheduled"
        if temp[1] == "send_time" or (send_time and send_time > time.time())
        else "public"
    )

    if temp[1] == "send_time":
        kwargs["send_time"] = send_time or post.send_time
    if temp[1] == "public":
        kwargs["send_time"] = int(time.time()) - 1

    logger.info(
        "Пользователь %s: сохранение поста ID=%s, тип=%s, каналов=%d",
        call.from_user.id,
        post.id,
        post_type_log,
        len(chosen),
    )

    # Обновляем пост в БД
    await db.post.update_post(post_id=post.id, **kwargs)

    # Отправляем в backup если еще не отправлено
    if not post.backup_message_id:
        try:
            backup_chat_id, backup_message_id = await send_to_backup(post)
            if backup_chat_id and backup_message_id:
                await db.post.update_post(
                    post_id=post.id,
                    backup_chat_id=backup_chat_id,
                    backup_message_id=backup_message_id,
                )
        except Exception as e:
            logger.error(
                "Ошибка создания fallback-бекапа для поста %s: %s",
                post.id,
                e,
                exc_info=True,
            )

    # --- Реализация OTLOG (отчет) ---
    from datetime import datetime
    import html

    # 1. Превью (Копия из бекапа)
    # Пытаемся получить актуальные данные о бекапе (могли обновиться выше)
    current_post = await db.post.get_post(post.id)
    backup_chat_id = current_post.backup_chat_id
    backup_message_id = current_post.backup_message_id

    preview_sent = False
    if backup_chat_id and backup_message_id:
        try:
            # Генерируем клавиатуру для превью, чтобы кнопки точно были
            reply_markup = keyboards.post_kb(post=post)

            await call.bot.copy_message(
                chat_id=call.from_user.id,
                from_chat_id=backup_chat_id,
                message_id=backup_message_id,
                reply_markup=reply_markup,
            )
            preview_sent = True
        except Exception as e:
            logger.warning(
                "Не удалось скопировать превью из бэкапа (chat=%s, msg=%s): %s. Генерируем локально.",
                backup_chat_id,
                backup_message_id,
                e,
            )

    if not preview_sent:
        from main_bot.utils.message_utils import answer_post

        try:
            await answer_post(call.message, state, from_edit=True)
        except Exception as e:
            logger.error(
                "Ошибка локальной генерации превью для поста %s: %s",
                post.id,
                e,
                exc_info=True,
            )

    # 2. Формирование текста отчета (OTLOG)

    # Статус и дата
    use_send_time = kwargs.get("send_time", post.send_time)

    if use_send_time and use_send_time > time.time():
        status = text("post:report:status:scheduled")
        dt = datetime.fromtimestamp(use_send_time)
        date_str = dt.strftime("%d.%m.%Y %H:%M")
    else:
        status = text("post:report:status:published")
        dt = datetime.fromtimestamp(time.time())
        date_str = dt.strftime("%d.%m.%Y %H:%M")

    # Время удаления
    delete_str = ""
    if post.delete_time:
        if post.delete_time < 3600:
            time_display = f"{int(post.delete_time / 60)} мин."
        else:
            time_display = f"{int(post.delete_time / 3600)} ч."
        delete_str = text("post:report:delete_in").format(time_display)

    # Цена CPM
    cpm_str = ""
    if post.cpm_price:
        cpm_str = text("post:report:cpm").format(int(post.cpm_price))

    # Список каналов
    channels_block = ""
    if chosen:
        channels_str = "\n".join(
            f"{html.escape(obj.title)}" for obj in objects if obj.chat_id in chosen
        )
        channels_block = text("post:report:channels").format(
            f"<blockquote expandable>{channels_str}</blockquote>"
        )

    otlog_text = (
        f"{text('post:report:title')}\n\n"
        f"{status}\n"
        f"{text('post:report:date').format(date_str)}\n"
    )
    if delete_str:
        otlog_text += f"{delete_str}\n"
    if cpm_str:
        otlog_text += f"{cpm_str}\n"

    if channels_block:
        otlog_text += f"\n{channels_block}"

    # 3. Отправка отчета и меню
    await state.clear()
    await call.message.delete()

    # Отправка OTLOG
    await call.message.answer(
        otlog_text,
        reply_markup=None,  # Убрали кнопки по просьбе пользователя (отдельная реализация для отчета)
        parse_mode="HTML",
        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
    )
