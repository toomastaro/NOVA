"""
Модуль для управления меню ботов.

Реализует:
- Навигацию по меню ботов
- Выборканалов для рассылки
- Отображение настроек ботов
- Отображение контент-плана
"""

import logging


from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.user import Bots
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler
from main_bot.utils.user_settings import get_user_view_mode

logger = logging.getLogger(__name__)


@safe_handler(
    "Боты: выбор в меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора в меню ботов.
    Маршрутизирует действия (создать пост, настройки, контент-план, назад).

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await state.clear()
    temp = call.data.split("|")

    menu = {
        "create_post": {
            "cor": show_choice_channel,
            "args": (
                call.message,
                state,
            ),
        },
        "bots": {"cor": show_settings, "args": (call.message,)},
        "content_plan": {"cor": show_content, "args": (call.message,)},
        "back": {"cor": back_to_main, "args": (call.message,)},
    }

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


@safe_handler(
    "Боты: выбор канала для рассылки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_choice_channel(message: types.Message, state: FSMContext) -> None:
    """
    Начало создания рассылки для ботов.
    Отображает выбор каналов/папок для рассылки.

    Логика:
    1. Проверка наличия ботов в каналах
    2. Проверка наличия активной подписки у каналов
    3. Если нет - показ ошибки
    4. Если есть - показ выбора каналов/папок

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    channels_raw = await db.channel_bot_settings.get_bot_channels(
        message.chat.id, only_with_bot=True
    )
    if not channels_raw:
        await message.answer(text("error_no_bots"))
        return

    # Получаем полные объекты каналов для проверки подписки
    objects = await db.channel.get_user_channels(
        message.chat.id, from_array=[i.id for i in channels_raw]
    )

    # Проверяем наличие каналов с активной подпиской
    has_active_sub = any(obj.subscribe for obj in objects)

    if not has_active_sub:
        await message.answer(text("error_no_subscription_bots"))
        return

    folders = await db.user_folder.get_folders(message.chat.id)

    view_mode = await get_user_view_mode(message.chat.id)

    data = await state.get_data()
    chosen = data.get("chosen", [])

    await state.update_data(
        chosen=chosen,
        chosen_folders=data.get("chosen_folders", []),
        available=data.get("available", 0),
        current_folder_id=None,
    )

    # Фильтрация списков для отображения
    if view_mode == "folders":
        # Показываем только папки, в которых есть каналы, доступные для рассылки (привязанные к боту)
        kb_folders = [f for f in folders if f.content]
        kb_resources = []
    else:
        kb_resources = objects
        kb_folders = []

    await message.answer(
        text("choice_bots:post").format(
            len(chosen),
            (
                "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                )
                if chosen
                else ""
            ),
            data.get("available", 0),
        ),
        reply_markup=keyboards.choice_objects(
            resources=kb_resources,
            chosen=chosen,
            folders=kb_folders,
            chosen_folders=data.get("chosen_folders", []),
            data="ChoicePostBots",
            view_mode=view_mode,
        ),
    )


@safe_handler(
    "Боты: ввод сообщения поста"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_create_post(message: types.Message, state: FSMContext) -> None:
    """
    Переход к вводу сообщения для поста.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    await message.answer(
        text("input_message"), reply_markup=keyboards.cancel(data="InputBotPostCancel")
    )
    await state.set_state(Bots.input_message)


@safe_handler(
    "Боты: меню настроек"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_settings(message: types.Message) -> None:
    """
    Отображение списка ботов для настроек.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    bots = await db.user_bot.get_user_bots(user_id=message.chat.id, sort_by=True)
    await message.answer(
        text("bots_text"),
        reply_markup=keyboards.choice_bots(
            bots=bots,
        ),
    )


@safe_handler(
    "Боты: контент-план"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_content(message: types.Message) -> None:
    """
    Отображение контент-плана (выбор канала).

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    channels = await db.channel_bot_settings.get_bot_channels(
        message.chat.id, only_with_bot=True
    )
    objects = await db.channel.get_user_channels(
        message.chat.id, from_array=[i.id for i in channels]
    )

    await message.answer(
        text("choice_bot:content"),
        reply_markup=keyboards.choice_object_content(
            channels=objects, data="ChoiceObjectContentBots"
        ),
    )


@safe_handler(
    "Боты: возврат в главное меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_to_main(message: types.Message) -> None:
    """
    Возврат в главное меню бота.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    from main_bot.keyboards.common import Reply

    await message.answer("Главное меню", reply_markup=Reply.menu())


def get_router() -> Router:
    """
    Регистрация роутера меню ботов.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuBots")
    return router
