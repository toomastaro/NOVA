from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.channel_bot_settings.model import ChannelBotSetting
from main_bot.database.db import db
from main_bot.handlers.user.bots.settings import show_bot_manage
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.utils.schemas import HelloAnswer, ByeAnswer
from main_bot.utils.error_handler import safe_handler
import logging

logger = logging.getLogger(__name__)


@safe_handler("Bots Show Channel Setting")
async def show_channel_setting(
    message: types.Message, db_obj: Database, state: FSMContext
):
    """Отображение настроек конкретного канала (статистика и меню)."""
    data = await state.get_data()

    channel = await db.channel.get_channel_by_chat_id(chat_id=data.get("chat_id"))
    channel_settings = await db.channel_bot_settings.get_channel_bot_setting(
        chat_id=channel.chat_id
    )
    count_users = await db_obj.get_count_users(chat_id=channel.chat_id)

    await message.answer(
        text("channel_bot_setting_info").format(
            channel.title,
            count_users["active"],
            count_users["walk_day"],
            count_users["walk_week"],
            count_users["walk_month"],
        ),
        reply_markup=keyboards.bot_setting_menu(channel_settings=channel_settings),
    )


@safe_handler("Bots Setting Choice Channel")
async def choice_channel(
    call: types.CallbackQuery, state: FSMContext, db_obj: Database
):
    """Выбор канала для настройки."""
    temp = call.data.split("|")
    data = await state.get_data()

    if temp[1] in ["next", "back"]:
        channel_ids_in_bot = await db.channel_bot_settings.get_all_channels_in_bot_id(
            bot_id=data.get("bot_id")
        )
        channels = [
            await db.channel.get_channel_by_chat_id(chat.id)
            for chat in channel_ids_in_bot
        ]

        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_for_setting(
                channels=channels, remover=int(temp[2])
            )
        )

    await call.message.delete()

    if temp[1] == "cancel":
        return await show_bot_manage(
            message=call.message, user_bot=data.get("user_bot")
        )

    await state.update_data(chat_id=int(temp[1]))
    await show_channel_setting(call.message, db_obj, state)


@safe_handler("Bots Setting Choice")
async def choice(call: types.CallbackQuery, state: FSMContext, db_obj: Database):
    """Главное меню выбора настроек (приветствия, капча и т.д.)."""
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)
    temp = call.data.split("|")

    if temp[1] == "back":
        if data.get("from_privetka"):
            channels_raw = await db.channel_bot_settings.get_bot_channels(
                call.from_user.id
            )
            channels = await db.channel.get_user_channels(
                call.from_user.id, from_array=[i.id for i in channels_raw]
            )
            return await call.message.edit_text(
                text("privetka_text"),
                reply_markup=keyboards.choice_channel_for_setting(
                    channels=channels, data="PrivetkaChannel"
                ),
                parse_mode="HTML",
            )

        channel_ids_in_bot = await db.channel_bot_settings.get_all_channels_in_bot_id(
            bot_id=data.get("bot_id")
        )
        channels = [
            await db.channel.get_channel_by_chat_id(chat.id)
            for chat in channel_ids_in_bot
        ]
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_for_setting(channels=channels)
        )

    if temp[1] == "update":
        await call.message.delete()
        return await show_channel_setting(call.message, db_obj, state)

    channel_setting = await db.channel_bot_settings.get_channel_bot_setting(
        chat_id=data.get("chat_id")
    )

    menu = {
        "application": {
            "cor": show_application,
            "args": (call.message, channel_setting, db_obj),
        },
        "captcha": {
            "cor": show_captcha,
            "args": (call.message, channel_setting, db_obj),
        },
        "hello": {"cor": show_hello, "args": (call.message, channel_setting)},
        "bye": {"cor": show_bye, "args": (call.message, channel_setting)},
        "clone": {"cor": show_cloner, "args": (call.message, state)},
        "cleaner": {"cor": show_cleaner, "args": (call.message,)},
    }

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


@safe_handler("Bots Show Application")
async def show_application(
    message: types.Message, setting: ChannelBotSetting, db_obj: Database
):
    """Меню настроек автоприема."""
    not_approve_count = await db_obj.get_count_not_approve_users(chat_id=setting.id)

    await message.answer(
        text("application_text"),
        reply_markup=keyboards.manage_application(
            not_approve_count=not_approve_count,
            auto_approve=setting.auto_approve,
            delay_approve=setting.delay_approve,
        ),
    )


@safe_handler("Bots Show Captcha")
async def show_captcha(
    message: types.Message, setting: ChannelBotSetting, db_obj: Database
):
    """Меню настроек капчи."""
    channel_captcha_list = await db.channel_bot_captcha.get_all_captcha(
        chat_id=setting.id
    )
    count_users = await db_obj.get_captcha_users(chat_id=setting.id)

    await message.answer(
        text("choice_captcha").format(*count_users.values()),
        reply_markup=keyboards.choice_channel_captcha(
            channel_captcha_list=channel_captcha_list,
            active_captcha=setting.active_captcha_id,
        ),
    )


@safe_handler("Bots Show Hello")
async def show_hello(message: types.Message, setting: ChannelBotSetting):
    """Меню настроек приветствий."""
    hello_messages = await db.channel_bot_hello.get_hello_messages(chat_id=setting.id)

    await message.answer(
        text("hello_text").format(
            "\n\n".join(
                "{}-е: {}\nЗадержка: {}".format(
                    a,
                    "✅" if HelloAnswer.from_orm(hello_obj).is_active else "❌",
                    HelloAnswer.from_orm(hello_obj).delay,
                )
                for a, hello_obj in enumerate(hello_messages, start=1)
            )
        ),
        reply_markup=keyboards.manage_hello_messages(hello_messages=hello_messages),
    )


@safe_handler("Bots Show Bye")
async def show_bye(message: types.Message, setting: ChannelBotSetting):
    """Меню настроек прощания."""
    hello = ByeAnswer(**setting.bye)

    await message.answer(
        text("bye_text").format(
            text("{}added".format("" if hello.message else "no_")),
            text("on" if hello.active else "off"),
        ),
        reply_markup=keyboards.manage_answer_user(obj=hello, data="ManageBye"),
    )


@safe_handler("Bots Show Cloner")
async def show_cloner(message: types.Message, state: FSMContext):
    """Меню клонирования настроек."""
    data = await state.get_data()

    channel_ids_in_bot = await db.channel_bot_settings.get_all_channels_in_bot_id(
        bot_id=data.get("bot_id")
    )
    channels = [
        await db.channel.get_channel_by_chat_id(chat.id)
        for chat in channel_ids_in_bot
        if data.get("chat_id") != chat.id
    ]

    await state.update_data(chosen=[])

    await message.answer(
        text("cloner"),
        reply_markup=keyboards.choice_channel_for_cloner(channels=channels, chosen=[]),
    )


@safe_handler("Bots Show Cleaner")
async def show_cleaner(message: types.Message):
    """Меню очистки (чистки) участников."""
    await message.answer(text("cleaner"), reply_markup=keyboards.choice_cleaner_type())


def get_router():
    router = Router()
    router.callback_query.register(
        choice_channel, F.data.split("|")[0] == "ChoiceBotSettingChannel"
    )
    router.callback_query.register(choice, F.data.split("|")[0] == "BotSettingMenu")
    return router
