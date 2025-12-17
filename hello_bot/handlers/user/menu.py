"""
Модуль главного меню hello_bot.

Содержит функции для отображения разделов меню (статистика, ответы, приветствие, прощание, заявки).
"""

from datetime import datetime

from loguru import logger

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext


from hello_bot.database.db import Database
from hello_bot.utils.functions import get_protect_tag
from hello_bot.utils.lang.language import text
from hello_bot.keyboards.keyboards import keyboards
from hello_bot.utils.schemas import HelloAnswer, ByeAnswer, Protect


async def choice(call: types.CallbackQuery, state: FSMContext, db: Database, settings):
    """
    Обрабатывает навигацию в главном меню.

    :param call: CallbackQuery
    :param state: FSMContext
    :param db: Database instance
    :param settings: Channel settings
    """
    await state.clear()
    temp = call.data.split("|")
    logger.debug(f"Menu choice: {temp}")

    menu = {
        "stats": {
            "cor": show_stats,
            "args": (
                call.message,
                db,
                settings,
            ),
        },
        "answer": {
            "cor": show_answers,
            "args": (
                call.message,
                settings,
            ),
        },
        "hello": {"cor": show_hello, "args": (call.message, settings)},
        "bye": {"cor": show_bye, "args": (call.message, settings)},
        "application": {"cor": show_application, "args": (call.message, settings)},
    }

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


async def show_stats(message: types.Message, db: Database, setting):
    """Показывает статистику бота."""
    count_users = await db.get_count_users()

    await message.answer(
        text("stats_text").format(
            (await message.bot.get_me()).username,
            *count_users.values(),
            setting.input_messages,
            setting.output_messages,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
        ),
        reply_markup=keyboards.back(data="StatsBack"),
    )


async def show_answers(message: types.Message, setting):
    """Показывает меню управления автоответами."""
    await message.answer(
        text("answer_text"), reply_markup=keyboards.answers(settings=setting)
    )


async def show_hello(message: types.Message, setting):
    """Показывает меню управления приветствием."""
    hello = HelloAnswer(**setting.hello)

    await message.answer(
        text("hello_text").format(
            text("{}added".format("" if hello.message else "no_")),
            text("on" if hello.active else "off"),
        ),
        reply_markup=keyboards.manage_answer_user(obj=hello),
    )


async def show_bye(message: types.Message, setting):
    """Показывает меню управления прощанием."""
    hello = ByeAnswer(**setting.bye)

    await message.answer(
        text("bye_text").format(
            text("{}added".format("" if hello.message else "no_")),
            text("on" if hello.active else "off"),
        ),
        reply_markup=keyboards.manage_answer_user(obj=hello, data="ManageBye"),
    )


async def show_application(message: types.Message, setting):
    """Показывает меню управления заявками (автоприем, защита)."""
    protect = Protect(**setting.protect)
    protect_tag = get_protect_tag(protect)

    await message.answer(
        text("application_text").format(
            text("on" if setting.auto_approve else "off"),
            text("on" if protect.arab or protect.china else "off"),
            text("protect:{}".format(protect_tag)) if protect_tag else "",
            setting.delay_approve,
        ),
        reply_markup=keyboards.manage_application(setting=setting),
    )


def hand_add():
    """Регистрация хэндлеров меню."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Menu")
    return router
