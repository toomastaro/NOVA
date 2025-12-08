"""
Модуль подтверждения и сохранения поста.

Содержит логику:
- Подтверждение публикации поста
- Сохранение поста в БД с выбранными каналами и временем
- Отправка в backup канал
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.utils.lang.language import text
from main_bot.utils.backup_utils import send_to_backup
from main_bot.keyboards import keyboards
from main_bot.states.user import Posting
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Posting Accept")
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
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Post = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    send_time: int = data.get("send_time")
    is_edit: bool = data.get("is_edit")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )

    # Отмена - возврат к предыдущему шагу
    if temp[1] == "cancel":
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
                    text("resource_title").format(obj.title) for obj in objects
                    if obj.chat_id in chosen[:10]
                )
            )
            reply_markup = keyboards.finish_params(
                obj=post
            )
        
        # Если редактируем опубликованный пост
        if is_edit:
            message_text = text("post:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            )
            reply_markup = keyboards.manage_remain_post(
                post=data.get("post"),
                is_published=data.get("is_published")
            )

        return await call.message.edit_text(
            message_text,
            reply_markup=reply_markup
        )

    # Подготовка данных для сохранения
    date_values: tuple = data.get("date_values")
    kwargs = {"chat_ids": chosen}

    if temp[1] == "send_time":
        kwargs["send_time"] = send_time or post.send_time
    if temp[1] == "public":
        kwargs["send_time"] = None

    logger.info(f"Accepting post {post.id}. Chosen channels: {chosen}")

    # Обновляем пост в БД
    await db.update_post(
        post_id=post.id,
        **kwargs
    )

    # Отправляем в backup если еще не отправлено
    if not post.backup_message_id:
        backup_chat_id, backup_message_id = await send_to_backup(post)
        if backup_chat_id and backup_message_id:
            await db.update_post(
                post_id=post.id,
                backup_chat_id=backup_chat_id,
                backup_message_id=backup_message_id
            )

    # Формируем сообщение об успехе
    if send_time:
        weekday, day, month, year, _time = date_values
        message_text = text("manage:post:success:date").format(
            f"{day} {month} {year} {_time} ({weekday})",
            "\n".join(
                text("resource_title").format(obj.title) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )
    else:
        message_text = text("manage:post:success:public").format(
            "\n".join(
                text("resource_title").format(obj.title) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )

    # Очищаем состояние и показываем успех
    await state.clear()
    await call.message.delete()
    await call.message.answer(
        message_text,
        reply_markup=keyboards.create_finish()
    )
