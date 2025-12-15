import asyncio
import time

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.channel_bot_settings.model import ChannelBotSetting
from main_bot.database.db import db
from main_bot.database.user_bot.model import UserBot
from main_bot.handlers.user.bots.bot_settings.menu import show_application, show_channel_setting
from main_bot.states.user import Application
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards


async def choice(call: types.CallbackQuery, state: FSMContext, db_obj: Database, channel_settings: ChannelBotSetting):
    temp = call.data.split('|')

    if temp[1] == "...":
        return await call.answer()

    await call.message.delete()

    if temp[1] == "cancel":
        return await show_channel_setting(call.message, db_obj, state)

    if temp[1] == "auto_approve":
        await db.channel_bot_settings.update_channel_bot_setting(
            chat_id=channel_settings.id,
            auto_approve=not channel_settings.auto_approve
        )
        channel_settings = await db.channel_bot_settings.get_channel_bot_setting(
            chat_id=channel_settings.id
        )
        return await show_application(call.message, channel_settings, db_obj)

    if temp[1] == "delay":
        await call.message.answer(
            text("application:delay"),
            reply_markup=keyboards.choice_application_delay(
                current=channel_settings.delay_approve
            )
        )

    if temp[1] == "manual_approve":
        not_approve_count = await db_obj.get_count_not_approve_users(
            chat_id=channel_settings.id
        )
        await call.message.answer(
            text("application:manual_approve").format(
                not_approve_count
            ),
            reply_markup=keyboards.choice_manual_approve()
        )


async def back(call: types.CallbackQuery, channel_settings: ChannelBotSetting, db_obj: Database):
    await call.message.delete()
    return await show_application(call.message, channel_settings, db_obj)


async def choice_application_delay(call: types.CallbackQuery, db_obj: Database, channel_settings: ChannelBotSetting):
    temp = call.data.split('|')
    await call.message.delete()

    if temp[1] == "cancel":
        return await show_application(call.message, channel_settings, db_obj)

    delay_approve = int(temp[1])

    await db.channel_bot_settings.update_channel_bot_setting(
        chat_id=channel_settings.id,
        delay_approve=delay_approve
    )
    channel_settings = await db.channel_bot_settings.get_channel_bot_setting(
        chat_id=channel_settings.id
    )
    await call.message.answer(
        text("application:delay"),
        reply_markup=keyboards.choice_application_delay(
            current=channel_settings.delay_approve
        )
    )


async def approve(user_bot: UserBot, chat_id: int, users, db_obj: Database):
    async with BotManager(token=user_bot.token) as manager:
        if not manager.bot:
            return

        for user in users:
            try:
                await manager.bot.approve_chat_join_request(chat_id, user.id)
                await db_obj.update_user(user.id, is_approved=True, time_approved=int(time.time()))
            except Exception as e:
                print(e)

            await asyncio.sleep(0.25)


async def choice_manual_approve(
        call: types.CallbackQuery,
        state: FSMContext,
        db_obj: Database,
        db_bot: UserBot,
        channel_settings: ChannelBotSetting
):
    temp = call.data.split("|")
    data = await state.get_data()

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_application(call.message, channel_settings, db_obj)

    not_approve_users = await db_obj.get_not_approve_users_by_chat_id(
        chat_id=data.get("chat_id")
    )
    await state.update_data(
        not_approve_users_count=len(not_approve_users)
    )

    if temp[1] == "all":
        asyncio.create_task(
            approve(db_bot, data.get("chat_id"), not_approve_users, db_obj)
        )
        await call.answer("Начал принимать", show_alert=True)

        await call.message.delete()
        await show_application(call.message, channel_settings, db_obj)

    if temp[1] == "part":
        await call.message.delete()
        await call.message.answer(
            text("input_approve_count").format(
                len(not_approve_users)
            ),
            reply_markup=keyboards.back(
                data="InputApproveCountBack"
            )
        )
        await state.set_state(Application.part)

    if temp[1] == "invite_url":
        invite_urls = await db_obj.get_invite_urls(data.get("chat_id"))

        await call.message.delete()
        await call.message.answer(
            text("choice_invite_url"),
            reply_markup=keyboards.choice_invite_url(
                invite_urls=invite_urls
            )
        )


async def input_back(
        call: types.CallbackQuery, state: FSMContext, db_obj: Database, channel_settings: ChannelBotSetting
):
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)

    not_approve_count = await db_obj.get_count_not_approve_users(
        chat_id=channel_settings.id
    )

    await call.message.delete()
    await call.message.answer(
        text("application:manual_approve").format(
            not_approve_count
        ),
        reply_markup=keyboards.choice_manual_approve()
    )


async def get_count_part(
        message: types.Message, state: FSMContext,
        db_obj: Database, db_bot: UserBot, channel_settings: ChannelBotSetting
):
    data = await state.get_data()

    try:
        count = int(message.text)
        if count > data.get("not_approve_users_count"):
            raise ValueError()

    except ValueError:
        return await message.answer(
            text("error_input")
        )

    await state.clear()
    await state.update_data(**data)

    not_approve_users = await db_obj.get_not_approve_users_by_chat_id(
        chat_id=data.get("chat_id"),
        limit=count
    )

    asyncio.create_task(
        approve(db_bot, data.get("chat_id"), not_approve_users, db_obj)
    )

    await message.answer("Начал принимать")
    await show_application(message, channel_settings, db_obj)


async def choice_invite_url(
    call: types.CallbackQuery, state: FSMContext, db_obj: Database, db_bot: UserBot, channel_settings: ChannelBotSetting
):
    temp = call.data.split('|')
    data = await state.get_data()

    if temp[1] == "cancel":
        not_approve_count = await db_obj.get_count_not_approve_users(
            chat_id=channel_settings.id
        )

        await call.message.delete()
        return await call.message.answer(
            text("application:manual_approve").format(
                not_approve_count
            ),
            reply_markup=keyboards.choice_manual_approve()
        )

    not_approve_users = await db_obj.get_not_approve_users_by_chat_id(
        chat_id=channel_settings.id,
        invite_url=temp[1]
    )

    asyncio.create_task(
        approve(db_bot, data.get("chat_id"), not_approve_users, db_obj)
    )
    await call.answer("Начал принимать", show_alert=True)

    await call.message.delete()
    await show_application(call.message, channel_settings, db_obj)


def get_router():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ManageApplication")
    router.callback_query.register(back, F.data.split("|")[0] == "AddDelayBack")
    router.callback_query.register(choice_application_delay, F.data.split("|")[0] == "ChoiceApplicationDelay")

    router.callback_query.register(choice_manual_approve, F.data.split("|")[0] == "ChoiceManualApprove")
    router.callback_query.register(input_back, F.data.split("|")[0] == "InputApproveCountBack")

    router.message.register(get_count_part, Application.part, F.text)
    router.callback_query.register(choice_invite_url, F.data.split("|")[0] == "ChoiceInviteUrlApplication")

    return router
