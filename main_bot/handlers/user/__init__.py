from aiogram import Router

from . import menu, start, set_resource, support, commands, exchange_rate, novastat, ad_creative
from .profile import get_router as profile_router
from .posting import get_router as posting_router
from .stories import get_router as stories_router
from .bots import get_router as bots_router


def get_router():
    routers = [
        start.hand_add(),
        menu.hand_add(),
        support.hand_add(),
        set_resource.hand_add(),
        commands.hand_add(),
        exchange_rate.hand_add(),
        novastat.router,
        profile_router(),
        posting_router(),
        stories_router(),
        bots_router(),
        ad_creative.get_router(),
    ]

    router = Router(name='User')
    router.include_routers(*routers)

    return router
