from aiogram import Router
from . import menu, channels, create_post, content


def get_router():
    routers = [
        menu.hand_add(),
        channels.hand_add(),
        create_post.hand_add(),
        content.get_router(),
    ]

    router = Router(name='Stories')
    router.include_routers(*routers)

    return router
