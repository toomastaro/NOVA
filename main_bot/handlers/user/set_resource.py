import asyncio
import logging
from aiogram import types, F, Router
from aiogram import types, F, Router, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext

from main_bot.states.user import AddChannel
from main_bot.handlers.user.menu import start_posting

from main_bot.database.db import db
from main_bot.utils.functions import create_emoji, background_join_channel
from main_bot.utils.lang.language import text

logger = logging.getLogger(__name__)


async def set_admins(bot: Bot, chat_id: int, chat_title: str, emoji_id: str, user_id: int = None):
    """
    Добавляет администраторов канала в базу данных.
    Если бот еще не добавлен в канал, добавляет только пользователя, который добавил бота.
    """
    try:
        admins = await bot.get_chat_administrators(chat_id)
    except Exception as e:
        logger.error(f"Ошибка получения администраторов канала {chat_id}: {e}")
        # Если не можем получить список админов, добавляем хотя бы того, кто добавил бота
        if user_id:
            await db.add_channel(
                chat_id=chat_id,
                title=chat_title,
                admin_id=user_id,
                emoji_id=emoji_id
            )
        return
    
    for admin in admins:
        if admin.user.is_bot:
            continue

        if not isinstance(admin, types.ChatMemberOwner):
            rights = {
                admin.can_post_messages,
                admin.can_edit_messages,
                admin.can_delete_messages,
                admin.can_post_stories,
                admin.can_edit_stories,
                admin.can_delete_stories
            }
            if False in rights:
                continue

        await db.add_channel(
            chat_id=chat_id,
            title=chat_title,
            admin_id=admin.user.id,
            emoji_id=emoji_id
        )


async def set_channel(call: types.ChatMemberUpdated):
    chat_id = call.chat.id
    channel = await db.get_channel_by_chat_id(
        chat_id=chat_id
    )

    if call.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        if channel:
            return

        # Обработка ошибок при получении информации о канале
        try:
            chat = await call.bot.get_chat(chat_id)
            chat_title = chat.title
            photo = chat.photo
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале {chat_id}: {e}")
            chat_title = call.chat.title
            photo = None

        # Загрузка фото канала
        if photo:
            try:
                photo_bytes = await call.bot.download(photo.big_file_id)
            except Exception as e:
                logger.error(f"Ошибка загрузки фото канала {chat_id}: {e}")
                photo_bytes = None
        else:
            photo_bytes = None


        emoji_id = await create_emoji(call.from_user.id, photo_bytes)
        await set_admins(call.bot, chat_id, chat_title, emoji_id, user_id=call.from_user.id)

        # Запуск фоновой задачи для добавления клиента в канал
        asyncio.create_task(background_join_channel(chat_id, user_id=call.from_user.id))

        message_text = text('success_add_channel').format(
            chat_title
        )
    else:
        if not channel:
            return

        await db.delete_channel(
            chat_id=chat_id
        )

        message_text = text('success_delete_channel').format(
            channel.title
        )


    if call.from_user.is_bot:
        return

    await call.bot.send_message(
        chat_id=call.from_user.id,
        text=message_text
    )


async def set_admin(call: types.ChatMemberUpdated):
    if call.new_chat_member.user.is_bot:
        return

    chat_id = call.chat.id
    
    # Track subscription for ad purchases if user joined via invite link
    if call.new_chat_member.status == ChatMemberStatus.MEMBER and call.invite_link:
        try:
            await db.process_join_event(
                channel_id=chat_id,
                user_id=call.new_chat_member.user.id,
                invite_link=call.invite_link.invite_link
            )
        except Exception:
            # Silently ignore errors in subscription tracking
            pass
    
    if call.new_chat_member.status == ChatMemberStatus.MEMBER:
        await db.delete_channel(
            chat_id=chat_id,
            user_id=call.new_chat_member.user.id
        )

    if call.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        admin = call.new_chat_member
        rights = {
            admin.can_post_messages,
            admin.can_edit_messages,
            admin.can_delete_messages,
            admin.can_post_stories,
            admin.can_edit_stories,
            admin.can_delete_stories
        }
        if False in rights:
            return await db.delete_channel(
                chat_id=chat_id,
                user_id=admin.user.id
            )

        channel = await db.get_channel_by_chat_id(chat_id)
        await db.add_channel(
            chat_id=chat_id,
            admin_id=admin.user.id,
            title=call.chat.title,
            subscribe=channel.subscribe,
            session_path=channel.session_path,
            emoji_id=channel.emoji_id,
            created_timestamp=channel.created_timestamp
        )


async def set_active(call: types.ChatMemberUpdated):
    await db.update_user(
        user_id=call.from_user.id,
        is_active=call.new_chat_member.status != ChatMemberStatus.KICKED
    )


async def manual_add_channel(message: types.Message, state: FSMContext):
    chat_id = None
    
    if message.forward_from_chat and message.forward_from_chat.type == 'channel':
        chat_id = message.forward_from_chat.id
    else:
        text_val = message.text.strip()
        if text_val.startswith('@') or 't.me/' in text_val:
            try:
                # Extract username if it's a link
                if 't.me/' in text_val:
                    username = text_val.split('t.me/')[-1].split('/')[0]
                    if not username.startswith('@'):
                        username = f"@{username}"
                else:
                    username = text_val
                
                chat = await message.bot.get_chat(username)
                if chat.type == 'channel':
                    chat_id = chat.id
            except Exception:
                pass
    
    if not chat_id:
        await message.answer("Не удалось определить канал. Пожалуйста, перешлите сообщение из канала или отправьте ссылку/юзернейм канала (например @channel).")
        return

    # Check if bot is admin
    try:
        bot_member = await message.bot.get_chat_member(chat_id, (await message.bot.get_me()).id)
        if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
            await message.answer("Бот не является администратором этого канала. Пожалуйста, добавьте бота в администраторы и попробуйте снова.")
            return
            
        # Check if user is admin
        user_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
        if user_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
             await message.answer("Вы не являетесь администратором этого канала.")
             return

        # Add channel logic
        try:
            chat = await message.bot.get_chat(chat_id)
            chat_title = chat.title
            photo = chat.photo
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале {chat_id}: {e}")
            # Получаем информацию из user_member
            try:
                chat_info = await message.bot.get_chat(chat_id)
                chat_title = chat_info.title
                photo = None
            except:
                chat_title = f"Channel {chat_id}"
                photo = None
        
        # Загрузка фото канала
        if photo:
            try:
                photo_bytes = await message.bot.download(photo.big_file_id)
            except Exception as e:
                logger.error(f"Ошибка загрузки фото канала {chat_id}: {e}")
                photo_bytes = None
        else:
            photo_bytes = None

        emoji_id = await create_emoji(message.from_user.id, photo_bytes)
        
        await set_admins(message.bot, chat_id, chat_title, emoji_id, user_id=message.from_user.id)
        
        # Запуск фоновой задачи для добавления клиента в канал
        asyncio.create_task(background_join_channel(chat_id, user_id=message.from_user.id))
            
        msg = text('success_add_channel').format(chat_title)
        await message.answer(msg)
        await state.clear()
        await start_posting(message)

    except Exception as e:
        await message.answer(f"Произошла ошибка при добавлении канала: {e}")


def hand_add():
    router = Router()
    router.my_chat_member.register(set_channel, F.chat.type == 'channel')
    router.my_chat_member.register(set_active, F.chat.type == 'private')
    router.chat_member.register(set_admin, F.chat.type == 'channel')
    
    router.message.register(manual_add_channel, AddChannel.waiting_for_channel)
    
    return router
