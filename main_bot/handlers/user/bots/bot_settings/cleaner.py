"""
Модуль очистки подписчиков или заявок.

Реализует:
- Выбор типа очистки (бан или отклонение заявок)
- Указание временного периода для очистки
- Асинхронный процесс очистки
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, List

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.user_bot.model import UserBot
from main_bot.handlers.user.bots.bot_settings.menu import show_channel_setting
from main_bot.states.user import Cleaner
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Bots Cleaner Choice")
async def choice(
    call: types.CallbackQuery, state: FSMContext, db_obj: Database
) -> None:
    """
    Выбор типа очистки.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
        db_obj (Database): БД бота.
    """
    temp = call.data.split("|")

    if temp[1] == "cancel":
        await call.message.delete()
        await show_channel_setting(call.message, db_obj, state)
        return

    await state.update_data(cleaner_type=temp[1])

    await call.message.delete()
    await call.message.answer(
        text("input_period_clean"),
        reply_markup=keyboards.back(data="InputCleanerPeriod"),
    )
    await state.set_state(Cleaner.period)


@safe_handler("Bots Cleaner Back")
async def back(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Возврат в меню очистки.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()

    await state.clear()
    await state.update_data(**data)

    await call.message.delete()
    await call.message.answer(
        text("cleaner"), reply_markup=keyboards.choice_cleaner_type()
    )


async def start_clean(
    user_bot: UserBot, cleaner_type: str, users: List[Any], chat_id: int
) -> None:
    """
    Асинхронная задача очистки пользователей.

    Аргументы:
        user_bot (UserBot): Бот, выполняющий очистку.
        cleaner_type (str): Тип очистки ('ban' или отклонение заявок).
        users (List[Any]): Список пользователей для очистки.
        chat_id (int): ID канала.
    """
    async with BotManager(user_bot.token) as manager:
        if not manager.bot:
            return

        for user in users:
            try:
                if cleaner_type == "ban":
                    await manager.bot.ban_chat_member(chat_id, user.id)
                else:
                    await manager.bot.decline_chat_join_request(chat_id, user.id)
            except Exception as e:
                logger.error(f"Error cleaning user: {e}", exc_info=True)

            await asyncio.sleep(0.25)


@safe_handler("Bots Cleaner Get Period")
async def get_period(
    message: types.Message, state: FSMContext, db_obj: Database
) -> None:
    """
    Обработка ввода периода очистки пользователем.
    Запускает процесс очистки в фоне.

    Аргументы:
        message (types.Message): Сообщение с периодом.
        state (FSMContext): Контекст состояния.
        db_obj (Database): БД бота.
    """
    try:
        start, end = message.text.split("-")
        start_date = datetime.strptime(start.strip(), "%d.%m.%Y %H:%M")
        end_date = datetime.strptime(end.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer(text("error_input"))
        return

    data = await state.get_data()
    # Получаем пользователей по времени (participant=True для бана, False для заявок)
    users = await db_obj.get_time_users(
        chat_id=data.get("chat_id"),
        start_time=start_date.timestamp(),
        end_time=end_date.timestamp(),
        participant=data.get("cleaner_type") == "ban",
    )

    asyncio.create_task(
        start_clean(
            data.get("user_bot"), data.get("cleaner_type"), users, data.get("chat_id")
        )
    )

    await state.clear()
    await state.update_data(**data)

    await message.answer("Начал очистку")
    await show_channel_setting(message, db_obj, state)


def get_router() -> Router:
    """
    Регистрация роутеров модуля очистки.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoiceCleanerType")
    router.callback_query.register(back, F.data.split("|")[0] == "InputCleanerPeriod")
    router.message.register(get_period, Cleaner.period, F.text)
    return router
