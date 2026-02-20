"""
Модуль управления каналами в админ-панели.

Содержит:
- Просмотр списка всех каналов
- Поиск каналов по названию
- Просмотр детальной информации о канале
- Просмотр администраторов канала
"""

import logging
import time

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

    # Получение данных через Bot API (для справки)
    members_count = "N/A"
    status_bot_post = "❓"
    status_bot_mail = "❓"
    
    try:
        # Получаем количество подписчиков
        members_count = await call.bot.get_chat_member_count(channel.chat_id)
        
        # Проверка прав основного бота
        try:
            bot_member = await call.bot.get_chat_member(channel.chat_id, call.bot.id)
            from aiogram.enums import ChatMemberStatus
            bot_can_post = False
            if bot_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                bot_can_post = getattr(bot_member, "can_post_messages", True)
            
            status_bot_post = "✅" if bot_can_post else "❌"
            status_bot_mail = "✅" if bot_can_post else "❌"
        except Exception as e:
            logger.warning(f"Failed to get bot member status: {e}")

    except Exception as e:
        logger.warning(f"Failed to get chat info for {channel.title}: {e}")

    # Сбор и форматирование списка администраторов
    admins_list = []
    try:
        chat_admins = await call.bot.get_chat_administrators(channel.chat_id)
        for admin in chat_admins:
            if admin.user.is_bot:
                continue
            
            name = f"@{admin.user.username}" if admin.user.username else admin.user.full_name
            admins_list.append(f"{name} (<code>{admin.user.id}</code>)")
    except Exception as e:
        logger.error(f"Failed to get admins for {channel.chat_id}: {e}")

    admins_str = "\n".join(admins_list) if admins_list else "<i>Не удалось получить список</i>"

    # Проверка приветственных сообщений
    hello_msgs = await db.channel_bot_hello.get_hello_messages(channel.chat_id, active=True)
    status_welcome = "✅" if hello_msgs else "❌"

    # 1. Информация о клиенте MTProto
    client_info_text = "❌ Не назначен"
    rights_text = "❌ Нет данных"
    if channel.last_client_id:
        client = await db.mt_client.get_mt_client(channel.last_client_id)
        if client:
            client_info_text = f"<code>{client.alias}</code> (ID: {client.id}) [{client.status}]"
            # Проверка прав конкретного клиента
            membership = await db.mt_client_channel.get_or_create_mt_client_channel(client.id, channel.id)
            if membership:
                rights = []
                if membership.is_member:
                    rights.append("Участник")
                if membership.is_admin:
                    rights.append("Админ")
                if membership.can_post_messages:
                    rights.append("Посты")
                if membership.can_post_stories:
                    rights.append("Сторис")
                rights_text = ", ".join(rights) if rights else "Ограничен (чтение)"

    # 2. Статистика постов
    posts_count = await db.post.count_channel_posts(channel.chat_id)
    published_count = await db.published_post.count_channel_published(channel.chat_id)

    # 3. Информация о подписке
    sub_status = "❌ Нет"
    if channel.subscribe:
        if channel.subscribe > time.time():
            sub_status = f"✅ Активна (до {time.strftime('%d.%m.%Y', time.localtime(channel.subscribe))})"
        else:
            sub_status = f"⌛ Истекла ({time.strftime('%d.%m.%Y', time.localtime(channel.subscribe))})"

    # Формирование текста
    text_msg = "📺 <b>Информация о канале</b>\n\n"
    text_msg += f"<b>Название:</b> {channel.title} (<code>{channel.chat_id}</code>)\n"
    text_msg += f"<b>Подписчиков:</b> {members_count}\n"
    text_msg += f"<b>Добавлен:</b> {time.strftime('%d.%m.%Y %H:%M', time.localtime(channel.created_timestamp))}\n\n"
    
    text_msg += f"<b>Подписка:</b> {sub_status}\n"
    text_msg += f"<b>Посты:</b> {posts_count} (план) / {published_count} (архив)\n\n"
    
    text_msg += "🤖 <b>Статус Nova Bot:</b>\n"
    text_msg += f"├ Постинг: {status_bot_post}\n"
    text_msg += f"├ Рассылка: {status_bot_mail}\n"
    text_msg += f"└ Приветствие: {status_welcome}\n\n"

    if channel.last_client_id and client_info_text != "❌ Не назначен":
        text_msg += f"<b>Клиент MTProto:</b> {client_info_text}\n"
        text_msg += f"<b>Права клиента:</b> {rights_text}\n\n"
    
    text_msg += f"<b>Админы:</b>\n{admins_str}"

    await call.message.edit_text(
        text_msg,
        reply_markup=keyboards.admin_channel_details(channel_id),
        parse_mode="HTML",
    )
    await call.answer()


