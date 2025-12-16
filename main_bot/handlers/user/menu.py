"""
Обработчики главного меню и навигации.

Модуль управляет:
- Маршрутизацией по пунктам главного меню
- Отображением разделов (Постинг, Сторис, Боты, Профиль)
- Настройкой "Приветки"
"""

import logging
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.keyboards import keyboards
from main_bot.keyboards.common import Reply
from main_bot.states.user import Support
from main_bot.utils.lang.language import text
from main_bot.utils.error_handler import safe_handler
from main_bot.database.db import db
from hello_bot.database.db import Database

logger = logging.getLogger(__name__)


def serialize_user_bot(bot):
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


@safe_handler("Выбор меню")
async def choice(message: types.Message, state: FSMContext):
    """
    Маршрутизатор главного меню.
    Определяет нажатую кнопку и вызывает соответствующий обработчик.
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
        text("reply_menu:channels"): {"cor": show_channels, "args": (message,)},
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


@safe_handler("Меню постинга")
async def start_posting(message: types.Message):
    logger.info("Пользователь %s открыл меню постинга", message.from_user.id)
    await message.answer(text("start_post_text"), reply_markup=keyboards.posting_menu())


@safe_handler("Меню сторис")
async def start_stories(message: types.Message):
    await message.answer(
        text("start_stories_text"), reply_markup=keyboards.stories_menu()
    )


@safe_handler("Меню ботов")
async def start_bots(message: types.Message):
    await message.answer(text("start_bots_text"), reply_markup=keyboards.bots_menu())


@safe_handler("Поддержка")
async def support(message: types.Message, state: FSMContext):
    await message.answer(
        text("start_support_text"), reply_markup=keyboards.cancel(data="CancelSupport")
    )
    await state.set_state(Support.message)


@safe_handler("Профиль")
async def profile(message: types.Message):
    await message.answer(
        text("start_profile_text"), reply_markup=keyboards.profile_menu()
    )


@safe_handler("Подписка")
async def subscription(message: types.Message):
    """Меню подписки с балансом, подпиской и реферальной системой"""
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


@safe_handler("Показать каналы")
async def show_channels(message: types.Message):
    """Показать список каналов пользователя"""
    channels = await db.channel.get_user_channels(
        user_id=message.chat.id, sort_by="posting"
    )
    await message.answer(
        text("channels_text"), reply_markup=keyboards.channels(channels=channels)
    )


@safe_handler("Приветка")
async def start_privetka(message: types.Message, state: FSMContext):
    await state.update_data(from_privetka=True)
    channels_raw = await db.channel_bot_settings.get_bot_channels(message.chat.id)
    channels = await db.channel.get_user_channels(
        message.chat.id, from_array=[i.id for i in channels_raw]
    )

    await message.answer(
        text("privetka_text"),
        reply_markup=keyboards.choice_channel_for_setting(
            channels=channels, data="PrivetkaChannel"
        ),
    )


@safe_handler("Выбор канала для приветки")
async def privetka_choice_channel(call: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора канала для настройки приветственного бота."""
    temp = call.data.split("|")

    if temp[1] == "cancel":
        await call.message.delete()
        await call.message.answer("Главное меню", reply_markup=Reply.menu())
        return

    if temp[1] in ["next", "back"]:
        channels_raw = await db.channel_bot_settings.get_bot_channels(call.from_user.id)
        channels = await db.channel.get_user_channels(
            call.from_user.id, from_array=[i.id for i in channels_raw]
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
    from main_bot.handlers.user.bots.bot_settings.menu import show_channel_setting

    await show_channel_setting(call.message, db_obj, state)


def get_router():
    """Создает роутер для меню."""
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
