from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.channel_bot_settings.model import ChannelBotSetting
from main_bot.database.db import db
from main_bot.handlers.user.bots.settings import show_bot_manage
from main_bot.utils.lang.language import text
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.schemas import HelloAnswer, ByeAnswer


async def show_channel_setting(message: types.Message, db_obj: Database, state: FSMContext):
    data = await state.get_data()

    channel = await db.get_channel_by_chat_id(
        chat_id=data.get("chat_id")
    )
    channel_settings = await db.get_channel_bot_setting(
        chat_id=channel.chat_id
    )
    count_users = await db_obj.get_count_users(
        chat_id=channel.chat_id
    )

    await message.answer(
        text("channel_bot_setting_info").format(
            channel.title,
            count_users["active"],
            count_users["walk_day"],
            count_users["walk_week"],
            count_users["walk_month"],
        ),
        reply_markup=keyboards.bot_setting_menu(
            channel_settings=channel_settings
        )
    )


async def choice_channel(call: types.CallbackQuery, state: FSMContext, db_obj: Database):
    temp = call.data.split("|")
    data = await state.get_data()

    if temp[1] in ["next", "back"]:
        channel_ids_in_bot = await db.get_all_channels_in_bot_id(
            bot_id=data.get("bot_id")
        )
        channels = [
            await db.get_channel_by_chat_id(chat.id)
            for chat in channel_ids_in_bot
        ]

        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_for_setting(
                channels=channels,
                remover=int(temp[2])
            )
        )

    await call.message.delete()

    if temp[1] == "cancel":
        return await show_bot_manage(
            message=call.message,
            user_bot=data.get("user_bot")
        )

    await state.update_data(
        chat_id=int(temp[1])
    )
    await show_channel_setting(call.message, db_obj, state)


async def choice(call: types.CallbackQuery, state: FSMContext, db_obj: Database):
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)
    temp = call.data.split('|')

    if temp[1] == "back":
        channel_ids_in_bot = await db.get_all_channels_in_bot_id(
            bot_id=data.get("bot_id")
        )
        channels = [
            await db.get_channel_by_chat_id(chat.id)
            for chat in channel_ids_in_bot
        ]
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_for_setting(
                channels=channels
            )
        )

    if temp[1] == "update":
        await call.message.delete()
        return await show_channel_setting(call.message, db_obj, state)

    channel_setting = await db.get_channel_bot_setting(
        chat_id=data.get("chat_id")
    )

    menu = {
        'application': {
            'cor': show_application,
            'args': (call.message, channel_setting, db_obj)
        },
        'captcha': {
            'cor': show_captcha,
            'args': (call.message, channel_setting, db_obj)
        },
        'hello': {
            'cor': show_hello,
            'args': (call.message, channel_setting)
        },
        'bye': {
            'cor': show_bye,
            'args': (call.message, channel_setting)
        },
        'clone': {
            'cor': show_cloner,
            'args': (call.message, state)
        },
        'cleaner': {
            'cor': show_cleaner,
            'args': (call.message,)
        },
    }

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


async def show_application(message: types.Message, setting: ChannelBotSetting, db_obj: Database):
    not_approve_count = await db_obj.get_count_not_approve_users(
        chat_id=setting.id
    )

    await message.answer(
        text("application_text"),
        reply_markup=keyboards.manage_application(
            not_approve_count=not_approve_count,
            auto_approve=setting.auto_approve,
            delay_approve=setting.delay_approve
        )
    )


async def show_captcha(message: types.Message, setting: ChannelBotSetting, db_obj: Database):
    channel_captcha_list = await db.get_all_captcha(
        chat_id=setting.id
    )
    count_users = await db_obj.get_captcha_users(
        chat_id=setting.id
    )

    await message.answer(
        text("choice_captcha").format(
            *count_users.values()
        ),
        reply_markup=keyboards.choice_channel_captcha(
            channel_captcha_list=channel_captcha_list,
            active_captcha=setting.active_captcha_id
        )
    )


async def show_hello(message: types.Message, setting: ChannelBotSetting):
    hello_messages = await db.get_hello_messages(
        chat_id=setting.id
    )

    await message.answer(
        text("hello_text").format(
            "\n\n".join(
                "{}-е: {}\nЗадержка: {}".format(
                    a,
                    '✅' if HelloAnswer.from_orm(hello_obj).is_active else '❌',
                    HelloAnswer.from_orm(hello_obj).delay
                ) for a, hello_obj in enumerate(hello_messages, start=1)
            )
        ),
        reply_markup=keyboards.manage_hello_messages(
            hello_messages=hello_messages
        )
    )


async def show_bye(message: types.Message, setting: ChannelBotSetting):
    hello = ByeAnswer(**setting.bye)

    await message.answer(
        text("bye_text").format(
            text("{}added".format("" if hello.message else "no_")),
            text("on" if hello.active else "off"),
        ),
        reply_markup=keyboards.manage_answer_user(
            obj=hello,
            data="ManageBye"
        )
    )


async def show_cloner(message: types.Message, state: FSMContext):
    data = await state.get_data()

    channel_ids_in_bot = await db.get_all_channels_in_bot_id(
        bot_id=data.get("bot_id")
    )
    channels = [
        await db.get_channel_by_chat_id(chat.id)
        for chat in channel_ids_in_bot if data.get("chat_id") != chat.id
    ]

    await state.update_data(
        chosen=[]
    )

    await message.answer(
        text("cloner"),
        reply_markup=keyboards.choice_channel_for_cloner(
            channels=channels,
            chosen=[]
        )
    )


async def show_cleaner(message: types.Message):
    await message.answer(
        text("cleaner"),
        reply_markup=keyboards.choice_cleaner_type()
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice_channel, F.data.split("|")[0] == "ChoiceBotSettingChannel")
    router.callback_query.register(choice, F.data.split("|")[0] == "BotSettingMenu")
    return router
