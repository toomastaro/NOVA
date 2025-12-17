"""
Модуль настроек ботов.

Реализует:
- Управление ботами пользователя (добавление, удаление, настройки)
- Получение токена и валидацию
- Импорт/экспорт базы пользователей бота
"""

import csv
import logging
import os
import time
from typing import Any, Dict, Union

import pandas as pd
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.db import db
from main_bot.database.user_bot.model import UserBot
from main_bot.states.user import AddBot
from main_bot.handlers.user.menu import start_bots
from main_bot.handlers.user.bots.menu import show_settings
from main_bot.keyboards import keyboards
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.functions import create_emoji
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


class DictObj:
    """Вспомогательный класс для преобразования ключей словаря в атрибуты."""

    def __init__(self, in_dict: Dict[str, Any]):
        for key, val in in_dict.items():
            setattr(self, key, val)


def ensure_bot_obj(bot: Union[UserBot, Dict[str, Any]]) -> Union[UserBot, DictObj]:
    """
    Гарантирует, что входные данные являются объектом с атрибутами, а не словарем.

    Аргументы:
        bot: Объект UserBot или словарь.

    Возвращает:
        UserBot или DictObj.
    """
    if isinstance(bot, dict):
        return DictObj(bot)
    return bot


def serialize_user_bot(bot: Any) -> Union[Dict[str, Any], None]:
    """
    Сериализует объект бота пользователя в словарь.
    """
    if not bot:
        return None
    return {
        "id": bot.id,
        "admin_id": bot.admin_id,
        "token": bot.token,
        "username": bot.username,
        "title": bot.title,
        "schema": getattr(bot, "schema", None),
        "created_timestamp": getattr(bot, "created_timestamp", None),
        "emoji_id": getattr(bot, "emoji_id", None),
        "subscribe": getattr(bot, "subscribe", None),
    }


@safe_handler("Bots Show Bot Manage")
async def show_bot_manage(
    message: types.Message, user_bot: Union[UserBot, Dict[str, Any]]
) -> None:
    """
    Отображение панели управления конкретным ботом.
    Показывает инфо о боте, статистику пользователей, каналы и статус.

    Аргументы:
        message (types.Message): Сообщение для ответа.
        user_bot: Объект бота или словарь данных.
    """
    user_bot = ensure_bot_obj(user_bot)

    bot_database = Database()
    bot_database.schema = user_bot.schema

    count_users = await bot_database.get_count_users()

    channel_ids_in_bot = await db.channel_bot_settings.get_all_channels_in_bot_id(
        bot_id=user_bot.id
    )
    channels = [
        await db.channel.get_channel_by_chat_id(chat.id) for chat in channel_ids_in_bot
    ]

    async with BotManager(user_bot.token) as bot_manager:
        status = await bot_manager.status()

    await message.answer(
        text("bot:info").format(
            user_bot.title,
            (
                "\n".join(
                    text("resource_title").format(channel.title) for channel in channels
                )
                if channels
                else "❌"
            ),
            "✅" if status else "❌",
            count_users.get("active"),
            count_users.get("total"),
        ),
        reply_markup=keyboards.manage_bot(user_bot=user_bot, status=status),
    )


@safe_handler("Bots Settings Choice")
async def choice(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Выбор бота для настройки или добавления нового.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")

    if temp[1] in ["next", "back"]:
        bots = await db.user_bot.get_user_bots(user_id=call.from_user.id, sort_by=True)
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_bots(bots=bots, remover=int(temp[2]))
        )
        return

    if temp[1] == "cancel":
        await call.message.delete()
        # Возврат в меню настроек (профиль)
        await call.message.answer(
            text("start_profile_text"),
            reply_markup=keyboards.profile_menu(),
            parse_mode="HTML",
        )
        return

    if temp[1] == "add":
        await call.message.edit_text(
            text=text("bots:add:text"), reply_markup=keyboards.back(data="BackAddBot")
        )
        await state.set_state(AddBot.input_token)
        return

    bot_id = int(temp[1])
    user_bot = await db.user_bot.get_bot_by_id(bot_id)

    await state.update_data(user_bot=serialize_user_bot(user_bot), bot_id=user_bot.id)

    await call.message.delete()
    await show_bot_manage(call.message, user_bot)


