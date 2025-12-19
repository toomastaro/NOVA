"""
Модуль для управления разделом "Админы" (пользователи) в админ-панели.
"""

import logging
import time

from aiogram import Router, F, types
from main_bot.database.db import db
from main_bot.keyboards import keyboards
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

router = Router()

USERS_PER_PAGE = 10

@safe_handler("Админ: Пользователи — список")
async def show_users_list(call: types.CallbackQuery, offset: int = 0) -> None:
    """Отображает список всех пользователей системы."""
    all_users = await db.user.get_users()
    total = len(all_users)
    users = all_users[offset : offset + USERS_PER_PAGE]

    text = f"👥 <b>Пользователи системы</b>\n\nВсего: {total}\n"
    if not users:
        text += "Пользователи не найдены."

    await call.message.edit_text(
        text,
        reply_markup=keyboards.admin_users_list(users, offset, total),
        parse_mode="HTML"
    )
    await call.answer()

@safe_handler("Админ: Пользователи — детали")
async def view_user_details(call: types.CallbackQuery) -> None:
    """Отображает детальный отчет по администратору."""
    user_id = int(call.data.split("|")[2])
    user = await db.user.get_user(user_id)
    
    if not user:
        return await call.answer("❌ Пользователь не найден", show_alert=True)

    # Собираем статистику
    channels = await db.channel.get_user_channels(user_id)
    bots = await db.user_bot.get_user_bots(user_id)
    
    posts_count = await db.post.count_user_posts(user_id)
    stories_count = await db.story.count_user_stories(user_id)
    published_count = await db.published_post.count_user_published(user_id)
    bot_posts_count = await db.bot_post.count_user_bot_posts(user_id)

    msg = "👤 <b>Отчет по администратору</b>\n\n"
    msg += f"<b>Telegram ID:</b> <code>{user_id}</code>\n"
    msg += f"<b>Регистрация:</b> {time.strftime('%d.%m.%Y %H:%M', time.localtime(user.created_timestamp))}\n"
    msg += f"<b>Баланс:</b> {user.balance}₽\n"
    msg += f"<b>Статус:</b> {'✅ Активен' if user.is_active else '❌ Заблокирован'}\n\n"

    msg += "📊 <b>Статистика действий:</b>\n"
    msg += f"├ Постов (план/архив): {posts_count}\n"
    msg += f"├ Опубликовано: {published_count}\n"
    msg += f"├ Историй: {stories_count}\n"
    msg += f"└ Рассылок через ботов: {bot_posts_count}\n\n"

    if channels:
        msg += f"📺 <b>Каналы ({len(channels)}):</b>\n"
        for ch in channels[:5]:
            status = "✅" if ch.subscribe and ch.subscribe > time.time() else "❌"
            msg += f"• {status} {ch.title[:20]}\n"
        if len(channels) > 5:
            msg += f"<i>... и еще {len(channels)-5}</i>\n"
        msg += "\n"

    if bots:
        msg += f"🤖 <b>Боты ({len(bots)}):</b>\n"
        for b in bots:
            msg += f"• {b.title} (@{b.username})\n"
    else:
        msg += "🤖 <b>Боты отсутствуют</b>"

    await call.message.edit_text(
        msg,
        reply_markup=keyboards.admin_user_details(user_id),
        parse_mode="HTML"
    )
    await call.answer()

@safe_handler("Админ: Пользователи — колбэки")
async def users_callback_handler(call: types.CallbackQuery) -> None:
    """Маршрутизатор колбэков для раздела пользователей."""
    data = call.data.split("|")
    action = data[1]
    
    if action == "list":
        offset = int(data[2])
        await show_users_list(call, offset)
    elif action == "view":
        await view_user_details(call)

def get_router() -> Router:
    router.callback_query.register(users_callback_handler, F.data.split("|")[0] == "AdminUsers")
    return router
