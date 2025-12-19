"""
Модуль управления каналами в админ-панели.

Содержит:
- Просмотр списка всех каналов
- Поиск каналов по названию
- Просмотр детальной информации о канале
- Просмотр администраторов канала
"""

import logging

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.admin import AdminChannels
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

router = Router()

CHANNELS_PER_PAGE = 10


@safe_handler("Admin Show Channels List")
async def show_channels_list(call: types.CallbackQuery, offset: int = 0) -> None:
    """
    Показать список каналов с пагинацией.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        offset (int): Смещение для пагинации.
    """
    # Получить все каналы
    all_channels = await db.channel.get_all_channels()
    total = len(all_channels)

    # Пагинация
    channels = all_channels[offset : offset + CHANNELS_PER_PAGE]

    # Формирование текста
    text_msg = "📺 <b>Управление каналами</b>\n\n"
    text_msg += f"Всего каналов: {total}\n"
    text_msg += f"Страница: {offset // CHANNELS_PER_PAGE + 1}/{(total + CHANNELS_PER_PAGE - 1) // CHANNELS_PER_PAGE}\n\n"

    if not channels:
        text_msg += "Нет добавленных каналов"

    try:
        await call.message.edit_text(
            text_msg,
            reply_markup=keyboards.admin_channels_list(channels, offset, total),
            parse_mode="HTML",
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            raise

    await call.answer()


@safe_handler("Admin Search Channel Start")
async def search_channel_start(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Начать процесс поиска канала.
    Переводит бота в состояние ожидания ввода.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await call.message.edit_text(
        "🔍 <b>Поиск канала</b>\n\nОтправьте название или username канала для поиска:",
        reply_markup=keyboards.back(data="AdminChannels|list|0"),
        parse_mode="HTML",
    )
    await state.set_state(AdminChannels.searching)
    await call.answer()


@safe_handler("Admin Search Channel Process")
async def search_channel_process(message: types.Message, state: FSMContext) -> None:
    """
    Обработка текстового запроса для поиска канала.

    Аргументы:
        message (types.Message): Сообщение с поисковым запросом.
        state (FSMContext): Контекст состояния.
    """
    query = message.text.strip().lower()

    # Получить все каналы
    all_channels = await db.channel.get_all_channels()

    # Фильтрация
    found_channels = [ch for ch in all_channels if query in ch.title.lower()]

    if not found_channels:
        await message.answer(
            f"❌ Каналы не найдены\n\nПо запросу '{query}' ничего не найдено",
            reply_markup=keyboards.back(data="AdminChannels|list|0"),
            parse_mode="HTML",
        )
    else:
        text_msg = "🔍 <b>Результаты поиска</b>\n\n"
        text_msg += f"Найдено каналов: {len(found_channels)}\n"
        text_msg += f"Запрос: '{query}'\n\n"

        await message.answer(
            text_msg,
            reply_markup=keyboards.admin_channels_list(
                found_channels, 0, len(found_channels)
            ),
            parse_mode="HTML",
        )

    await state.clear()


@safe_handler("Admin View Channel Details")
async def view_channel_details(call: types.CallbackQuery) -> None:
    """
    Показать детальную информацию о выбранном канале.
    Включает информацию из БД и список админов из Telegram API.

    Аргументы:
        call (types.CallbackQuery): Callback запрос с ID канала.
    """
    channel_id = int(call.data.split("|")[2])

    # Получить канал
    channel = await db.channel.get_channel_by_id(channel_id)

    if not channel:
        await call.answer("❌ Канал не найден", show_alert=True)
        return

    # Получить администраторов через Bot API
    chat_info = None
    username = "N/A"
    try:
        chat_info = await call.bot.get_chat(channel.chat_id)
        if chat_info.username:
            username = chat_info.username
    except Exception as e:
        logger.warning(
            f"Failed to get chat info for {channel.title} ({channel.id}): {e}"
        )

    admins_text = ""
    try:
        admins = await call.bot.get_chat_administrators(channel.chat_id)
        admins_list = [
            f"• {admin.user.full_name} (@{admin.user.username or 'N/A'}) - {admin.status}"
            for admin in admins[:10]  # Показать первых 10
        ]
        admins_text = "\n".join(admins_list)

        if len(admins) > 10:
            admins_text += f"\n\n... и еще {len(admins) - 10} администраторов"
    except Exception as e:
        logger.error(f"Failed to get admins for {channel.title} ({channel.id}): {e}")
        admins_text = f"❌ Не удалось получить список: {str(e)[:100]}"

    # Формирование текста
    text_msg = "📺 <b>Информация о канале</b>\n\n"
    text_msg += f"<b>Название:</b> {channel.title}\n"
    text_msg += f"<b>Username:</b> @{username}\n"
    text_msg += f"<b>Chat ID:</b> <code>{channel.chat_id}</code>\n"
    text_msg += (
        f"<b>Подписка:</b> {'✅ Активна' if channel.subscribe else '❌ Неактивна'}\n\n"
    )
    text_msg += f"👥 <b>Администраторы:</b>\n{admins_text}"

    await call.message.edit_text(
        text_msg,
        reply_markup=keyboards.admin_channel_details(channel_id),
        parse_mode="HTML",
    )
    await call.answer()


@safe_handler("Admin Channels Callback")
async def channels_callback_handler(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Общий обработчик для всех callback'ов каналов.
    Маршрутизирует действия (list, search, view) на соответствующие функции.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    data = call.data.split("|")
    action = data[1] if len(data) > 1 else None

    if action == "list":
        offset = int(data[2]) if len(data) > 2 else 0
        await show_channels_list(call, offset)
    elif action == "search":
        await search_channel_start(call, state)
    elif action == "view":
        await view_channel_details(call)


def get_router() -> Router:
    """
    Регистрация handlers и возврат роутера.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router.callback_query.register(
        channels_callback_handler, F.data.split("|")[0] == "AdminChannels"
    )
    router.message.register(search_channel_process, AdminChannels.searching)
    return router
