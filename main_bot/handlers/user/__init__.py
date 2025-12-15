from aiogram import Router

from . import (
    menu,
    start,
    set_resource,
    support,
    commands,
    exchange_rate,
    novastat,
    ad_creative,
    ad_buy_menu,
    subscription_menu,
    join_request,
)
from .profile import get_router as profile_router
from .posting import get_router as posting_router
from .stories import get_router as stories_router
from .bots import get_router as bots_router


def get_router():
    routers = [
        start.get_router(),
        menu.get_router(),
        support.get_router(),
        set_resource.get_router(),
        commands.get_router(),
        exchange_rate.get_router(),
        novastat.router,
        profile_router(),
        posting_router(),
        stories_router(),
        bots_router(),
        ad_creative.get_router(),
        ad_buy_menu.router,
        subscription_menu.router,
        join_request.get_router(),
    ]

    router = Router(name="User")
    router.include_routers(*routers)

    return router
