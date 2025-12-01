import os
import time
from contextlib import asynccontextmanager

import uvicorn
from aiogram import types, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request

from config import Config
from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.user_bot.model import UserBot
from main_bot.handlers import set_main_routers, set_scheduler, dp
from hello_bot.handlers import set_routers
from main_bot.utils.logger import setup_logging

setup_logging()


dispatchers = {}


def set_dispatcher(db_bot: UserBot):
    if db_bot.token in dispatchers:
        return dispatchers[db_bot.token]

    other_dp = set_routers()
    dispatchers[db_bot.token] = other_dp

    return other_dp


@asynccontextmanager
async def lifespan(_app: FastAPI):
    os.environ['TZ'] = 'Europe/Moscow'
    time.tzset()

    set_main_routers()
    set_scheduler()

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"BACKUP_CHAT_ID: {Config.BACKUP_CHAT_ID}")
    if not Config.BACKUP_CHAT_ID:
        logger.warning("BACKUP_CHAT_ID is not set or is 0!")

    await db.create_tables()

    # Bot Setting
    await bot.delete_webhook(
        drop_pending_updates=True
    )
    await bot.set_webhook(
        url=Config.WEBHOOK_DOMAIN + '/webhook/main',
        allowed_updates=[
            'message',
            'callback_query',
            'pre_checkout_query',
            'chat_member',
            'my_chat_member',
        ]
    )

    yield

    await bot.delete_webhook(
        drop_pending_updates=True
    )


app = FastAPI(
    lifespan=lifespan
)


@app.get('/health')
async def health_check():
    return {"status": "ok", "message": "Service is running"}


@app.post('/webhook/main')
async def main_update(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data)

    await dp.feed_update(
        bot=bot,
        update=update
    )


@app.post("/webhook/{token}")
async def other_update(request: Request, token: str):
    data = await request.json()
    update = types.Update.model_validate(data)

    exist = await db.get_bot_by_token(token)
    if not exist:
        return

    try:
        other_bot = Bot(
            token=token,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML
            )
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error creating bot for token {token}: {e}", exc_info=True)
        return

    other_dp = set_dispatcher(exist)
    await other_dp.feed_update(other_bot, update)


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8099)
