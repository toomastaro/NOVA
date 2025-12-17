"""
Инициализация handlers для main_bot.

Модуль отвечает за:
- Настройку диспетчера Aiogram с Redis-хранилищем
- Регистрацию middleware (StateReset, VersionCheck, GetUser, Error)
- Регистрацию роутеров (user, admin)
- Инициализацию планировщика задач с персистентностью в PostgreSQL
"""
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from config import Config
from main_bot.database.db import db
from main_bot.utils.middlewares import (
    ErrorMiddleware,
    GetUserMiddleware,
    VersionCheckMiddleware,
)
from main_bot.utils.redis_client import redis_client
from main_bot.utils.schedulers import init_scheduler, register_channel_jobs
from main_bot.utils.state_reset_middleware import StateResetMiddleware
from .admin import get_router as admin_router
from .user import get_router as user_router

load_dotenv()

logger = logging.getLogger(__name__)

# Use shared Redis client
redis = redis_client

dp = Dispatcher(storage=RedisStorage(redis=redis))


def set_main_routers() -> None:
    """
    Регистрация глобальных middleware и роутеров (user, admin).
    Порядок регистрации middleware важен для корректной работы.
    """
    # Регистрируем StateResetMiddleware первым для сброса состояния при нажатии меню
    dp.update.middleware.register(StateResetMiddleware())
    # Регистрируем VersionCheckMiddleware для проверки версии
    dp.update.middleware.register(VersionCheckMiddleware())
    dp.update.middleware.register(GetUserMiddleware())
    dp.update.middleware.register(ErrorMiddleware())
    dp.include_routers(
        user_router(),
        admin_router(),
    )


async def set_scheduler() -> None:
    """
    Инициализация планировщика задач.

    Использует init_scheduler для регистрации всех системных задач
    с параметром replace_existing=True для предотвращения дублей при перезапуске.

    Использует SQLAlchemyJobStore для персистентности задач в PostgreSQL,
    что позволяет восстанавливать все задачи после рестарта Docker контейнера.
    """
    # Формирование URL подключения к PostgreSQL
    postgres_url = f"postgresql://{Config.PG_USER}:{Config.PG_PASS}@{Config.PG_HOST}/{Config.PG_DATABASE}"

    # Настройка jobstore для персистентности задач в БД
    jobstores = {"default": SQLAlchemyJobStore(url=postgres_url)}

    # Создание планировщика с jobstore
    sch = AsyncIOScheduler(jobstores=jobstores, timezone="Europe/Moscow")

    # Регистрация задач очистки БД (выполняются в полночь)
    sch.add_job(
        func=db.bot_post.clear_empty_bot_posts,
        trigger=CronTrigger(hour="0"),
        id="clear_empty_bot_posts_daily",
        replace_existing=True,
        name="Очистка пустых постов ботов",
    )
    sch.add_job(
        func=db.post.clear_empty_posts,
        trigger=CronTrigger(hour="0"),
        id="clear_empty_posts_daily",
        replace_existing=True,
        name="Очистка пустых постов",
    )
    sch.add_job(
        func=db.story.clear_empty_stories,
        trigger=CronTrigger(hour="0"),
        id="clear_empty_stories_daily",
        replace_existing=True,
        name="Очистка пустых сторис",
    )

    # Регистрация всех системных задач через init_scheduler
    init_scheduler(sch)

    # Регистрация задач для каналов
    await register_channel_jobs(sch)

    sch.start()
    logger.info("Планировщик задач запущен")
    logger.debug("Зарегистрированные задачи планировщика: %s", [job.id for job in sch.get_jobs()])
