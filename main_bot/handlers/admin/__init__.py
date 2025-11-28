from aiogram import Router

from . import promo, session, start, backup_callbacks


def get_router():
    routers = [
        start.hand_add(),
        promo.hand_add(),
        session.hand_add(),
        backup_callbacks.hand_add(),
    ]

    router = Router(name="Admin")
    router.include_routers(*routers)

    return router
