import asyncio
from datetime import datetime

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.user_bot.model import UserBot
from main_bot.handlers.user.bots.bot_settings.menu import show_channel_setting
from main_bot.states.user import Cleaner
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.utils.error_handler import safe_handler
import logging

logger = logging.getLogger(__name__)


@safe_handler("Bots Cleaner Choice")
async def choice(call: types.CallbackQuery, state: FSMContext, db_obj: Database):
    """Выбор типа очистки (удаление/бан)."""
    temp = call.data.split("|")

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_channel_setting(call.message, db_obj, state)

    await state.update_data(cleaner_type=temp[1])

    await call.message.delete()
    await call.message.answer(
        text("input_period_clean"),
        reply_markup=keyboards.back(data="InputCleanerPeriod"),
    )
    await state.set_state(Cleaner.period)


@safe_handler("Bots Cleaner Back")
async def back(call: types.CallbackQuery, state: FSMContext):
    """Возврат в меню очистки."""
    data = await state.get_data()

    await state.clear()
    await state.update_data(**data)

    await call.message.delete()
    await call.message.answer(
        text("cleaner"), reply_markup=keyboards.choice_cleaner_type()
    )


async def start_clean(user_bot: UserBot, cleaner_type: str, users, chat_id: int):
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
async def get_period(message: types.Message, state: FSMContext, db_obj: Database):
    """Обработка ввода периода очистки."""
    try:
        start, end = message.text.split("-")
        start_date = datetime.strptime(start.strip(), "%d.%m.%Y %H:%M")
        end_date = datetime.strptime(end.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        return await message.answer(text("error_input"))

    data = await state.get_data()
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


def get_router():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoiceCleanerType")
    router.callback_query.register(back, F.data.split("|")[0] == "InputCleanerPeriod")
    router.message.register(get_period, Cleaner.period, F.text)
    return router
