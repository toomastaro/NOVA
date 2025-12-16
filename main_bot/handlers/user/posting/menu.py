from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.utils.user_settings import get_user_view_mode
import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Выбор в меню постинга")
async def choice(call: types.CallbackQuery, state: FSMContext):
    """Главное меню постинга (создать пост, каналы, контент-план)."""
    await state.clear()
    temp = call.data.split("|")
    logger.info(
        "Пользователь %s выбрал раздел постинга: %s", call.from_user.id, temp[1]
    )

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

    if temp[1] in menu:
        cor, args = menu[temp[1]].values()
        await call.message.delete()
        await cor(*args)
    else:
        logger.warning("Неизвестная команда меню постинга: %s", temp[1])


@safe_handler("Показ создания поста")
async def show_create_post(message: types.Message, state: FSMContext):
    """
    Начало создания поста.

    Новая логика:
    1. Проверка наличия каналов с активной подпиской
    2. Если нет - показ ошибки
    3. Если есть - показ выбора каналов

    Производительность:
    - Параллельная загрузка каналов и папок (asyncio.gather)
    - Limit=500 для защиты от перегрузки при большом кол-ве каналов
    - TODO: добавить индекс (admin_id, subscribe) для ускорения запроса
    - TODO: кеширование в Redis (TTL 1-5 мин) при нагрузке 1000+ админов
    """
    try:
        # Параллельная загрузка каналов и папок для ускорения
        import asyncio

        channels, folders = await asyncio.gather(
            db.channel.get_user_channels(
                user_id=message.chat.id, sort_by="posting", limit=500
            ),
            db.user_folder.get_folders(user_id=message.chat.id),
        )

        view_mode = await get_user_view_mode(message.chat.id)

        logger.info(
            "Пользователь %s: загружено %d каналов для постинга",
            message.chat.id,
            len(channels),
        )
        logger.debug("Загружено папок: %d", len(folders))

        # Проверяем наличие каналов с активной подпиской
        channels_with_sub = [ch for ch in channels if ch.subscribe]
        logger.debug("Каналов с активной подпиской: %d", len(channels_with_sub))

        if not channels_with_sub:
            logger.warning(
                "Пользователь %s попытался создать пост без активной подписки",
                message.chat.id,
            )
            return await message.answer(
                text("error_no_subscription_posting"),
                reply_markup=keyboards.posting_menu(),
            )

        # Инициализируем состояние
        await state.update_data(chosen=[], chosen_folders=[], current_folder_id=None)

        if view_mode == "folders":
            display_channels = []
            display_folders = folders
        else:
            display_channels = channels_with_sub
            display_folders = []

        # Показываем выбор каналов
        await message.answer(
            text("choice_channels:post").format(0, ""),
            reply_markup=keyboards.choice_objects(
                resources=display_channels,
                chosen=[],
                folders=display_folders,
                data="ChoicePostChannels",
                view_mode=view_mode,
            ),
        )

    except Exception as e:
        logger.error(
            "Ошибка при загрузке каналов для пользователя %s: %s",
            message.chat.id,
            str(e),
            exc_info=True,
        )
        await message.answer(
            "❌ Произошла ошибка при загрузке каналов. Попробуйте позже.",
            reply_markup=keyboards.posting_menu(),
        )


@safe_handler("Показ настроек постинга")
async def show_settings(message: types.Message):
    """Показывает меню управления каналами."""
    channels = await db.channel.get_user_channels(
        user_id=message.chat.id, sort_by="posting"
    )
    await message.answer(
        text("channels_text"), reply_markup=keyboards.channels(channels=channels)
    )


@safe_handler("Показ контент-плана")
async def show_content(message: types.Message):
    """Показывает меню выбора канала для контент-плана."""
    channels = await db.channel.get_user_channels(user_id=message.chat.id)
    await message.answer(
        text("choice_channel:content"),
        reply_markup=keyboards.choice_object_content(channels=channels),
    )


@safe_handler("Возврат в главное меню")
async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    from main_bot.keyboards.common import Reply

    await message.answer("Главное меню", reply_markup=Reply.menu())


def get_router():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuPosting")
    return router
