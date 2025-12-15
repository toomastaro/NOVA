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
    objects = await db.channel.get_user_channels(
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
        kwargs["send_time"] = int(time.time()) - 1

    logger.info(f"Accepting post {post.id}. Chosen channels: {chosen}")

    # Обновляем пост в БД
    await db.post.update_post(
        post_id=post.id,
        **kwargs
    )

    # Отправляем в backup если еще не отправлено
    if not post.backup_message_id:
        backup_chat_id, backup_message_id = await send_to_backup(post)
        if backup_chat_id and backup_message_id:
            await db.post.update_post(
                post_id=post.id,
                backup_chat_id=backup_chat_id,
                backup_message_id=backup_message_id
            )

    # --- OTLOG IMPLEMENTATION ---
    from datetime import datetime
    import html

    # 1. Preview (Copy from Backup)
    backup_chat_id = post.backup_chat_id or (kwargs.get("backup_chat_id") if 'kwargs' in locals() else None)
    backup_message_id = post.backup_message_id or (kwargs.get("backup_message_id") if 'kwargs' in locals() else None)

    if not backup_chat_id and 'backup_chat_id' in locals():
         backup_chat_id = locals()['backup_chat_id']
    if not backup_message_id and 'backup_message_id' in locals():
         backup_message_id = locals()['backup_message_id']
         
    if backup_chat_id and backup_message_id:
        try:
            await call.bot.copy_message(
                chat_id=call.from_user.id,
                from_chat_id=backup_chat_id,
                message_id=backup_message_id
            )
        except Exception as e:
            logging.error(f"Failed to copy preview from backup: {e}")
            from main_bot.utils.message_utils import answer_post
            await answer_post(call.message, state, from_edit=True)
    else:
        from main_bot.utils.message_utils import answer_post
        await answer_post(call.message, state, from_edit=True)


    # 2. OTLOG Text Construction
    
    # Status & Date
    if send_time and send_time > time.time():
        status = "🟡 <b>Запланировано</b>"
        dt = datetime.fromtimestamp(send_time)
        date_str = dt.strftime('%d.%m.%Y %H:%M')
    else:
        status = "🟢 <b>Опубликовано</b>"
        dt = datetime.fromtimestamp(time.time())
        date_str = dt.strftime('%d.%m.%Y %H:%M')

    # Delete Time
    delete_str = ""
    if post.delete_time:
        if post.delete_time < 3600:
             time_display = f"{int(post.delete_time / 60)} мин."
        else:
             time_display = f"{int(post.delete_time / 3600)} ч."
        delete_str = f"🗑 <b>Удаление через:</b> {time_display}"
    
    # CPM Price
    cpm_str = ""
    if post.cpm_price:
        cpm_str = f"💸 <b>CPM:</b> {int(post.cpm_price)}"

    # Channels List
    # Ensure quotes and HTML safety
    channels_block = ""
    if chosen:
        channels_str = "\n".join(
            f"{html.escape(obj.title)}" for obj in objects
            if obj.chat_id in chosen
        )
        channels_block = f"<blockquote expandable>{channels_str}</blockquote>"

    otlog_text = (
        f"📊 <b>Отчет о публикации</b>\n\n"
        f"Статус: {status}\n"
        f"📅 <b>Дата:</b> {date_str}\n" 
    )
    if delete_str:
        otlog_text += f"{delete_str}\n"
    if cpm_str:
        otlog_text += f"{cpm_str}\n"
    
    if channels_block:
        otlog_text += (
            f"\n📢 <b>Каналы:</b>\n"
            f"{channels_block}"
        )

    # 3. Send OTLOG and Menu
    await state.clear()
    await call.message.delete()
    
    # Send OTLOG
    await call.message.answer(
        otlog_text,
        reply_markup=keyboards.posting_menu(),
        parse_mode="HTML",
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )
