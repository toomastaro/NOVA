from aiogram import types, F, Router
from aiogram.enums import ChatMemberStatus

from main_bot.database.db import db
from main_bot.utils.functions import create_emoji
from main_bot.utils.lang.language import text


async def set_admins(call: types.ChatMemberUpdated, chat_id: int, emoji_id: str):
    admins = await call.bot.get_chat_administrators(chat_id)
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
            title=call.chat.title,
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

        chat = await call.bot.get_chat(chat_id)
        if chat.photo:
            photo_bytes = await call.bot.download(chat.photo.big_file_id)
        else:
            photo_bytes = None

        emoji_id = await create_emoji(call.from_user.id, photo_bytes)
        await set_admins(call, chat_id, emoji_id)

        message_text = text('success_add_channel').format(
            emoji_id,
            call.chat.title
        )
    else:
        if not channel:
            return

        await db.delete_channel(
            chat_id=chat_id
        )

        message_text = text('success_delete_channel').format(
            channel.emoji_id,
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


def hand_add():
    router = Router()
    router.my_chat_member.register(set_channel, F.chat.type == 'channel')
    router.my_chat_member.register(set_active, F.chat.type == 'private')
    router.chat_member.register(set_admin, F.chat.type == 'channel')
    return router
