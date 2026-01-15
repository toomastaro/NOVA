"""
Инициализация роутеров для админ-панели.
"""

from aiogram import Router

from . import admin_bots, admin_users, analytics, channels, finance, mailing, promo, session, start


def get_router() -> Router:
    """
    Сборка и подключение всех роутеров админ-панели.

    Возвращает:
        Router: Главный роутер админ-панели с подключенными под-роутерами.
    """
    routers = [
        start.get_router(),
        promo.get_router(),
        session.get_router(),
        channels.get_router(),
        mailing.get_router(),
        admin_bots.get_router(),
        admin_users.get_router(),
        finance.get_router(),
        analytics.get_router(),
    ]

    router = Router(name="Admin")
    router.include_routers(*routers)

    return router
