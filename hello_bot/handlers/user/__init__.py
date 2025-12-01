from aiogram import Router

from . import start  # menu, answers, hello, bye, application, stats


def get_router():
    routers = [
        start.hand_add(),
        # menu.hand_add(),
        # answers.hand_add(),
        # hello.hand_add(),
        # bye.hand_add(),
        # application.hand_add(),
        # stats.hand_add(),
    ]

    router = Router(name='User')
    router.include_routers(*routers)

    return router
