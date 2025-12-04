from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards.keyboards import keyboards
from main_bot.states.admin import AdminChannels
from main_bot.utils.lang.language import text
from config import Config

router = Router()

CHANNELS_PER_PAGE = 10


async def show_channels_list(call: types.CallbackQuery, offset: int = 0):
    """Показать список каналов с пагинацией"""
    # Получить все каналы
    all_channels = await db.get_all_channels()
    total = len(all_channels)
    
    # Пагинация
    channels = all_channels[offset:offset + CHANNELS_PER_PAGE]
    
    # Формирование текста
    text_msg = f"📺 <b>Управление каналами</b>\n\n"
    text_msg += f"Всего каналов: {total}\n"
    text_msg += f"Страница: {offset // CHANNELS_PER_PAGE + 1}/{(total + CHANNELS_PER_PAGE - 1) // CHANNELS_PER_PAGE}\n\n"
    
    if not channels:
        text_msg += "Нет добавленных каналов"
    
    try:
        await call.message.edit_text(
            text_msg,
            reply_markup=keyboards.admin_channels_list(channels, offset, total),
            parse_mode="HTML"
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            raise
    
    await call.answer()


async def search_channel_start(call: types.CallbackQuery, state: FSMContext):
    """Начать поиск канала"""
    await call.message.edit_text(
        "🔍 <b>Поиск канала</b>\n\n"
        "Отправьте название или username канала для поиска:",
        reply_markup=keyboards.back(data="AdminChannels|list|0"),
        parse_mode="HTML"
    )
    await state.set_state(AdminChannels.searching)
    await call.answer()


async def search_channel_process(message: types.Message, state: FSMContext):
    """Обработка поиска канала"""
    query = message.text.strip().lower()
    
    # Получить все каналы
    all_channels = await db.get_all_channels()
    
    # Фильтрация
    found_channels = [
        ch for ch in all_channels
        if query in ch.title.lower() or (ch.username and query in ch.username.lower())
    ]
    
    if not found_channels:
        await message.answer(
            "❌ Каналы не найдены\n\n"
            f"По запросу '{query}' ничего не найдено",
            reply_markup=keyboards.back(data="AdminChannels|list|0"),
            parse_mode="HTML"
        )
    else:
        text_msg = f"🔍 <b>Результаты поиска</b>\n\n"
        text_msg += f"Найдено каналов: {len(found_channels)}\n"
        text_msg += f"Запрос: '{query}'\n\n"
        
        await message.answer(
            text_msg,
            reply_markup=keyboards.admin_channels_list(found_channels, 0, len(found_channels)),
            parse_mode="HTML"
        )
    
    await state.clear()


async def view_channel_details(call: types.CallbackQuery):
    """Показать детали канала"""
    channel_id = int(call.data.split('|')[2])
    
    # Получить канал
    channel = await db.get_channel_by_id(channel_id)
    
    if not channel:
        await call.answer("❌ Канал не найден", show_alert=True)
        return
    
    # Получить администраторов через Bot API
    from instance_bot import bot as main_bot_obj
    
    try:
        admins = await main_bot_obj.get_chat_administrators(channel.chat_id)
        admins_text = "\n".join([
            f"• {admin.user.full_name} (@{admin.user.username or 'N/A'}) - {admin.status}"
            for admin in admins[:10]  # Показать первых 10
        ])
        
        if len(admins) > 10:
            admins_text += f"\n\n... и еще {len(admins) - 10} администраторов"
    except Exception as e:
        admins_text = f"❌ Не удалось получить список: {str(e)[:100]}"
    
    # Формирование текста
    text_msg = f"📺 <b>Информация о канале</b>\n\n"
    text_msg += f"<b>Название:</b> {channel.title}\n"
    text_msg += f"<b>Username:</b> @{channel.username or 'N/A'}\n"
    text_msg += f"<b>Chat ID:</b> <code>{channel.chat_id}</code>\n"
    text_msg += f"<b>Подписка:</b> {'✅ Активна' if channel.subscribe else '❌ Неактивна'}\n\n"
    text_msg += f"👥 <b>Администраторы:</b>\n{admins_text}"
    
    await call.message.edit_text(
        text_msg,
        reply_markup=keyboards.admin_channel_details(channel_id),
        parse_mode="HTML"
    )
    await call.answer()


async def channels_callback_handler(call: types.CallbackQuery, state: FSMContext):
    """Общий обработчик для всех callback'ов каналов"""
    data = call.data.split('|')
    action = data[1] if len(data) > 1 else None
    
    if action == 'list':
        offset = int(data[2]) if len(data) > 2 else 0
        await show_channels_list(call, offset)
    elif action == 'search':
        await search_channel_start(call, state)
    elif action == 'view':
        await view_channel_details(call)


def hand_add():
    """Регистрация handlers"""
    router.callback_query.register(channels_callback_handler, F.data.split('|')[0] == "AdminChannels")
    router.message.register(search_channel_process, AdminChannels.searching)
    return router
