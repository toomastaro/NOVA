from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from pathlib import Path
import time
import asyncio

from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.keyboards import keyboards
from main_bot.states.user import AddChannel
from main_bot.utils.functions import get_editors
from main_bot.utils.lang.language import text
from main_bot.utils.logger import logging
from main_bot.utils.error_handler import safe_handler
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


@safe_handler("Posting Channel Choice")
async def choice(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] in ['next', 'back']:
        channels = await db.get_user_channels(
            user_id=call.from_user.id,
            sort_by="posting"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.channels(
                channels=channels,
                remover=int(temp[2])
            )
        )

    if temp[1] == 'cancel':
        await call.message.delete()
        return await start_posting(call.message)

    if temp[1] == 'add':
        await state.set_state(AddChannel.waiting_for_channel)
        
        # Удаляем старое сообщение
        await call.message.delete()
        
        # Отправляем текстовую инструкцию
        return await call.message.answer(
            text=text("channels:add:text"),
            reply_markup=keyboards.add_channel(
                bot_username=(await call.bot.get_me()).username,
            )
        )

    # Store channel_id to state or pass through callback
    channel_id = int(temp[1])
    # Store in FSM for refresh
    await state.update_data(current_channel_id=channel_id)
    
    channel = await db.get_channel_by_chat_id(channel_id)
    editors_str = await get_editors(call, channel.chat_id)
    
    # Получаем информацию о создателе
    try:
        creator = await call.bot.get_chat(channel.admin_id)
        creator_name = f"@{creator.username}" if creator.username else creator.full_name
    except:
        creator_name = "Неизвестно"
    
    # Получаем количество подписчиков
    try:
        members_count = await call.bot.get_chat_member_count(channel.chat_id)
    except:
        members_count = "N/A"
    
    # Форматируем дату добавления
    from datetime import datetime
    created_date = datetime.fromtimestamp(channel.created_timestamp)
    created_str = created_date.strftime("%d.%m.%Y в %H:%M")
    
    # Статус подписки
    if channel.subscribe:
        from datetime import datetime
        sub_date = datetime.fromtimestamp(channel.subscribe)
        subscribe_str = f"✅ Активна до {sub_date.strftime('%d.%m.%Y')}"
    else:
        subscribe_str = "❌ Не активна"

    # Получаем статус помощника
    try:
        # Находим привязанного клиента
        client_row = await db.get_my_membership(channel.chat_id)
        
        can_post = False
        can_stories = False
        mt_client = None
        
        if client_row:
             if client_row[0].is_admin:
                 pass
             
             can_post = client_row[0].is_admin
             can_stories = client_row[0].can_post_stories
             mt_client = client_row[0].client
        
        status_post = "✅" if can_post else "❌"
        status_story = "✅" if can_stories else "❌"
        # Mailing depends on posting
        status_mail = "✅" if can_post else "❌"
        
        # Check welcome messages
        hello_msgs = await db.get_hello_messages(channel.chat_id, active=True)
        status_welcome = "✅" if hello_msgs else "❌"
        
        if mt_client:
            import html
            clean_alias = mt_client.alias.replace("👤", "").strip()
            if " " in clean_alias:
                assistant_name = html.escape(clean_alias)
            else:
                assistant_name = f"@{html.escape(clean_alias)}"
            assistant_desc = "<i>Назначенный помощник для этого канала</i>"
            assistant_header = f"🤖 <b>Статус помощника:</b> {assistant_name}\n{assistant_desc}\n"
        else:
            assistant_header = "🤖 <b>Статус помощника:</b> Не назначен\n"
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса помощника: {e}")
        status_post = "❓"
        status_story = "❓"
        status_mail = "❓"
        status_welcome = "❓"
        assistant_header = "🤖 <b>Статус помощника:</b> Ошибка\n"

    info_text = (
        f"📺 <b>Информация о канале</b>\n\n"
        f"🏷 <b>Название:</b> {channel.title}\n"
        f"👑 <b>Владелец:</b> {creator_name}\n"
        f"👥 <b>Подписчиков:</b> {members_count}\n"
        f"📅 <b>Добавлен:</b> {created_str}\n"
        f"💎 <b>Подписка:</b> {subscribe_str}\n\n"
        f"🛠 <b>Редакторы:</b>\n{editors_str}\n\n"
        f"{assistant_header}"
        f"├ 📝 Постинг: {status_post}\n"
        f"├ 📸 Истории: {status_story}\n"
        f"├ 📨 Рассылка: {status_mail}\n"
        f"└ 👋 Приветствие: {status_welcome}"
    )

    await call.message.edit_text(
        text=info_text,
        reply_markup=keyboards.manage_channel(),
        parse_mode="HTML"
    )


@safe_handler("Posting Channel Cancel")
async def cancel(call: types.CallbackQuery):
    channels = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )
    return await call.message.edit_text(
        text=text("channels_text"),
        reply_markup=keyboards.channels(
            channels=channels,
        )
    )


