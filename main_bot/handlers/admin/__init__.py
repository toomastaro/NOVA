from aiogram import Router

from . import promo, session, start


def get_router():
    routers = [
        start.hand_add(),
        promo.hand_add(),
        session.hand_add(),
    ]

    router = Router(name="Admin")
    router.include_routers(*routers)

    return router
