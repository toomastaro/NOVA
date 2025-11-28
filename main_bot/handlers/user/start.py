from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.enums import ChatMemberStatus

from config import settings
from main_bot.database.db import db
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.functions import create_emoji
from main_bot.utils.lang.language import text
from main_bot.utils.middlewares import StartMiddle


async def handle_add_channel(message: types.Message, chat_id: int):
    """
    Обрабатывает добавление канала, когда бот уже находится в канале
    """
    try:
        # Проверяем, не добавлен ли уже канал
        channel = await db.get_channel_by_chat_id(chat_id=chat_id)
        user_channel = await db.get_channel_admin_row(chat_id=chat_id, user_id=message.from_user.id)

        if user_channel:
            await message.answer("ℹ️ Канал уже добавлен в ваш список")
            return

        # Проверяем, является ли бот администратором канала
        try:
            bot_member = await message.bot.get_chat_member(chat_id, message.bot.id)
            if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                await message.answer("❌ Бот должен быть администратором в канале")
                return
        except Exception:
            await message.answer("❌ Не удалось проверить статус бота в канале")
            return

        # Проверяем, является ли пользователь администратором канала
        try:
            user_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
            if user_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await message.answer("❌ Вы должны быть администратором канала")
                return

            # Проверяем необходимые права (только для обычных админов)
            if user_member.status == ChatMemberStatus.ADMINISTRATOR:
                rights = {
                    user_member.can_post_messages,
                    user_member.can_edit_messages,
                    user_member.can_delete_messages,
                }
                if False in rights:
                    await message.answer("❌ У вас недостаточно прав в канале (нужны права на посты, редактирование и удаление)")
                    return
        except Exception:
            await message.answer("❌ Не удалось проверить ваш статус в канале")
            return

        # Получаем информацию о канале
        try:
            chat = await message.bot.get_chat(chat_id)
        except Exception:
            await message.answer("❌ Не удалось получить информацию о канале")
            return

        # Создаем emoji для канала (если его еще нет)
        if channel:
            emoji_id = channel.emoji_id
        else:
            if chat.photo:
                photo_bytes = await message.bot.download(chat.photo.big_file_id)
            else:
                photo_bytes = None
            emoji_id = await create_emoji(message.from_user.id, photo_bytes)

        # Добавляем канал в базу
        await db.add_channel(
            chat_id=chat_id,
            title=chat.title,
            admin_id=message.from_user.id,
            emoji_id=emoji_id,
        )

        message_text = text("success_add_channel").format(emoji_id, chat.title)
        await message.answer(message_text)

    except Exception as e:
        print(f"Error in handle_add_channel: {e}")
        await message.answer("❌ Произошла ошибка при добавлении канала")



async def start(message: types.Message):
    # Проверяем, есть ли аргументы команды (например, ID канала)
    if message.text and len(message.text.split()) > 1:
        args = message.text.split()[1:]

        # Если это команда для добавления канала
        if len(args) == 1 and args[0].lstrip('-').isdigit():
            await handle_add_channel(message, int(args[0]))
            return

    await message.answer(
        text("start_text") + f"\n\n<code>v{settings.VERSION}</code>",
        reply_markup=keyboards.menu(),
    )


def hand_add():
    router = Router()
    router.message.middleware(StartMiddle())
    router.message.register(start, CommandStart())
    return router