@safe_handler("Admin Extend Subscription Start")
async def extend_channel_subscription_start(call: types.CallbackQuery) -> None:
    """Отображает меню выбора периода продления."""
    channel_id = int(call.data.split("|")[2])
    await call.message.edit_text(
        "➕ <b>Продление подписки</b>\n\nВыберите период, на который хотите продлить подписку бесплатно:",
        reply_markup=keyboards.admin_channel_subscribe_extend(channel_id),
        parse_mode="HTML"
    )
    await call.answer()


@safe_handler("Admin Extend Subscription Process")
async def extend_channel_subscription_process(call: types.CallbackQuery) -> None:
    """Обрабатывает логику продления подписки."""
    data = call.data.split("|")
    channel_id = int(data[2])
    days = int(data[3])

    channel = await db.channel.get_channel_by_id(channel_id)
    if not channel:
        return await call.answer("❌ Канал не найден", show_alert=True)

    current_time = int(time.time())
    # Если подписка уже кончилась или ее не было — продлеваем от текущего времени
    # Если подписка активна — добавляем к существующей дате
    base_time = max(current_time, channel.subscribe or 0)
    new_expire = base_time + (days * 86400)

    await db.channel.update_channel_by_chat_id(channel.chat_id, subscribe=new_expire)
    
    await call.answer(f"✅ Подписка продлена на {days} дн.", show_alert=True)
    await view_channel_details(call)



@safe_handler("Admin Add Helper List")
async def admin_add_helper_list(call: types.CallbackQuery) -> None:
    """Отображает список доступных помощников."""
    channel_id = int(call.data.split("|")[2])
    
    # Получаем список всех внутренних помощников
    assistants = await db.mt_client.get_mt_clients_by_pool("internal")
    
    if not assistants:
        return await call.answer("❌ В пуле 'internal' нет доступных помощников", show_alert=True)

    await call.message.edit_text(
        "🤖 <b>Выбор помощника</b>\n\nВыберите помощника из списка 'internal' для приглашения в канал:",
        reply_markup=keyboards.admin_assistants_list(channel_id, assistants),
        parse_mode="HTML"
    )
    await call.answer()


@safe_handler("Admin Set Helper Process")
async def admin_set_helper_process(call: types.CallbackQuery) -> None:
    """Запускает процесс приглашения выбранного помощника."""
    data = call.data.split("|")
    channel_id = int(data[2])
    client_id = int(data[3])

    channel = await db.channel.get_channel_by_id(channel_id)
    if not channel:
        return await call.answer("❌ Канал не найден", show_alert=True)

    await call.message.edit_text("⏳ <b>Процесс приглашения запущен...</b>", parse_mode="HTML")
    
    from main_bot.utils.tg_utils import invite_specific_helper
    result = await invite_specific_helper(channel.chat_id, client_id)

    if result.get("success"):
        import html
        me = result["me"]
        username = me.username or me.first_name
        
        msg = (
            f"✅ <b>Помощник успешно добавлен!</b>\n\n"
            f"Бот: <code>{html.escape(username)}</code>\n\n"
            f"Теперь убедитесь, что ему выданы права администратора в канале."
        )
        await call.message.answer(msg, parse_mode="HTML")
        await view_channel_details(call)
    else:
        error_msg = result.get("message", "Неизвестная ошибка")
        await call.message.edit_text(
            f"❌ <b>Ошибка приглашения:</b>\n{error_msg}",
            reply_markup=keyboards.back(data=f"AdminChannels|view|{channel_id}"),
            parse_mode="HTML"
        )


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
    elif action == "extend":
        await extend_channel_subscription_start(call)
    elif action == "ext_proc":
        await extend_channel_subscription_process(call)
    elif action == "add_helper":
        await admin_add_helper_list(call)
    elif action == "set_helper":
        await admin_set_helper_process(call)


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
