import csv
import os
import time

import pandas as pandas
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
import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Bots Show Bot Manage")
async def show_bot_manage(message: types.Message, user_bot: UserBot):
    bot_database = Database()
    bot_database.schema = user_bot.schema

    count_users = await bot_database.get_count_users()

    channel_ids_in_bot = await db.get_all_channels_in_bot_id(
        bot_id=user_bot.id
    )
    channels = [
        await db.get_channel_by_chat_id(chat.id)
        for chat in channel_ids_in_bot
    ]

    async with BotManager(user_bot.token) as bot_manager:
        status = await bot_manager.status()

    await message.answer(
        text("bot:info").format(
            user_bot.title,
            count_users.get("active"),
            count_users.get("total"),
            "\n".join(
                text("resource_title").format(
                    channel.title
                ) for channel in channels
            ) if channels else "❌",
            "✅" if status else "❌",
        ),
        reply_markup=keyboards.manage_bot(
            user_bot=user_bot,
            status=status
        )
    )


@safe_handler("Bots Settings Choice")
async def choice(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] in ['next', 'back']:
        bots = await db.get_user_bots(
            user_id=call.from_user.id,
            sort_by=True
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_bots(
                bots=bots,
                remover=int(temp[2])
            )
        )

    if temp[1] == 'cancel':
        await call.message.delete()
        return await start_bots(call.message)

    if temp[1] == 'add':
        await call.message.edit_text(
            text=text("bots:add:text"),
            reply_markup=keyboards.back(
                data="BackAddBot"
            )
        )
        await state.set_state(AddBot.input_token)
        return

    bot_id = int(temp[1])
    user_bot = await db.get_bot_by_id(bot_id)

    await state.update_data(
        user_bot=user_bot,
        bot_id=user_bot.id
    )

    await call.message.delete()
    await show_bot_manage(call.message, user_bot)


@safe_handler("Bots Settings Cancel")
async def cancel(call: types.CallbackQuery, state: FSMContext):
    bots = await db.get_user_bots(
        user_id=call.from_user.id,
        sort_by=True
    )

    await state.clear()
    await call.message.edit_text(
        text('bots_text'),
        reply_markup=keyboards.choice_bots(
            bots=bots,
        )
    )


@safe_handler("Bots Get Token")
async def get_token(message: types.Message, state: FSMContext):
    token = message.text
    if message.forward_from:
        try:
            token = message.text.split('API:')[1].split('Keep')[0].strip()
        except IndexError:
            token = ''

    bot_manager = BotManager(token)
    is_valid = await bot_manager.validate_token()
    if not is_valid:
        return await message.answer(
            text("error_valid_token"),
            reply_markup=keyboards.cancel(
                data="BackAddBot"
            )
        )

    bot_id = is_valid.id
    exist = await db.get_bot_by_id(bot_id)
    if exist:
        return await message.answer(
            text("error_exist_token"),
            reply_markup=keyboards.cancel(
                data="BackAddBot"
            )
        )

    username = is_valid.username
    title = is_valid.full_name

    success_start = await bot_manager.set_webhook()
    if not success_start:
        return await message.answer(
            text("error_valid_token"),
            reply_markup=keyboards.cancel(
                data="BackAddBot"
            )
        )

    photo_bytes = None
    get_photo = await bot_manager.bot.get_user_profile_photos(bot_id)
    if get_photo.total_count > 0:
        photo_bytes = await bot_manager.bot.download(
            get_photo.photos[0][-1].file_id
        )
    await bot_manager.close()

    emoji_id = await create_emoji(
        user_id=message.from_user.id,
        photo_bytes=photo_bytes
    )
    schema = "hello_{}_{}".format(
        message.from_user.id,
        username
    )
    await db.add_bot(
        id=bot_id,
        admin_id=message.from_user.id,
        schema=schema,
        token=token,
        username=username,
        title=title,
        emoji_id=emoji_id
    )

    bot_database = Database()
    bot_database.schema = schema
    await bot_database.create_tables()

    await state.clear()
    await message.answer(
        text("success_add_bot"),
        reply_markup=keyboards.back(
            data="BackAddBot"
        )
    )


