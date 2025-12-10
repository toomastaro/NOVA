from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.user import Posting
from main_bot.utils.lang.language import text
from main_bot.utils.logger import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Posting Menu Choice")
async def choice(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    temp = call.data.split('|')

    menu = {
        'create_post': {
            'cor': show_create_post,
            'args': (call.message, state,)
        },
        'channels': {
            'cor': show_settings,
            'args': (call.message,)
        },
        'content_plan': {
            'cor': show_content,
            'args': (call.message,)
        },
        'back': {
            'cor': back_to_main,
            'args': (call.message,)
        },
    }

    if temp[1] in menu:
        cor, args = menu[temp[1]].values()
        await call.message.delete()
        await cor(*args)
    else:
        logger.warning(f"Unknown posting menu command: {temp[1]}")


@safe_handler("Posting Show Create Post")
async def show_create_post(message: types.Message, state: FSMContext):
    """
    Начало создания поста.
    
    Новая логика:
    1. Проверка наличия каналов с активной подпиской
    2. Если нет - показ ошибки
    3. Если есть - показ выбора каналов
    """
    # Получаем каналы пользователя с сортировкой по posting
    channels = await db.get_user_channels(
        user_id=message.chat.id,
        sort_by="posting"
    )
    
    # Проверяем наличие каналов с активной подпиской
    channels_with_sub = [ch for ch in channels if ch.subscribe]
    
    if not channels_with_sub:
        return await message.answer(
            text('error_no_subscription_posting'),
            reply_markup=keyboards.posting_menu()
        )
    
    # Получаем папки
    folders = await db.get_folders(user_id=message.chat.id)
    
    # Инициализируем состояние
    await state.update_data(
        chosen=[],
        chosen_folders=[],
        current_folder_id=None
    )
    
    # Показываем выбор каналов
    await message.answer(
        text("choice_channels:post").format(0, ""),
        reply_markup=keyboards.choice_objects(
            resources=channels_with_sub,
            chosen=[],
            folders=folders,
            data="ChoicePostChannels"
        )
    )


@safe_handler("Posting Show Settings")
async def show_settings(message: types.Message):
    channels = await db.get_user_channels(
        user_id=message.chat.id,
        sort_by="posting"
    )
    await message.answer(
        text('channels_text'),
        reply_markup=keyboards.channels(
            channels=channels
        )
    )


@safe_handler("Posting Show Content")
async def show_content(message: types.Message):
    channels = await db.get_user_channels(
        user_id=message.chat.id
    )
    await message.answer(
        text('choice_channel:content'),
        reply_markup=keyboards.choice_object_content(
            channels=channels
        )
    )


@safe_handler("Posting Back To Main")
async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    from main_bot.keyboards.common import Reply
    await message.answer(
        "Главное меню",
        reply_markup=Reply.menu()
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuPosting")
    return router
