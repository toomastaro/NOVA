from aiogram import Router

from . import channels, content, create_post, menu


def get_router():
    routers = [
        menu.hand_add(),
        channels.hand_add(),
        create_post.hand_add(),
        content.hand_add(),
    ]

    router = Router(name="Stories")
    router.include_routers(*routers)

    return router
