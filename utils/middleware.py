from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Update

from hello_bot.utils.schemas import Answer
from main_bot.database.db import db
import logging
from hello_bot.utils.functions import answer_message

logger = logging.getLogger(__name__)


created_db_objects = {}


class SetCrud(BaseMiddleware):
    async def __call__(self, handler, event, data):
        db_bot = await db.get_bot_by_id(event.bot.id)

        from hello_bot.database.db import Database as HelloDatabase

        other_db = HelloDatabase()
        if not other_db.schema:
            other_db.schema = db_bot.schema

        await other_db.create_tables()

        data['db'] = other_db
        data['db_bot'] = db_bot
        data['owner_id'] = db_bot.admin_id

        return await handler(event, data)


class SetCrudMain(BaseMiddleware):
    async def __call__(self, handler, event, data):
        state: FSMContext = data.get("state")
        state_data = await state.get_data()
        print(state_data)

        bot_id: int = state_data.get("bot_id")
        if not bot_id:
            return await handler(event, data)

        if bot_id in created_db_objects:
            for key, value in created_db_objects[bot_id].items():
                data[key] = value

                if state_data.get("chat_id"):
                    channel_settings = await db.get_channel_bot_setting(
                        chat_id=state_data.get("chat_id")
                    )
                    data["channel_settings"] = channel_settings

            return await handler(event, data)

        if state_data.get("chat_id"):
            channel_settings = await db.get_channel_bot_setting(
                chat_id=state_data.get("chat_id")
            )
        else:
            channel_settings = None

        db_bot = await db.get_bot_by_id(bot_id)
        from hello_bot.database.db import Database as HelloDatabase

        other_db = HelloDatabase()
        if not other_db.schema:
            other_db.schema = db_bot.schema

        await other_db.create_tables()

        data['db_obj'] = other_db
        data['db_bot'] = db_bot
        data['owner_id'] = db_bot.admin_id
        data['channel_settings'] = channel_settings

        created_db_objects[bot_id] = {
            "db_obj": other_db,
            "db_bot": db_bot,
            "owner_id": db_bot.admin_id,
        }

        print(created_db_objects)
        return await handler(event, data)


class AnswerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        other_db = data['db']
        settings = await other_db.get_setting()

        data['settings'] = settings
        if not event.message:
            return await handler(event, data)

        if settings.answers:
            for answer in settings.answers:
                answer = Answer(**dict(answer))

                if answer.key == event.message.text:
                    await answer_message(event.message, answer.message, None)
                    await other_db.update_setting(
                        input_messages=settings.input_messages + 1,
                        output_messages=settings.output_messages + 1,
                    )
                    return await handler(event, data)

        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(
                f"Ошибка в обработчике {handler}",
                exc_info=True
            )
