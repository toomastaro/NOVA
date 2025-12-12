"""
Модуль подтверждения и сохранения поста для ботов.

Содержит логику:
- Подтверждение публикации поста
- Сохранение поста в БД с выбранными ботами и временем
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.bot_post.model import BotPost
from main_bot.database.types import Status
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.states.user import Bots

logger = logging.getLogger(__name__)
from main_bot.utils.error_handler import safe_handler
from main_bot.utils.backup_utils import send_to_backup, edit_backup_message


@safe_handler("Bots Accept")
async def accept(call: types.CallbackQuery, state: FSMContext):
    """
    Confirms and saves the post for bots.
    
    Actions:
    - cancel: returns to the previous step
    - send_time: saves with delayed publication
    - public: immediate publication
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: BotPost = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    send_time: int = data.get("send_time")
    is_edit: bool = data.get("is_edit")
    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

    if temp[1] == "cancel":
        if send_time:
            await state.update_data(send_time=None)
            message_text = text("manage:post_bot:new:send_time").format(
                *data.get("day_values")
            )
            reply_markup = keyboards.choice_send_time_bot_post(day=data.get("day"))
            await state.set_state(Bots.input_send_time)
        else:
            message_text = text("manage:post_bot:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                data.get("available")
            )
            reply_markup = keyboards.finish_bot_post_params(
                obj=post
            )

        if is_edit:
            message_text = text("bot:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            )
            reply_markup = keyboards.manage_remain_bot_post(
                post=data.get("post")
            )

        return await call.message.edit_text(
            message_text,
            reply_markup=reply_markup
        )

    date_values: tuple = data.get("date_values")
    kwargs = {}

    if temp[1] == "send_time":
        kwargs["send_time"] = send_time or post.send_time
    if temp[1] == "public":
        kwargs["status"] = Status.READY

    # Update bot post in DB
    await db.update_bot_post(
        post_id=post.id,
        **kwargs
    )

    # Отправляем в backup если еще не отправлено
    if not post.backup_message_id:
        backup_chat_id, backup_message_id = await send_to_backup(post)
        if backup_chat_id and backup_message_id:
            await db.update_bot_post(
                post_id=post.id,
                backup_chat_id=backup_chat_id,
                backup_message_id=backup_message_id
            )
            # Обновляем локальный объект
            post.backup_chat_id = backup_chat_id
            post.backup_message_id = backup_message_id
    else:
        # Если бэкап уже есть, обновляем его (для редактирования запланированных рассылок)
        await edit_backup_message(post)

    # --- PREVIEW (Copy from Backup) ---
    backup_chat_id = post.backup_chat_id
    backup_message_id = post.backup_message_id

    if backup_chat_id and backup_message_id:
        try:
            # Copy message to user as preview
            await call.bot.copy_message(
                chat_id=call.from_user.id,
                from_chat_id=backup_chat_id,
                message_id=backup_message_id
            )
        except Exception as e:
            logger.error(f"Failed to copy preview from backup for mailing: {e}")
    else:
        logger.warning(f"No backup data for mailing {post.id}, preview not shown.")

    if send_time:
        weekday, day, month, year, _time = date_values
        message_text = text("manage:post_bot:success:date").format(
            _time,
            weekday,
            day,
            month,
            year,
            "\n".join(
                f"{obj.title} (@{obj.username})" for obj in objects
                if obj.id in chosen[:10]
            )
        )
    else:
        message_text = text("manage:post_bot:success:public").format(
            "\n".join(
                f"{obj.title} (@{obj.username})" for obj in objects
                if obj.id in chosen[:10]
            )
        )

    await state.clear()
    await call.message.delete()
    await call.message.answer(
        message_text,
        reply_markup=keyboards.create_finish(
            data="MenuBots"
        )
    )
