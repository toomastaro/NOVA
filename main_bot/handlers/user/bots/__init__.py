from aiogram import Router

from utils.middleware import SetCrudMain

from . import content, create_post, menu, settings
from .bot_settings import application, bye, captcha, cleaner, cloner, hello
from .bot_settings import menu as hmenu


def get_router():
    routers = [
        menu.hand_add(),
        settings.hand_add(),
        create_post.hand_add(),
        content.hand_add(),
        application.hand_add(),
        hello.hand_add(),
        captcha.hand_add(),
        cloner.hand_add(),
        cleaner.hand_add(),
        bye.hand_add(),
        hmenu.hand_add(),
    ]

    router = Router(name="Bots")
    router.include_routers(*routers)
    router.message.middleware(SetCrudMain())
    router.callback_query.middleware(SetCrudMain())

    return router
