from aiogram import Router

from utils.middleware import SetCrudMain
from . import menu, settings, create_post, content
from .bot_settings import application, hello, bye, menu as hmenu, captcha, cloner, cleaner


def get_router():
    routers = [
        menu.get_router(),
        settings.get_router(),
        create_post.get_router(),
        content.get_router(),

        application.get_router(),
        hello.get_router(),
        captcha.get_router(),
        cloner.get_router(),
        cleaner.get_router(),
        bye.get_router(),
        hmenu.get_router(),
    ]

    router = Router(name='Bots')
    router.include_routers(*routers)
    router.message.middleware(SetCrudMain())
    router.callback_query.middleware(SetCrudMain())

    return router
