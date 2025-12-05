from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.user import Bots
from main_bot.utils.lang.language import text


async def choice(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    temp = call.data.split('|')

    menu = {
        'create_post': {
            'cor': show_choice_channel,
            'args': (call.message, state,)
        },
        'bots': {
            'cor': show_settings,
            'args': (call.message,)
        },
        'content_plan': {
            'cor': show_content,
            'args': (call.message,)
        },
    }

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


async def show_choice_channel(message: types.Message, state: FSMContext):
    """
    Начало создания рассылки для ботов.
    
    Новая логика:
    1. Проверка наличия ботов в каналах
    2. Проверка наличия ботов с активной подпиской
    3. Если нет - показ ошибки
    4. Если есть - показ выбора ботов
    """
    channels = await db.get_bot_channels(message.chat.id)
    if not channels:
        return await message.answer(text('error_no_bots'))
    
    # Получаем ботов пользователя
    bots = await db.get_user_bots(user_id=message.chat.id)
    
    # Проверяем наличие ботов с активной подпиской
    bots_with_sub = [bot for bot in bots if bot.subscribe]
    
    if not bots_with_sub:
        return await message.answer(
            text('error_no_subscription_bots')
        )

    objects = await db.get_user_channels(message.chat.id, from_array=[i.id for i in channels])
    folders = await db.get_folders(message.chat.id)

    data = await state.get_data()
    chosen = data.get("chosen", [])

    await state.update_data(
        chosen=chosen,
        chosen_folders=data.get("chosen_folders", []),
        available=data.get("available", 0)
    )

    await message.answer(
        text("choice_bots:post").format(
            len(chosen),
            "\\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            ) if chosen else "",
            data.get("available", 0)
        ),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            chosen_folders=data.get("chosen_folders", []),
            data="ChoicePostBots"
        )
    )


async def show_create_post(message: types.Message, state: FSMContext):
    await message.answer(
        text('input_message'),
        reply_markup=keyboards.cancel(
            data="InputBotPostCancel"
        )
    )
    await state.set_state(Bots.input_message)


async def show_settings(message: types.Message):
    bots = await db.get_user_bots(
        user_id=message.chat.id,
        sort_by=True
    )
    await message.answer(
        text('bots_text'),
        reply_markup=keyboards.choice_bots(
            bots=bots,
        )
    )


async def show_content(message: types.Message):
    channels = await db.get_bot_channels(message.chat.id)
    objects = await db.get_user_channels(message.chat.id, from_array=[i.id for i in channels])

    await message.answer(
        text('choice_bot:content'),
        reply_markup=keyboards.choice_object_content(
            channels=objects,
            data="ChoiceObjectContentBots"
        )
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuBots")
    return router
