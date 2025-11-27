import os
import time
from contextlib import asynccontextmanager

import uvicorn
from aiogram import Bot, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from hello_bot.handlers import set_routers
from instance_bot import bot
from main_bot.database import engine
from main_bot.database.db import db
from main_bot.database.user_bot.model import UserBot
from main_bot.handlers import dp, set_main_routers, set_scheduler
from utils.logger import logger, setup_logger

from aiogram import Dispatcher

dispatchers: dict[str, Dispatcher] = {}


def set_dispatcher(db_bot: UserBot) -> Dispatcher:
    """
    Get or create a dispatcher for a user bot.
    """
    if db_bot.token in dispatchers:
        return dispatchers[db_bot.token]

    other_dp = set_routers()
    dispatchers[db_bot.token] = other_dp

    return other_dp


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    setup_logger()
    logger.info(f"Starting application version {settings.VERSION}")

    os.environ["TZ"] = "Europe/Moscow"
    if hasattr(time, "tzset"):
        time.tzset()

    scheduler = set_scheduler()
    set_main_routers()

    await db.create_tables()

    # Bot Setting
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(
        url=settings.WEBHOOK_DOMAIN + "/webhook/main",
        allowed_updates=[
            "message",
            "callback_query",
            "pre_checkout_query",
            "chat_member",
            "my_chat_member",
        ],
    )

    yield

    scheduler.shutdown()
    await bot.delete_webhook(drop_pending_updates=True)
    await engine.dispose()
    logger.info("Application shutdown")


app = FastAPI(lifespan=lifespan, title="NOVA Bot API", version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "Service is running",
        "version": settings.VERSION,
    }


@app.post("/webhook/main")
async def main_update(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data)

    await dp.feed_update(bot=bot, update=update)


@app.post("/webhook/{token}")
async def other_update(request: Request, token: str):
    data = await request.json()
    update = types.Update.model_validate(data)

    exist = await db.get_bot_by_token(token)
    if not exist:
        return

    try:
        other_bot = Bot(
            token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    except Exception as e:
        logger.exception(f"Error creating bot instance for token {token}: {e}")
        return

    other_dp = set_dispatcher(exist)
    await other_dp.feed_update(other_bot, update)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099)
