from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Stories Menu Choice")
async def choice(call: types.CallbackQuery, state: FSMContext):
    """Главное меню историй (создать, каналы, контент-план)."""
    await state.clear()
    temp = call.data.split("|")

    menu = {
        "create_post": {
            "cor": show_create_post,
            "args": (
                call.message,
                state,
            ),
        },
        "channels": {"cor": show_settings, "args": (call.message,)},
        "content_plan": {"cor": show_content, "args": (call.message,)},
        "back": {"cor": back_to_main, "args": (call.message,)},
    }

    if temp[1] not in menu:
        logger.warning(f"Неизвестная опция меню: {temp[1]}")
        return await call.answer("Неизвестная опция")

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


@safe_handler("Stories Show Create Post")
async def show_create_post(message: types.Message, state: FSMContext):
    """
    Начало создания истории.

    Новая логика:
    1. Проверка наличия каналов с активной подпиской
    2. Если нет - показ ошибки
    3. Если есть - показ выбора каналов
    """
    logger.info(f"Пользователь {message.from_user.id} начал процесс создания сторис")

    # Получаем каналы пользователя с сортировкой по stories
    channels = await db.channel.get_user_channels(
        user_id=message.chat.id, sort_by="stories"
    )

    # Проверяем наличие каналов с активной подпиской
    channels_with_sub = [ch for ch in channels if ch.subscribe]

    if not channels_with_sub:
        return await message.answer(text("error_no_subscription_stories"))

    # Получаем папки
    folders = await db.user_folder.get_folders(user_id=message.chat.id)

    # Инициализируем состояние
    await state.update_data(chosen=[], chosen_folders=[], current_folder_id=None)

    # Показываем выбор каналов
    await message.answer(
        text("choice_channels:story").format(0, ""),
        reply_markup=keyboards.choice_objects(
            resources=channels_with_sub,
            chosen=[],
            folders=folders,
            data="ChoiceStoriesChannels",
        ),
    )


@safe_handler("Stories Show Settings")
async def show_settings(message: types.Message):
    """Показывает меню управления каналами для историй."""
    channels = await db.channel.get_user_channels(
        user_id=message.chat.id, sort_by="stories"
    )
    await message.answer(
        text("channels_text"),
        reply_markup=keyboards.channels(channels=channels, data="ChoiceStoriesChannel"),
    )


@safe_handler("Stories Show Content")
async def show_content(message: types.Message):
    """Показывает меню выбора канала для контент-плана историй."""
    channels = await db.channel.get_user_channels(user_id=message.chat.id)
    await message.answer(
        text("choice_channel:content:story"),
        reply_markup=keyboards.choice_object_content(
            channels=channels, data="ChoiceObjectContentStories"
        ),
    )


@safe_handler("Stories Back To Main")
async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    from main_bot.keyboards.common import Reply

    await message.answer("Главное меню", reply_markup=Reply.menu())


def get_router():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuStories")
    return router
