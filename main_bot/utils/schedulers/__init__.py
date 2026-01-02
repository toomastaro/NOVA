"""
Модуль планировщика задач для Telegram-бота.
Реэкспорт всех функций планировщика для удобного импорта.

Структура модулей:
- posts.py: отправка, удаление, открепление постов, CPM отчеты
- stories.py: отправка сторис
- bots.py: рассылки через ботов, удаление сообщений
- cleanup.py: проверка подписок, самопроверка MT клиентов
- extra.py: обновление курсов валют и прочие вспомогательные задачи
"""

import logging
import os
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import config

# Импорты из модулей
from .ad_stats import process_ad_stats
from .bots import (
    send_bot_posts,
    start_delete_bot_posts,
)
from .channels import (
    register_channel_jobs,
    schedule_channel_job,
    update_channel_stats,
)
from .cleanup import (
    check_subscriptions,
    mt_clients_self_check,
    update_external_channels_stats,
)
from .extra import (
    update_exchange_rates_in_db,
)
from .posts import (
    check_cpm_reports,
    delete_posts,
    send_posts,
    unpin_posts,
)
from .stories import (
    send_stories,
)

logger = logging.getLogger(__name__)

scheduler_instance: Optional[AsyncIOScheduler] = None


def init_scheduler(scheduler: AsyncIOScheduler) -> None:
    """
    Инициализация и регистрация всех системных периодических задач.

    Использует replace_existing=True для предотвращения дублей при перезапуске приложения.
    Регистрирует только системные задачи, пользовательские задачи (отложенные посты)
    управляются через бизнес-логику.

    Аргументы:
        scheduler (AsyncIOScheduler): Экземпляр планировщика для регистрации задач.
    """
    global scheduler_instance
    scheduler_instance = scheduler

    # === ПОСТЫ ===
    # Отправка отложенных постов (каждые 10 секунд)
    scheduler.add_job(
        func=send_posts,
        trigger=CronTrigger(second="*/10"),
        id="send_posts_periodic",
        replace_existing=True,
        name="Отправка отложенных постов",
    )

    # Открепление постов (каждые 10 секунд)
    scheduler.add_job(
        func=unpin_posts,
        trigger=CronTrigger(second="*/10"),
        id="unpin_posts_periodic",
        replace_existing=True,
        name="Открепление постов",
    )

    # Удаление постов (каждые 10 секунд)
    scheduler.add_job(
        func=delete_posts,
        trigger=CronTrigger(second="*/10"),
        id="delete_posts_periodic",
        replace_existing=True,
        name="Удаление постов по расписанию",
    )

    # Проверка CPM отчетов (каждые 10 секунд)
    scheduler.add_job(
        func=check_cpm_reports,
        trigger=CronTrigger(second="*/10"),
        id="check_cpm_reports_periodic",
        replace_existing=True,
        name="Проверка CPM отчетов 24/48/72ч",
    )

    # === СТОРИС ===
    # Отправка отложенных сторис (каждые 10 секунд)
    scheduler.add_job(
        func=send_stories,
        trigger=CronTrigger(second="*/10"),
        id="send_stories_periodic",
        replace_existing=True,
        name="Отправка отложенных сторис",
    )

    # === БОТЫ ===
    # Отправка постов через ботов (каждые 10 секунд)
    scheduler.add_job(
        func=send_bot_posts,
        trigger=CronTrigger(second="*/10"),
        id="send_bot_posts_periodic",
        replace_existing=True,
        name="Отправка постов через ботов",
    )

    # Удаление сообщений ботов (каждые 10 секунд)
    scheduler.add_job(
        func=start_delete_bot_posts,
        trigger=CronTrigger(second="*/10"),
        id="delete_bot_posts_periodic",
        replace_existing=True,
        name="Удаление сообщений ботов",
    )

    # === ОЧИСТКА И ОБСЛУЖИВАНИЕ ===
    # Проверка подписок (каждые 10 секунд)
    scheduler.add_job(
        func=check_subscriptions,
        trigger=CronTrigger(second="*/10"),
        id="check_subscriptions_periodic",
        replace_existing=True,
        name="Проверка подписок",
    )

    # Самопроверка MT клиентов (ОТКЛЮЧЕНО ПО ЗАПРОСУ)
    try:
        scheduler.remove_job("mt_clients_self_check_hourly")
        logger.info("🗑 Удалена устаревшая задача: mt_clients_self_check_hourly")
    except Exception:
        pass

    # Обслуживание внешних каналов (ОТКЛЮЧЕНО ПО ЗАПРОСУ - ПРИВОДИТ К FROZEN)
    try:
        scheduler.remove_job("update_external_channels_periodic")
        logger.info("🗑 Удалена устаревшая задача: update_external_channels_periodic")
    except Exception:
        pass

    # === ВСПОМОГАТЕЛЬНЫЕ ===
    # Обновление курсов валют
    rub_usdt_timer = int(os.getenv("RUBUSDTTIMER", "3600"))
    scheduler.add_job(
        func=update_exchange_rates_in_db,
        trigger=IntervalTrigger(seconds=rub_usdt_timer),
        id="update_exchange_rates_periodic",
        replace_existing=True,
        name="Обновление курсов валют",
    )

    # === AD STATS ===
    # Сбор статистики рекламы (Admin Log)
    # Используем `process_ad_stats` с IntervalTrigger

    ad_timer = int(config.zakup_timer or 600)

    scheduler.add_job(
        func=process_ad_stats,
        trigger=IntervalTrigger(seconds=ad_timer),
        id="process_ad_stats_periodic",
        replace_existing=True,
        name="Сбор статистики рекламы (Admin Log)",
    )

    logger.info("✅ Зарегистрированы все системные задачи планировщика")


# Экспорт всех функций
__all__ = [
    # Инициализация
    "init_scheduler",
    # Посты
    "send_posts",
    "unpin_posts",
    "delete_posts",
    "check_cpm_reports",
    # Сторис
    "send_stories",
    # Боты
    "send_bot_posts",
    "start_delete_bot_posts",
    # Очистка и обслуживание
    "check_subscriptions",
    "mt_clients_self_check",
    "update_external_channels_stats",
    # Вспомогательные
    "update_exchange_rates_in_db",
    # Channels
    "register_channel_jobs",
    "update_channel_stats",
    "schedule_channel_job",
]