@safe_handler("Bots Manage Bot")
async def manage_bot(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] in ["cancel", "delete"]:
        if temp[1] == "delete":
            await call.message.edit_text(
                text("delete:bot"),
                reply_markup=keyboards.accept(
                    data="AcceptDeleteBot"
                )
            )
            return

        await call.message.delete()
        return await show_settings(call.message)

    if temp[1] in ["check_token", "channel"]:
        if temp[1] == "channel":
            message_text = text("delete_channel:bot")
        else:
            async with BotManager(data.get('user_bot').token) as bot_manager:
                is_valid = await bot_manager.validate_token()

            message_text = text("token_{}valid".format("" if is_valid else "not_"))

        return await call.answer(message_text, show_alert=True)

    if temp[1] == "refresh_token":
        await call.message.edit_text(
            text("input_token"),
            reply_markup=keyboards.back(
                data="BackRefreshToken"
            )
        )
        return await state.set_state(AddBot.update_token)

    if temp[1] == "status":
        async with BotManager(data.get("user_bot").token) as bot_manager:
            status = await bot_manager.status()
            await bot_manager.set_webhook(delete=status)

        await call.message.delete()
        return await show_bot_manage(call.message, data.get("user_bot"))

    if temp[1] == "import_db":
        await call.message.edit_text(
            text("input_import_file"),
            reply_markup=keyboards.back(
                data="BackImportFile"
            )
        )
        await state.set_state(AddBot.import_file)

    if temp[1] == "export_db":
        await call.message.edit_text(
            text("choice_export_type"),
            reply_markup=keyboards.export_type()
        )

    if temp[1] == "settings":
        channel_ids_in_bot = await db.get_all_channels_in_bot_id(
            bot_id=data.get("bot_id")
        )
        if not channel_ids_in_bot:
            return await call.answer(text("not_have_channels"), show_alert=True)

        channels = [
            await db.get_channel_by_chat_id(chat.id)
            for chat in channel_ids_in_bot
        ]
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_for_setting(
                channels=channels
            )
        )


@safe_handler("Bots Update Token")
async def update_token(message: types.Message, state: FSMContext):
    token = message.text
    data = await state.get_data()
    user_bot: UserBot = data.get("user_bot")

    async with BotManager(token) as bot_manager:
        me = await bot_manager.validate_token()
        if not me:
            return await message.answer(
                text("error_valid_token"),
                reply_markup=keyboards.cancel(
                    data="BackRefreshToken"
                )
            )
        if user_bot.username != me.username:
            return await message.answer(
                text("error_valid_token"),
                reply_markup=keyboards.cancel(
                    data="BackRefreshToken"
                )
            )
        if user_bot.admin_id != message.from_user.id:
            return await message.answer(
                text("error_valid_token"),
                reply_markup=keyboards.cancel(
                    data="BackRefreshToken"
                )
            )

        user_bot = await db.update_bot_by_id(
            row_id=user_bot.id,
            return_obj=True,
            token=token
        )
        await bot_manager.set_webhook()

    await state.update_data(
        user_bot=user_bot
    )
    await show_bot_manage(message, user_bot)


