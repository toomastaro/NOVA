from aiogram import types, F, Router

from main_bot.database.db import db
from main_bot.handlers.user.menu import start_stories
from main_bot.keyboards import keyboards
from main_bot.utils.functions import get_editors
from main_bot.utils.lang.language import text
import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

@safe_handler("Stories Channel Choice")
async def choice(call: types.CallbackQuery):
    temp = call.data.split('|')

    if temp[1] in ['next', 'back']:
        channels = await db.get_user_channels(
            user_id=call.from_user.id,
            sort_by="stories"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.channels(
                channels=channels,
                remover=int(temp[2]),
                data="ChoiceStoriesChannel"
            )
        )

    if temp[1] == 'cancel':
        await call.message.delete()
        return await start_stories(call.message)

    if temp[1] == 'add':
        # Удаляем старое сообщение
        await call.message.delete()
        
        # Отправляем текстовую инструкцию
        return await call.message.answer(
            text=text("channels:add:text"),
            reply_markup=keyboards.add_channel(
                bot_username=(await call.bot.get_me()).username,
                data="BackAddChannelStories"
            )
        )

    channel = await db.get_channel_by_chat_id(int(temp[1]))
    editors_str = await get_editors(call, channel.chat_id)
    
    # Получаем информацию о создателе
    try:
        creator = await call.bot.get_chat(channel.admin_id)
        creator_name = f"@{creator.username}" if creator.username else creator.full_name
    except:
        creator_name = "Неизвестно"
    
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

    await call.message.edit_text(
        text('channel_info').format(
            channel.title,
            creator_name,
            created_str,
            subscribe_str,
            editors_str
        ),
        reply_markup=keyboards.manage_channel(
            data="ManageChannelStories"
        )
    )


@safe_handler("Stories Channel Cancel")
async def cancel(call: types.CallbackQuery):
    channels = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="stories"
    )
    return await call.message.edit_text(
        text=text("channels_text"),
        reply_markup=keyboards.channels(
            channels=channels,
            data="ChoiceStoriesChannel"
        )
    )


@safe_handler("Stories Manage Channel")
async def manage_channel(call: types.CallbackQuery):
    temp = call.data.split('|')

    if temp[1] == 'delete':
        return await call.answer(
            text('delete_channel'),
            show_alert=True
        )

    await cancel(call)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoiceStoriesChannel")
    router.callback_query.register(cancel, F.data.split("|")[0] == "BackAddChannelStories")
    router.callback_query.register(manage_channel, F.data.split("|")[0] == "ManageChannelStories")
    return router