@safe_handler("Posting Manage Channel")
async def manage_channel(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] == 'delete':
        return await call.answer(
            text('delete_channel'),
            show_alert=True
        )
    
    if temp[1] == 'cancel':
        return await cancel(call)
        
    if temp[1] == 'invite_assistant':
        data = await state.get_data()
        channel_id = data.get("current_channel_id")
        
        if not channel_id:
             await call.answer("Ошибка: выберите канал заново", show_alert=True)
             return await cancel(call)

        channel = await db.get_channel_by_chat_id(channel_id)
        if not channel:
            await call.answer("Канал не найден", show_alert=True)
            return
            
        # Get client
        client_row = await db.get_my_membership(channel.chat_id)
        if not client_row or not client_row[0].client:
             await call.answer("❌ Нет назначенного помощника", show_alert=True)
             return
             
        mt_client = client_row[0].client
        session_path = Path(mt_client.session_path)
        
        if not session_path.exists():
            await call.answer("❌ Файл сессии не найден", show_alert=True)
            return

        await call.answer("⏳ Создаю ссылку и добавляю помощника...", show_alert=False)
        
        try:
            # 1. Create Invite Link
            invite = await call.bot.create_chat_invite_link(
                chat_id=channel.chat_id,
                name="Nova Assistant",
                creates_join_request=False
            )
            
            # 2. Join process
            success = False
            async with SessionManager(session_path) as manager:
                try:
                    success = await manager.join(invite.invite_link, max_attempts=5)
                    # Update username if possible
                    me = await manager.me()
                    if me and me.username:
                         await db.update_mt_client(mt_client.id, alias=me.username)
                         mt_client.alias = me.username # Update local obj for display
                except Exception as e:
                    logger.error(f"Join error: {e}")
            
            # 3. Handle Result
            if success:
                import html
                username = mt_client.alias.replace("@", "") # Clean just in case
                
                msg = (
                    f"✅ <b>Помощник успешно добавился в канал!</b>\n\n"
                    f"Теперь вам нужно выдать ему права администратора.\n\n"
                    f"📋 <b>Инструкция:</b>\n"
                    f"1. Зайдите в настройки канала -> Администраторы -> Добавить администратора.\n"
                    f"2. В поиске введите: @{html.escape(username)}\n"
                    f"3. Выберите этого пользователя и выдайте следующие права:\n"
                    f"   ✅ Публикация сообщений\n"
                    f"   ✅ Редактирование сообщений\n"
                    f"   ✅ Удаление сообщений\n"
                    f"   ✅ Публикация историй\n"
                    f"   ✅ Редактирование историй\n"
                    f"   ✅ Удаление историй\n\n"
                    f"После выдачи прав нажмите кнопку <b>«Проверить права помощника»</b>."
                )
                await call.message.edit_text(text=msg, parse_mode="HTML", reply_markup=keyboards.manage_channel("ManageChannelPost"))
                
            else:
                await call.answer("⚠️ Не удалось добавить помощника (5 попыток). Попробуйте позже.", show_alert=True)
                
        except Exception as e:
            logger.error(f"Invite assistant error: {e}")
            await call.answer(f"❌ Ошибка: удостоверьтесь, что бот - админ ({e})", show_alert=True)
        return
            
    if temp[1] == 'check_permissions':
        data = await state.get_data()
        channel_id = data.get("current_channel_id")
        
        if not channel_id:
             # Fallback attempt to find channel ID from previous step if state lost? 
             # Or just error.
             # Actually, choice stores channel_id in DB selection usually.
             # Let's try to get it from context or just fail
             # Try to get from call.message text maybe? No.
             # Let's hope state works. If not, user has to re-select channel.
             await call.answer("Ошибка: выберите канал заново", show_alert=True)
             return await cancel(call)

        channel = await db.get_channel_by_chat_id(channel_id)
        if not channel:
            await call.answer("Канал не найден", show_alert=True)
            return
            
        await call.answer("⏳ Проверяем права...", show_alert=False)
        
        # 1. Get client
        client_row = await db.get_my_membership(channel.chat_id)
        
        if not client_row:
             # No client assigned? Try to assign one.
             from main_bot.handlers.user.set_resource import set_channel_session
             await set_channel_session(channel.chat_id)
             # Retry fetch
             client_row = await db.get_my_membership(channel.chat_id)
        
        if not client_row:
             await call.answer("❌ Ошибка: нет назначенного помощника", show_alert=True)
             return

        mt_client = client_row[0].client
        
        if not mt_client:
             await call.answer("❌ Ошибка клиента", show_alert=True)
             return
             
        # 2. Check permissions
        session_path = Path(mt_client.session_path)
        if not session_path.exists():
            await call.answer("❌ Ошибка сессии помощника", show_alert=True)
            return

        async with SessionManager(session_path) as manager:
             perms = await manager.check_permissions(channel.chat_id)
        
        if perms.get("error"):
            error_code = perms['error']
            if error_code == "USER_NOT_PARTICIPANT":
                error_msg = "Помощник не найден в участниках канала"
            else:
                error_msg = f"Ошибка: {error_code}"
            
            await call.answer(f"❌ {error_msg}", show_alert=True)
            return
            
        # 3. Update DB
        is_admin = perms.get("is_admin", False)
        can_stories = perms.get("can_post_stories", False)
        
        # Update client alias if username is available
        me = perms.get("me")
        if me and me.username:
             await db.update_mt_client(mt_client.id, alias=me.username)
        
        await db.set_membership(
            client_id=mt_client.id,
            channel_id=channel.chat_id,
            is_member=perms.get("is_member", False),
            is_admin=is_admin,
            can_post_stories=can_stories,
            last_joined_at=int(time.time()),
            preferred_for_stats=client_row[0].preferred_for_stats # Keep existing preference
        )
        
        # 4. Refresh view
        # We need to reconstruct call.data to call choice again? 
        # Or just manually call choice logic.
        # Construct fake data to call choice with correct ID
        call.data = f"ChoicePostChannel|{channel.chat_id}|0"
        await choice(call, state)
        
        if is_admin and (can_stories or not perms.get("can_post_stories")): 
            # Notify success
             await call.answer("✅ Права успешно обновлены!", show_alert=True)
        else:
             await call.answer("⚠️ Не все права выданы. Проверьте настройки админа.", show_alert=True)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoicePostChannel")
    router.callback_query.register(cancel, F.data.split("|")[0] == "BackAddChannelPost")
    router.callback_query.register(manage_channel, F.data.split("|")[0] == "ManageChannelPost")
    return router
