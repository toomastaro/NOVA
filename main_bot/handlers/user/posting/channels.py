import logging
from aiogram import F, Router, types
from aiogram.enums import ChatMemberStatus

from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.functions import get_editors, create_emoji
from main_bot.utils.lang.language import text

logger = logging.getLogger(__name__)


async def scan_existing_channels(call: types.CallbackQuery):
    """
    Сканирование каналов, где бот уже является администратором,
    но которые не добавлены в базу
    """
    try:
        await call.message.edit_text("🔍 Поиск каналов...")

        instruction_text = (
            "🔍 <b>Поиск каналов</b>\n\n"
            "Отправьте ID канала, где я уже админ\n\n"
            "📌 <b>Как найти ID канала:</b>\n"
            "1. Откройте канал в Telegram\n"
            "2. Нажмите на название канала сверху\n"
            "3. В ссылке будет ID (например: t.me/c/1234567890/...)\n"
            "4. Скопируйте число после /c/\n\n"
            "Отправьте мне это число:"
        )

        await call.message.edit_text(
            instruction_text,
            parse_mode="HTML",
            reply_markup=keyboards.back("BackAddChannelPost|cancel")
        )

    except Exception as e:
        logger.error(f"Ошибка сканирования: {e}")
        await call.message.edit_text(
            "❌ Ошибка при поиске каналов",
            reply_markup=keyboards.back("BackAddChannelPost|cancel")
        )





async def choice(call: types.CallbackQuery):
    temp = call.data.split("|")

    if temp[1] in ["next", "back"]:
        channels = await db.get_user_channels(
            user_id=call.from_user.id, sort_by="posting"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.channels(channels=channels, remover=int(temp[2]))
        )

    if temp[1] == "cancel":
        await call.message.delete()
        return await start_posting(call.message)

    if temp[1] == "add":
        return await call.message.edit_text(
            text=text("channels:add:text"),
            reply_markup=keyboards.add_channel(
                bot_username=(await call.bot.get_me()).username,
            ),
        )

    if temp[1] == "scan":
        return await scan_existing_channels(call)

    channel = await db.get_channel_by_chat_id(int(temp[1]))
    editors_str = await get_editors(call, channel.chat_id)

    await call.message.edit_text(
        text("channel_info").format(channel.emoji_id, channel.title, editors_str),
        reply_markup=keyboards.manage_channel(),
    )


async def cancel(call: types.CallbackQuery):
    channels = await db.get_user_channels(user_id=call.from_user.id, sort_by="posting")
    return await call.message.edit_text(
        text=text("channels_text"),
        reply_markup=keyboards.channels(
            channels=channels,
        ),
    )


async def manage_channel(call: types.CallbackQuery):
    temp = call.data.split("|")

    if temp[1] == "delete":
        return await call.answer(text("delete_channel"), show_alert=True)

    await cancel(call)


async def handle_channel_id_message(message: types.Message):
    """
    Обрабатывает сообщение с ID канала
    """
    try:
        # Проверяем, что это число
        channel_id_str = message.text.strip()
        if not channel_id_str.isdigit():
            await message.answer("❌ Пожалуйста, отправьте только число (ID канала)")
            return

        # Преобразуем в полный ID канала
        chat_id = -int('100' + channel_id_str)
        logger.info(f"Пользователь {message.from_user.id} отправил ID: {channel_id_str}, полный ID: {chat_id}")

        await message.answer("🔍 Проверяю канал...")

        # Проверяем, не добавлен ли уже канал
        user_channel = await db.get_channel_admin_row(chat_id=chat_id, user_id=message.from_user.id)
        if user_channel:
            await message.answer("ℹ️ Канал уже добавлен в ваш список")
            return

        # Проверяем, является ли бот админом канала
        try:
            bot_member = await message.bot.get_chat_member(chat_id, message.bot.id)
            if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                await message.answer("❌ Бот не является администратором в этом канале")
                return
        except Exception:
            await message.answer("❌ Не удалось проверить канал. Проверьте ID")
            return

        # Проверяем права пользователя
        try:
            user_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
            if user_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await message.answer("❌ Вы не являетесь администратором этого канала")
                return

            if user_member.status == ChatMemberStatus.ADMINISTRATOR:
                rights = {
                    user_member.can_post_messages,
                    user_member.can_edit_messages,
                    user_member.can_delete_messages,
                }
                if False in rights:
                    await message.answer("❌ У вас недостаточно прав в канале")
                    return
        except Exception:
            await message.answer("❌ Не удалось проверить ваши права в канале")
            return

        # Получаем инфо о канале
        try:
            chat = await message.bot.get_chat(chat_id)
        except Exception:
            await message.answer("❌ Не удалось получить информацию о канале")
            return

        # Создаем emoji
        channel = await db.get_channel_by_chat_id(chat_id)
        if channel:
            emoji_id = channel.emoji_id
        else:
            if chat.photo:
                photo_bytes = await message.bot.download(chat.photo.big_file_id)
            else:
                photo_bytes = None
            emoji_id = await create_emoji(message.from_user.id, photo_bytes)

        # Добавляем в базу
        await db.add_channel(
            chat_id=chat_id,
            title=chat.title,
            admin_id=message.from_user.id,
            emoji_id=emoji_id,
        )

        await message.answer(
            f"✅ Канал <tg-emoji emoji-id=\"{emoji_id}\">👤</tg-emoji> {chat.title} успешно добавлен!",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки ID канала: {e}")
        await message.answer("❌ Ошибка при добавлении канала")


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoicePostChannel")
    router.callback_query.register(cancel, F.data.split("|")[0] == "BackAddChannelPost")
    router.callback_query.register(
        manage_channel, F.data.split("|")[0] == "ManageChannelPost"
    )
    # Добавляем обработку текстовых сообщений с ID канала
    router.message.register(handle_channel_id_message, F.text.regexp(r'^\d{8,}$'))
    return router