@safe_handler("Bots Settings Cancel")
async def cancel(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Отмена действия и возврат к списку ботов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    bots = await db.user_bot.get_user_bots(user_id=call.from_user.id, sort_by=True)

    await state.clear()
    await call.message.edit_text(
        text("start_bots_text"),
        reply_markup=keyboards.choice_bots(
            bots=bots,
        ),
        parse_mode="HTML",
    )


@safe_handler("Bots Get Token")
async def get_token(message: types.Message, state: FSMContext) -> None:
    """
    Обработка введенного токена бота.
    Валидирует токен, проверяет существование, устанавливает вебхук
    и добавляет бота в систему.

    Аргументы:
        message (types.Message): Сообщение с токеном.
        state (FSMContext): Контекст состояния.
    """
    token = message.text
    if message.forward_from:
        try:
            token = message.text.split("API:")[1].split("Keep")[0].strip()
        except IndexError:
            token = ""

    bot_manager = BotManager(token)
    is_valid = await bot_manager.validate_token()
    if not is_valid:
        await message.answer(
            text("error_valid_token"), reply_markup=keyboards.cancel(data="BackAddBot")
        )
        return

    bot_id = is_valid.id
    exist = await db.user_bot.get_bot_by_id(bot_id)
    if exist:
        await message.answer(
            text("error_exist_token"), reply_markup=keyboards.cancel(data="BackAddBot")
        )
        return

    username = is_valid.username
    title = is_valid.full_name

    success_start = await bot_manager.set_webhook()
    if not success_start:
        await message.answer(
            text("error_valid_token"), reply_markup=keyboards.cancel(data="BackAddBot")
        )
        return

    photo_bytes = None
    get_photo = await bot_manager.bot.get_user_profile_photos(bot_id)
    if get_photo.total_count > 0:
        photo_bytes = await bot_manager.bot.download(get_photo.photos[0][-1].file_id)
    await bot_manager.close()

    emoji_id = await create_emoji(user_id=message.from_user.id, photo_bytes=photo_bytes)
    schema = "hello_{}_{}".format(message.from_user.id, username)
    await db.user_bot.add_bot(
        id=bot_id,
        admin_id=message.from_user.id,
        schema=schema,
        token=token,
        username=username,
        title=title,
        emoji_id=emoji_id,
    )

    bot_database = Database()
    bot_database.schema = schema
    await bot_database.create_tables()

    await state.clear()
    await message.answer(
        text("success_add_bot"), reply_markup=keyboards.back(data="BackAddBot")
    )


@safe_handler("Bots Manage Bot")
async def manage_bot(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Управление настройками бота.
    Обрабатывает действия: удаление, проверка токена, обновление, импорт/экспорт.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    data = await state.get_data()

    if not data and len(temp) > 2:
        try:
            bot_id = int(temp[2])
            user_bot = await db.get_user_bot(bot_id)
            if user_bot:
                await state.update_data(bot_id=bot_id, user_bot=serialize_user_bot(user_bot))
                data = await state.get_data()
        except Exception:
            pass

    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    if temp[1] in ["cancel", "delete"]:
        if temp[1] == "delete":
            await call.message.edit_text(
                text("delete:bot"),
                reply_markup=keyboards.accept(data="AcceptDeleteBot"),
            )
            return

        await call.message.delete()
        await show_settings(call.message)
        return

    if temp[1] in ["check_token", "channel"]:
        if temp[1] == "channel":
            message_text = text("delete_channel:bot")
        else:
            async with BotManager(
                ensure_bot_obj(data.get("user_bot")).token
            ) as bot_manager:
                is_valid = await bot_manager.validate_token()

            message_text = text("token_{}valid".format("" if is_valid else "not_"))

        await call.answer(message_text, show_alert=True)
        return

    if temp[1] == "refresh_token":
        await call.message.edit_text(
            text("input_token"), reply_markup=keyboards.back(data="BackRefreshToken")
        )
        await state.set_state(AddBot.update_token)
        return

    if temp[1] == "status":
        async with BotManager(
            ensure_bot_obj(data.get("user_bot")).token
        ) as bot_manager:
            status = await bot_manager.status()
            await bot_manager.set_webhook(delete=status)

        await call.message.delete()
        await show_bot_manage(call.message, data.get("user_bot"))
        return

    if temp[1] == "import_db":
        await call.message.edit_text(
            text("input_import_file"),
            reply_markup=keyboards.back(data="BackImportFile"),
        )
        await state.set_state(AddBot.import_file)
        return

    if temp[1] == "export_db":
        await call.message.edit_text(
            text("choice_export_type"), reply_markup=keyboards.export_type()
        )
        return

    if temp[1] == "settings":
        channel_ids_in_bot = await db.channel_bot_settings.get_all_channels_in_bot_id(
            bot_id=data.get("bot_id")
        )
        if not channel_ids_in_bot:
            await call.answer(text("not_have_channels"), show_alert=True)
            return

        channels = [
            await db.channel.get_channel_by_chat_id(chat.id)
            for chat in channel_ids_in_bot
        ]
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_for_setting(channels=channels)
        )


@safe_handler("Bots Update Token")
async def update_token(message: types.Message, state: FSMContext) -> None:
    """
    Обновление токена существующего бота.

    Аргументы:
        message (types.Message): Сообщение с новым токеном.
        state (FSMContext): Контекст состояния.
    """
    token = message.text
    data = await state.get_data()
    user_bot: UserBot = ensure_bot_obj(data.get("user_bot"))

    async with BotManager(token) as bot_manager:
        me = await bot_manager.validate_token()
        if not me:
            await message.answer(
                text("error_valid_token"),
                reply_markup=keyboards.cancel(data="BackRefreshToken"),
            )
            return
        if user_bot.username != me.username:
            await message.answer(
                text("error_valid_token"),
                reply_markup=keyboards.cancel(data="BackRefreshToken"),
            )
            return
        if user_bot.admin_id != message.from_user.id:
            await message.answer(
                text("error_valid_token"),
                reply_markup=keyboards.cancel(data="BackRefreshToken"),
            )
            return

        user_bot = await db.user_bot.update_bot_by_id(
            row_id=user_bot.id, return_obj=True, token=token
        )
        await bot_manager.set_webhook()

    await state.update_data(user_bot=serialize_user_bot(user_bot))
    await show_bot_manage(message, user_bot)


@safe_handler("Bots Back Update")
async def back_update(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Возврат после обновления или ошибки.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    user_bot = data.get("user_bot")

    await call.message.delete()
    await state.clear()
    await state.update_data(data)

    await show_bot_manage(call.message, user_bot)


@safe_handler("Bots Delete Bot")
async def delete_bot(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Удаление бота из системы.
    Удаляет бота из базы и сбрасывает вебхук.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    await call.message.delete()

    if len(temp) == 2 and temp[1] == "yes":
        user_bot = ensure_bot_obj(data.get("user_bot"))
        await db.user_bot.delete_bot_by_id(row_id=user_bot.id)
        other_db = Database()
        other_db.schema = user_bot.schema
        await other_db.drop_schema()

        async with BotManager(user_bot.token) as bot_manager:
            await bot_manager.set_webhook(delete=True)

        await state.clear()
        await start_bots(call.message)
        return

    await show_bot_manage(call.message, data.get("user_bot"))


@safe_handler("Bots Get Import File")
async def get_import_file(message: types.Message, state: FSMContext) -> None:
    """
    Импорт базы пользователей из файла (txt, xlsx, csv).

    Аргументы:
        message (types.Message): Сообщение с файлом.
        state (FSMContext): Контекст состояния.
    """
    file = await message.bot.get_file(message.document.file_id)
    file_name = file.file_path.split("/")[-1]
    extension = file_name.split(".")[1].lower()

    if extension not in ["txt", "xlsx", "csv"]:
        await message.answer(
            text("error_input_file"), reply_markup=keyboards.back(data="BackImportFile")
        )
        return

    filepath = "main_bot/utils/temp/import_" + file_name
    await message.bot.download(message.document.file_id, filepath)

    try:
        users = []
        if extension == "txt":
            with open(filepath, "r") as file:
                users = [
                    {"id": int(i.strip())}
                    for i in file.readlines()
                    if i.strip().isdigit()
                ]
        elif extension == "csv":
            with open(filepath, "r", encoding="utf-8-sig") as file:
                read = csv.reader(file)
            users = [{"id": int(i[0])} for i in read if i[0].isdigit()]
        else:
            file_data = pd.read_excel(filepath, header=None)
            users = [{"id": i} for i in file_data[0] if isinstance(i, int)]

        data = await state.get_data()
        other_db = Database()
        other_db.schema = ensure_bot_obj(data.get("user_bot")).schema

        await other_db.many_insert_user(users)

    except Exception as e:
        logger.error(f"Error importing file: {e}")
        await message.answer(text("error_import"))
        return
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

    await state.clear()
    await state.update_data(data)

    await message.answer(text("success_import"))
    await show_bot_manage(message, data.get("user_bot"))


@safe_handler("Bots Choice Export")
async def choice_export(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Экспорт базы пользователей в файл.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    if temp[1] == "cancel":
        await call.message.delete()
        await show_bot_manage(call.message, data.get("user_bot"))
        return

    other_db = Database()
    other_db.schema = ensure_bot_obj(data.get("user_bot")).schema

    users = await other_db.get_dump_users()
    if not users:
        await call.answer(text("error_empty_users"))
        return

    await call.message.delete()
    await call.message.answer(text("start_export"))
    await show_bot_manage(call.message, data.get("user_bot"))

    filepath = "main_bot/utils/temp/export_users_{}_{}.{}".format(
        ensure_bot_obj(data.get("user_bot")).username,
        int(time.time()),
        temp[1] if temp[1] == "txt" else "csv",
    )

    try:
        # Create directory if not exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        if temp[1] in ["xlsx", "csv"]:
            # Для xlsx сначала пишем csv, потом конвертируем
            with open(filepath, "w", encoding="utf-8", newline="") as export_file:
                writer = csv.writer(export_file)
                writer.writerow(["id"])

                for user in users:
                    writer.writerow([str(user.id)])

            if temp[1] == "xlsx":
                csv_file = pd.read_csv(filepath)
                # Меняем расширение на xlsx
                filepath_xlsx = filepath.replace(".csv", ".xlsx")
                csv_file.to_excel(filepath_xlsx, index=False, header=True)
                os.remove(filepath)  # Remove csv
                filepath = filepath_xlsx
        else:
            with open(filepath, "w", encoding="utf-8") as export_file:
                for user in users:
                    export_file.write(str(user.id) + "\n")

    except Exception as e:
        logger.error(f"Error exporting users: {e}")
        await call.message.answer(text("error_export"))
        return

    try:
        await call.message.answer_document(document=types.FSInputFile(filepath))
    except Exception as e:
        logger.error(f"Error sending export file: {e}")
        await call.message.answer(text("error_export"))
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


def get_router() -> Router:
    """
    Регистрация роутеров настроек ботов.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoiceBots")
    router.callback_query.register(cancel, F.data.split("|")[0] == "BackAddBot")
    router.message.register(get_token, AddBot.input_token, F.text)
    router.callback_query.register(manage_bot, F.data.split("|")[0] == "ManageBot")

    router.callback_query.register(
        back_update, F.data.split("|")[0] == "BackRefreshToken"
    )
    router.message.register(update_token, AddBot.update_token, F.text)

    router.callback_query.register(
        delete_bot, F.data.split("|")[0] == "AcceptDeleteBot"
    )

    router.message.register(get_import_file, AddBot.import_file, F.document)
    router.callback_query.register(
        back_update, F.data.split("|")[0] == "BackImportFile"
    )
    router.callback_query.register(choice_export, F.data.split("|")[0] == "ExportType")

    return router
