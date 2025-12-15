from aiogram import Router
from . import menu, channels, create_post, content


def get_router():
    routers = [
        menu.get_router(),
        channels.get_router(),
        create_post.get_router(),
        content.get_router(),
    ]

    router = Router(name='Stories')
    router.include_routers(*routers)

    return router
