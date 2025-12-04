from aiogram import Router

from . import start, promo, session, channels


def get_router():
    routers = [
        start.hand_add(),
        promo.hand_add(),
        session.hand_add(),
        channels.hand_add(),
    ]

    router = Router(name='Admin')
    router.include_routers(*routers)

    return router
