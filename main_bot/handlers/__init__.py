import os

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv


from main_bot.database.db import db
from main_bot.utils.middlewares import GetUserMiddleware, ErrorMiddleware
from main_bot.utils.schedulers import init_scheduler
from .user import get_router as user_router
from .admin import get_router as admin_router

load_dotenv()


dp = Dispatcher(
    storage=MemoryStorage()
)


def set_main_routers():
    dp.update.middleware.register(
        GetUserMiddleware()
    )
    dp.update.middleware.register(
        ErrorMiddleware()
    )
    dp.include_routers(
        user_router(),
        admin_router(),
    )


def set_scheduler():
    """
    Инициализация планировщика задач.
    
    Использует init_scheduler для регистрации всех системных задач
    с параметром replace_existing=True для предотвращения дублей при перезапуске.
    
    Использует SQLAlchemyJobStore для персистентности задач в PostgreSQL,
    что позволяет восстанавливать все задачи после рестарта Docker контейнера.
    """
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from config import Config
    
    # Формирование URL подключения к PostgreSQL
    postgres_url = f"postgresql://{Config.PG_USER}:{Config.PG_PASS}@{Config.PG_HOST}/{Config.PG_DATABASE}"
    
    # Настройка jobstore для персистентности задач в БД
    jobstores = {
        'default': SQLAlchemyJobStore(url=postgres_url)
    }
    
    # Создание планировщика с jobstore
    sch = AsyncIOScheduler(
        jobstores=jobstores,
        timezone='Europe/Moscow'
    )
    
    # Регистрация задач очистки БД (выполняются в полночь)
    sch.add_job(
        func=db.clear_empty_bot_posts,
        trigger=CronTrigger(hour='0'),
        id="clear_empty_bot_posts_daily",
        replace_existing=True,
        name="Очистка пустых постов ботов"
    )
    sch.add_job(
        func=db.clear_empty_posts,
        trigger=CronTrigger(hour='0'),
        id="clear_empty_posts_daily",
        replace_existing=True,
        name="Очистка пустых постов"
    )
    sch.add_job(
        func=db.clear_empty_stories,
        trigger=CronTrigger(hour='0'),
        id="clear_empty_stories_daily",
        replace_existing=True,
        name="Очистка пустых сторис"
    )
    
    # Регистрация всех системных задач через init_scheduler
    init_scheduler(sch)
    
    sch.start()
    sch.print_jobs()
