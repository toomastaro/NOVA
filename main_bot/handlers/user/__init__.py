from aiogram import Router

from . import commands, menu, set_resource, start, support
from .bots import get_router as bots_router
from .posting import get_router as posting_router
from .profile import get_router as profile_router
from .stories import get_router as stories_router


def get_router():
    routers = [
        start.hand_add(),
        menu.hand_add(),
        support.hand_add(),
        set_resource.hand_add(),
        commands.hand_add(),
        profile_router(),
        posting_router(),
        stories_router(),
        bots_router(),
    ]

    router = Router(name="User")
    router.include_routers(*routers)

    return router
