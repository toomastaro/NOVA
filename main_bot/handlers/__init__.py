import os

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv


from main_bot.database.db import db
from main_bot.utils.middlewares import GetUserMiddleware, ErrorMiddleware
from main_bot.utils.schedulers import send_posts, unpin_posts, delete_posts, send_stories, send_bot_posts, \
    check_subscriptions, start_delete_bot_posts, update_exchange_rates_in_db, mt_clients_self_check
from .user import get_router as user_router
from .admin import get_router as admin_router

load_dotenv()


RUB_USDT_TIMER = os.getenv('RUBUSDTTIMER')


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
    sch = AsyncIOScheduler(
        timezone='Europe/Moscow'
    )
    sch.add_job(
        func=db.clear_empty_bot_posts,
        trigger=CronTrigger(
            hour='0'
        )
    )
    sch.add_job(
        func=db.clear_empty_posts,
        trigger=CronTrigger(
            hour='0'
        )
    )
    sch.add_job(
        func=db.clear_empty_stories,
        trigger=CronTrigger(
            hour='0'
        )
    )
    sch.add_job(
        func=send_posts,
        trigger=CronTrigger(
            second='*/10'
        )
    )
    sch.add_job(
        func=unpin_posts,
        trigger=CronTrigger(
            second='*/10'
        )
    )
    sch.add_job(
        func=delete_posts,
        trigger=CronTrigger(
            second='*/10'
        )
    )
    sch.add_job(
        func=start_delete_bot_posts,
        trigger=CronTrigger(
            second='*/10'
        )
    )
    sch.add_job(
        func=send_stories,
        trigger=CronTrigger(
            second='*/10'
        )
    )
    sch.add_job(
        func=send_bot_posts,
        trigger=CronTrigger(
            second='*/10'
        )
    )
    sch.add_job(
        func=check_subscriptions,
        trigger=CronTrigger(
            second="*/10"
        )
    )
    sch.add_job(
        func=update_exchange_rates_in_db,
        trigger=IntervalTrigger(
            seconds=int(RUB_USDT_TIMER)
        )
    )

    sch.add_job(
        func=mt_clients_self_check,
        trigger=CronTrigger(
            hour='3',
            minute='0',
            timezone='Europe/Moscow'
        )
    )

    sch.start()
    sch.print_jobs()
