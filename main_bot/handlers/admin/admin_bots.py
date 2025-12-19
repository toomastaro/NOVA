"""
Модуль для управления разделом "Боты" в админ-панели.
"""

import logging
import time

from aiogram import Router, F, types
from main_bot.database.db import db
from main_bot.keyboards import keyboards
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

router = Router()

BOTS_PER_PAGE = 10

@safe_handler("Админ: Боты — список")
async def show_bots_list(call: types.CallbackQuery, offset: int = 0) -> None:
    """Отображает список всех ботов системы."""
    all_bots = await db.user_bot.get_all_bots()
    total = len(all_bots)
    bots = all_bots[offset : offset + BOTS_PER_PAGE]

    text = "🤖 <b>Все боты системы</b>\n\nВсего ботов: {total}\n"
    if not bots:
        text += "Боты не найдены."

    await call.message.edit_text(
        text,
        reply_markup=keyboards.admin_bots_list(bots, offset, total),
        parse_mode="HTML"
    )
    await call.answer()

@safe_handler("Админ: Боты — детали")
async def view_bot_details(call: types.CallbackQuery) -> None:
    """Отображает детальную информацию о боте."""
    bot_id = int(call.data.split("|")[2])
    bot = await db.user_bot.get_bot_by_id(bot_id)
    
    if not bot:
        return await call.answer("❌ Бот не найден", show_alert=True)

    # Получаем каналы, к которым привязан этот бот
    channels_settings = await db.channel_bot_settings.get_all_channels_in_bot_id(bot.id)
    
    msg = "🤖 <b>Информация о боте</b>\n\n"
    msg += f"<b>Название:</b> {bot.title}\n"
    msg += f"<b>Username:</b> @{bot.username}\n"
    msg += f"<b>Владелец (ID):</b> <code>{bot.admin_id}</code>\n"
    msg += f"<b>Добавлен:</b> {time.strftime('%d.%m.%Y %H:%M', time.localtime(bot.created_timestamp))}\n"
    
    sub_text = "❌ Нет"
    if bot.subscribe:
        sub_text = time.strftime('%d.%m.%Y', time.localtime(bot.subscribe))
    msg += f"<b>Подписка до:</b> {sub_text}\n\n"

    if channels_settings:
        msg += "📺 <b>Привязан к каналам:</b>\n"
        for setting in channels_settings:
            channel = await db.channel.get_channel_by_chat_id(setting.id)
            title = channel.title if channel else f"ID: {setting.id}"
            msg += f"• {title}\n"
    else:
        msg += "📺 <b>Каналы не привязаны</b>"

    await call.message.edit_text(
        msg,
        reply_markup=keyboards.admin_bot_details(bot_id),
        parse_mode="HTML"
    )
    await call.answer()

@safe_handler("Админ: Боты — колбэки")
async def bots_callback_handler(call: types.CallbackQuery) -> None:
    """Маршрутизатор колбэков для раздела ботов."""
    data = call.data.split("|")
    action = data[1]
    
    if action == "list":
        offset = int(data[2])
        await show_bots_list(call, offset)
    elif action == "view":
        await view_bot_details(call)

def get_router() -> Router:
    router.callback_query.register(bots_callback_handler, F.data.split("|")[0] == "AdminBots")
    return router
