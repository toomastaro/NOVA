"""
Модуль клонирования настроек бота между каналами.

Реализует:
- Выбор целевых каналов для клонирования
- Выбор настроек для копирования (автоприем, капча, приветствие, прощание)
- Процесс клонирования настроек
"""

import logging
from typing import List

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.db import db
from main_bot.handlers.user.bots.bot_settings.menu import show_channel_setting
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Боты: клонирование — выбор канала-цели")
async def choice_channel(
    call: types.CallbackQuery, state: FSMContext, db_obj: Database
) -> None:
    """
    Выбор канала-цели для клонирования настроек текущего канала.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
        db_obj (Database): БД бота.
    """
    temp = call.data.split("|")
    data = await state.get_data()

    chosen: list = data.get("chosen")
    channel_ids_in_bot = await db.channel_bot_settings.get_all_channels_in_bot_id(
        bot_id=data.get("bot_id")
    )
    channels = [
        await db.channel.get_channel_by_chat_id(chat.id)
        for chat in channel_ids_in_bot
        if data.get("chat_id") != chat.id
    ]

    if temp[1] in ["next", "back"]:
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_for_cloner(
                channels=channels, chosen=chosen, remover=int(temp[2])
            )
        )
        return

    if temp[1] == "cancel":
        await call.message.delete()
        await show_channel_setting(call.message, db_obj, state)
        return

    if temp[1] == "next_step":
        if not chosen:
            await call.answer("Выберите минимум 1 ресурс!")
            return

        await state.update_data(chosen_settings=[])

        await call.message.delete()
        await call.message.answer(
            text("choice_setting"),
            reply_markup=keyboards.choice_cloner_setting(chosen=[]),
        )
        return

    if temp[1] == "choice_all":
        if len(chosen) == len(channels):
            chosen.clear()
        else:
            chosen.extend([i.chat_id for i in channels])

    channel_id = temp[1]
    if channel_id.replace("-", "").isdigit():
        channel_id = int(channel_id)

        if channel_id in chosen:
            chosen.remove(channel_id)
        else:
            chosen.append(channel_id)

    await state.update_data(chosen=chosen)

    await call.message.edit_reply_markup(
        reply_markup=keyboards.choice_channel_for_cloner(
            channels=channels, chosen=chosen, remover=int(temp[2])
        )
    )


async def start_clone(
    settings: List[int], chat_ids: List[int], current_chat: int
) -> None:
    """
    Выполняет клонирование выбранных настроек из текущего канала в целевые.

    Аргументы:
        settings (List[int]): Список ID выбранных настроек.
        chat_ids (List[int]): Список ID целевых каналов.
        current_chat (int): ID исходного канала.
    """
    channel = await db.channel_bot_settings.get_channel_bot_setting(
        chat_id=current_chat
    )
    hello_messages = await db.channel_bot_hello.get_hello_messages(chat_id=channel.id)
    captcha_list = await db.channel_bot_captcha.get_all_captcha(chat_id=channel.id)

    # application / bye
    if 0 in settings or 3 in settings:
        kwargs = {}

        if 0 in settings:
            kwargs["auto_approve"] = channel.auto_approve
            kwargs["delay_approve"] = channel.delay_approve
        if 3 in settings:
            kwargs["bye"] = channel.bye

        for chat_id in chat_ids:
            await db.channel_bot_settings.update_channel_bot_setting(
                chat_id=chat_id, **kwargs
            )

    # captcha
    # captcha
    if 1 in settings:
        for chat_id in chat_ids:
            captcha_list_remove = await db.channel_bot_captcha.get_all_captcha(
                chat_id=chat_id
            )
            for captcha_remove in captcha_list_remove:
                await db.channel_bot_captcha.delete_captcha(captcha_remove.id)

            new_active_captcha_id = None

            for captcha in captcha_list:
                new_captcha = await db.channel_bot_captcha.add_channel_captcha(
                    return_obj=True,
                    channel_id=chat_id,
                    message=captcha.message,
                    delay=captcha.delay,
                    start_delay=captcha.start_delay,
                )
                if channel.active_captcha_id == captcha.id:
                    new_active_captcha_id = new_captcha.id

            await db.channel_bot_settings.update_channel_bot_setting(
                chat_id=chat_id, active_captcha_id=new_active_captcha_id
            )

    # hello
    if 2 in settings:
        for chat_id in chat_ids:
            hello_messages_remove = await db.channel_bot_hello.get_hello_messages(
                chat_id=chat_id
            )
            for hello_remove in hello_messages_remove:
                await db.channel_bot_hello.delete_hello_message(hello_remove.id)

            for hello in hello_messages:
                max_id = await db.channel_bot_hello.get_next_id_hello_message()
                await db.channel_bot_hello.add_channel_hello_message(
                    id=max_id,
                    channel_id=chat_id,
                    message=hello.message,
                    delay=hello.delay,
                    text_with_name=hello.text_with_name,
                    is_active=hello.is_active,
                )


@safe_handler("Боты: клонирование — выбор настроек")
async def choice(
    call: types.CallbackQuery, state: FSMContext, db_obj: Database
) -> None:
    """
    Меню выбора конкретных настроек для клонирования (галочки).

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
        db_obj (Database): БД бота.
    """
    data = await state.get_data()
    temp = call.data.split("|")

    chosen: list = data.get("chosen")
    chosen_settings: list = data.get("chosen_settings")

    if temp[1] == "cancel":
        channel_ids_in_bot = await db.channel_bot_settings.get_all_channels_in_bot_id(
            bot_id=data.get("bot_id")
        )
        channels = [
            await db.channel.get_channel_by_chat_id(chat.id)
            for chat in channel_ids_in_bot
            if data.get("chat_id") != chat.id
        ]

        await call.message.delete()
        await call.message.answer(
            text("cloner"),
            reply_markup=keyboards.choice_channel_for_cloner(
                channels=channels, chosen=chosen
            ),
        )
        return

    if temp[1] == "clone":
        if not chosen_settings:
            await call.answer("Выберите минимум 1 настройку!")
            return

        await start_clone(chosen_settings, chosen, data.get("chat_id"))

        await call.message.delete()
        await call.message.answer(text("success_clone"))

        await show_channel_setting(call.message, db_obj, state)
        return

    setting_key = int(temp[1])
    if setting_key in chosen_settings:
        chosen_settings.remove(setting_key)
    else:
        chosen_settings.append(setting_key)

    await state.update_data(chosen_settings=chosen_settings)

    await call.message.edit_reply_markup(
        reply_markup=keyboards.choice_cloner_setting(chosen=chosen_settings)
    )


def get_router() -> Router:
    """
    Регистрация роутеров модуля клонировани.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.callback_query.register(
        choice_channel, F.data.split("|")[0] == "ChoiceClonerTarget"
    )
    router.callback_query.register(
        choice, F.data.split("|")[0] == "ChoiceClonerSetting"
    )
    return router
