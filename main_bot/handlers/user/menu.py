"""
Обработчики главного меню и навигации.

Модуль управляет:
- Маршрутизацией по пунктам главного меню
- Отображением разделов (Постинг, Сторис, Боты, Профиль)
- Настройкой "Приветки"
"""

import logging
from typing import Dict, Any, Optional

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.keyboards.common import Reply
from main_bot.states.user import Support
from utils.error_handler import safe_handler
from main_bot.utils.lang.language import text

logger = logging.getLogger(__name__)


def serialize_user_bot(bot: Any) -> Optional[Dict[str, Any]]:
    """
    Сериализует объект бота пользователя в словарь.

    Аргументы:
        bot (Any): Объект бота.

    Возвращает:
        Optional[Dict[str, Any]]: Словарь с данными бота или None.
    """
    if not bot:
        return None
    return {
        "id": bot.id,
        "admin_id": bot.admin_id,
        "token": bot.token,
        "username": bot.username,
        "title": bot.title,
        "schema": getattr(bot, "schema", None),
        "created_timestamp": getattr(bot, "created_timestamp", None),
        "emoji_id": getattr(bot, "emoji_id", None),
        "subscribe": getattr(bot, "subscribe", None),
    }


@safe_handler(
    "Выбор меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice(message: types.Message, state: FSMContext) -> None:
    """
    Маршрутизатор главного меню.
    Определяет нажатую кнопку и вызывает соответствующий обработчик.

    Аргументы:
        message (types.Message): Сообщение с выбором меню.
        state (FSMContext): Контекст состояния FSM.
    """
    await state.clear()

    menu = {
        text("reply_menu:posting"): {"cor": start_posting, "args": (message,)},
        text("reply_menu:story"): {"cor": start_stories, "args": (message,)},
        text("reply_menu:bots"): {"cor": start_bots, "args": (message,)},
        text("reply_menu:support"): {
            "cor": support,
            "args": (
                message,
                state,
            ),
        },
        text("reply_menu:profile"): {"cor": profile, "args": (message,)},
        text("reply_menu:subscription"): {"cor": subscription, "args": (message,)},
        text("reply_menu:channels"): {"cor": show_channels, "args": (message, state)},
        text("reply_menu:privetka"): {
            "cor": start_privetka,
            "args": (
                message,
                state,
            ),
        },
    }

    if message.text in menu:
        handler_data = menu[message.text]
        await handler_data["cor"](*handler_data["args"])
    else:
        logger.warning("Неизвестная команда меню: %s", message.text)


@safe_handler(
    "Меню постинга"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def start_posting(message: types.Message) -> None:
    """
    Открыть меню постинга.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    logger.info("Пользователь %s открыл меню постинга", message.from_user.id)
    await message.answer(text("start_post_text"), reply_markup=keyboards.posting_menu())

    # Удаляем сообщение пользователя ("📝 Постинг"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler(
    "Меню сторис"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def start_stories(message: types.Message) -> None:
    """
    Открыть меню сторис.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    logger.info("Пользователь %s открыл меню сторис", message.from_user.id)
    await message.answer(
        text("start_stories_text"), reply_markup=keyboards.stories_menu()
    )

    # Удаляем сообщение пользователя ("🎬 Истории"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler(
    "Меню ботов"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def start_bots(message: types.Message) -> None:
    """
    Открыть меню ботов.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    await message.answer(text("start_bots_text"), reply_markup=keyboards.bots_menu())

    # Удаляем сообщение пользователя ("🤖 Боты"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler(
    "Поддержка"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def support(message: types.Message, state: FSMContext) -> None:
    """
    Открыть меню поддержки.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    await message.answer(
        text("start_support_text"), reply_markup=keyboards.cancel(data="CancelSupport")
    )
    await state.set_state(Support.message)

    # Удаляем сообщение пользователя ("👨‍💻 Поддержка"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler(
    "Профиль"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def profile(message: types.Message) -> None:
    """
    Открыть профиль пользователя.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    await message.answer(
        text("start_profile_text"), reply_markup=keyboards.profile_menu()
    )

    # Удаляем сообщение пользователя ("👤 Профиль"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler(
    "Подписка"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def subscription(message: types.Message) -> None:
    """
    Меню подписки с балансом, подпиской и реферальной системой.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    user = await db.user.get_user(user_id=message.chat.id)
    if not user:
        # Если пользователя нет, создаем и получаем объект
        user = await db.user.add_user(
            id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
    await message.answer(
        text("balance_text").format(user.balance),
        reply_markup=keyboards.subscription_menu(),
        parse_mode="HTML",
    )

    # Удаляем сообщение пользователя ("💎 Подписка"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler(
    "Показать каналы"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_channels(message: types.Message, state: FSMContext) -> None:
    """
    Показать список каналов пользователя.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    view_mode = data.get("channels_view_mode", "folders")
    current_folder_id = data.get("channels_folder_id")

    folders = await db.user_folder.get_user_folders(user_id=message.chat.id)
    
    if current_folder_id:
        channels = await db.channel.get_user_channels(
            user_id=message.chat.id, folder_id=current_folder_id, sort_by="posting"
        )
    else:
        channels = await db.channel.get_user_channels(
            user_id=message.chat.id, sort_by="posting"
        )
        if view_mode == "folders":
            channels = [c for c in channels if not c.folder_id]

    await state.update_data(channels_view_mode=view_mode)

    await message.answer(
        text("channels_text"),
        reply_markup=keyboards.channels(
            channels=channels,
            folders=folders,
            view_mode=view_mode,
            is_inside_folder=bool(current_folder_id),
        ),
    )

    # Удаляем сообщение пользователя ("📺 Мои каналы"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler(
    "Приветка"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def start_privetka(message: types.Message, state: FSMContext) -> None:
    """
    Начало настройки приветственного бота (Privetka).

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    await state.update_data(from_privetka=True)
    import time

    channels_raw = await db.channel_bot_settings.get_bot_channels(
        message.chat.id, only_with_bot=True
    )
    # Создаем словарь chat_id -> bot_id для быстрой проверки
    bot_mapping = {c.id: c.bot_id for c in channels_raw if c.bot_id}

    objects = await db.channel.get_user_channels(
        message.chat.id, from_array=list(bot_mapping.keys())
    )

    # Фильтруем каналы с активной подпиской и ГАРАНТИРОВАННО привязанным ботом
    now = int(time.time())
    channels = [
        obj
        for obj in objects
        if obj.subscribe and obj.subscribe > now and bot_mapping.get(obj.chat_id)
    ]

    if not channels:
        await message.answer(text("error_privetka_empty"))
        return

    await message.answer(
        text("privetka_text"),
        reply_markup=keyboards.choice_channel_for_setting(
            channels=channels, data="PrivetkaChannel"
        ),
    )

    # Удаляем сообщение пользователя ("👋 Приветка"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler(
    "Выбор канала для приветки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def privetka_choice_channel(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора канала для настройки приветственного бота.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")

    if temp[1] == "cancel":
        await call.message.delete()
        await call.message.answer("Главное меню", reply_markup=Reply.menu())
        return

    if temp[1] in ["next", "back"]:
        import time

        channels_raw = await db.channel_bot_settings.get_bot_channels(
            call.from_user.id, only_with_bot=True
        )
        # Создаем словарь chat_id -> bot_id для быстрой проверки
        bot_mapping = {c.id: c.bot_id for c in channels_raw if c.bot_id}

        objects = await db.channel.get_user_channels(
            call.from_user.id, from_array=list(bot_mapping.keys())
        )

        now = int(time.time())
        channels = [
            obj
            for obj in objects
            if obj.subscribe and obj.subscribe > now and bot_mapping.get(obj.chat_id)
        ]

        if not channels:
            return await call.message.edit_text(
                text("error_privetka_empty"), reply_markup=None
            )

        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_for_setting(
                channels=channels, data="PrivetkaChannel", remover=int(temp[2])
            )
        )

    chat_id = int(temp[1])
    channel_setting = await db.channel_bot_settings.get_channel_bot_setting(
        chat_id=chat_id
    )

    bot_id = channel_setting.bot_id if channel_setting else None

    user_bot = None
    await state.update_data(chat_id=chat_id)
    if bot_id:
        await state.update_data(bot_id=bot_id)
        user_bot = await db.user_bot.get_bot_by_id(bot_id)
        if user_bot:
            await state.update_data(user_bot=serialize_user_bot(user_bot))

    db_obj = Database()
    if user_bot:
        db_obj.schema = user_bot.schema

    await call.message.delete()
    # Импорт внутри функции чтобы избежать циклических зависимостей
    from main_bot.handlers.user.bots.bot_settings.menu import show_channel_setting

    await show_channel_setting(call.message, db_obj, state)


def get_router() -> Router:
    """
    Создает роутер для меню.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.message.register(
        choice,
        F.text.in_(
            {
                text("reply_menu:posting"),
                text("reply_menu:story"),
                text("reply_menu:bots"),
                text("reply_menu:support"),
                text("reply_menu:profile"),
                text("reply_menu:subscription"),
                text("reply_menu:channels"),
                text("reply_menu:privetka"),
            }
        ),
    )
    router.callback_query.register(
        privetka_choice_channel, F.data.startswith("PrivetkaChannel")
    )
    return router