@safe_handler("Bots Back Update")
async def back_update(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    user_bot = data.get('user_bot')

    await call.message.delete()
    await state.clear()
    await state.update_data(data)

    await show_bot_manage(call.message, user_bot)


@safe_handler("Bots Delete Bot")
async def delete_bot(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    await call.message.delete()

    if len(temp) == 2 and temp[1] == "yes":
        await db.delete_bot_by_id(
            row_id=data.get("user_bot").id
        )
        other_db = Database()
        other_db.schema = data.get("user_bot").schema
        await other_db.drop_schema()

        async with BotManager(data.get("user_bot").token) as bot_manager:
            await bot_manager.set_webhook(delete=True)

        await state.clear()
        return await start_bots(call.message)

    await show_bot_manage(call.message, data.get("user_bot"))


@safe_handler("Bots Get Import File")
async def get_import_file(message: types.Message, state: FSMContext):
    file = await message.bot.get_file(message.document.file_id)
    file_name = file.file_path.split('/')[-1]
    extension = file_name.split('.')[1].lower()

    if extension not in ["txt", "xlsx", "csv"]:
        return await message.answer(
            text("error_input_file"),
            reply_markup=keyboards.back(
                data="BackImportFile"
            )
        )

    filepath = "main_bot/utils/temp/import_" + file_name
    await message.bot.download(
        message.document.file_id,
        filepath
    )

    try:
        if extension == 'txt':
            with open(filepath, 'r') as file:
                users = [{"id": int(i.strip())} for i in file.readlines() if i.strip().isdigit()]
        elif extension == 'csv':
            with open(filepath, 'r', encoding='utf-8-sig') as file:
                read = csv.reader(file)
            users = [{"id": int(i[0])} for i in read if i[0].isdigit()]
        else:
            file = pandas.read_excel(filepath, header=None)
            users = [{"id": i} for i in file[0] if isinstance(i, int)]

        data = await state.get_data()
        other_db = Database()
        other_db.schema = data.get("user_bot").schema

        await other_db.many_insert_user(users)

    except Exception as e:
        logger.error(f"Error importing file: {e}")
        return await message.answer(
            text("error_import")
        )
    finally:
        os.remove(filepath)

    await state.clear()
    await state.update_data(data)

    await message.answer(text("success_import"))
    await show_bot_manage(message, data.get("user_bot"))


@safe_handler("Bots Choice Export")
async def choice_export(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_bot_manage(call.message, data.get("user_bot"))

    other_db = Database()
    other_db.schema = data.get("user_bot").schema

    users = await other_db.get_dump_users()
    if not users:
        return await call.answer(
            text("error_empty_users")
        )

    await call.message.delete()
    await call.message.answer(text("start_export"))
    await show_bot_manage(call.message, data.get("user_bot"))

    filepath = "main_bot/utils/temp/export_users_{}_{}.{}".format(
        data.get("user_bot").username,
        int(time.time()),
        temp[1] if temp[1] == "txt" else "csv"
    )

    try:
        export_file = open(filepath, "w", encoding="utf-8")
        if temp[1] in ["xlsx", "csv"]:
            writer = csv.writer(export_file)
            writer.writerow(["id"])

            for user in users:
                writer.writerow([str(user.id)])

            if temp[1] == "xlsx":
                export_file.close()
                csv_file = pandas.read_csv(filepath)
                filepath = filepath.replace("csv", "xlsx")
                csv_file.to_excel(filepath, index=False, header=True)
        else:
            for user in users:
                export_file.write(str(user.id) + "\n")

        if temp[1] != "xlsx":
            export_file.close()

    except Exception as e:
        logger.error(f"Error exporting users: {e}")
        return await call.message.answer(
            text("error_export")
        )

    try:
        await call.message.answer_document(
            document=types.FSInputFile(filepath)
        )
    except Exception as e:
        logger.error(f"Error sending export file: {e}")
        await call.message.answer(text("error_export"))
    finally:
        os.remove(filepath)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoiceBots")
    router.callback_query.register(cancel, F.data.split("|")[0] == "BackAddBot")
    router.message.register(get_token, AddBot.input_token, F.text)
    router.callback_query.register(manage_bot, F.data.split("|")[0] == "ManageBot")

    router.callback_query.register(back_update, F.data.split("|")[0] == "BackRefreshToken")
    router.message.register(update_token, AddBot.update_token, F.text)

    router.callback_query.register(delete_bot, F.data.split("|")[0] == "AcceptDeleteBot")

    router.message.register(get_import_file, AddBot.import_file, F.document)
    router.callback_query.register(back_update, F.data.split("|")[0] == "BackImportFile")
    router.callback_query.register(choice_export, F.data.split("|")[0] == "ExportType")

    return router
