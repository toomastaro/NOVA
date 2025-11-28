from aiogram import Router

from . import calendar_manager, channels, content, create_post, menu


def get_router():
    routers = [
        menu.hand_add(),
        channels.hand_add(),
        create_post.hand_add(),
        content.hand_add(),
        calendar_manager.register_calendar_manager(),
    ]

    router = Router(name="Posting")
    router.include_routers(*routers)

    return router
