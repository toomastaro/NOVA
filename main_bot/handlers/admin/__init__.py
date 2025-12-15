from aiogram import Router

from . import start, promo, session, channels


def get_router():
    """Сборка и подключение всех роутеров админ-панели."""
    routers = [
        start.get_router(),
        promo.get_router(),
        session.get_router(),
        channels.get_router(),
    ]

    router = Router(name='Admin')
    router.include_routers(*routers)

    return router
