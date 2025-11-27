from aiogram import Router

from . import (
    balance,
    folders,
    payment,
    profile,
    referral,
    settings,
    subscribe,
    subscribe_payment,
    timezone,
)


def get_router():
    routers = [
        profile.hand_add(),
        balance.hand_add(),
        payment.hand_add(),
        subscribe.hand_add(),
        subscribe_payment.hand_add(),
        referral.hand_add(),
        settings.hand_add(),
        timezone.hand_add(),
        folders.hand_add(),
    ]

    router = Router(name="Profile")
    router.include_routers(*routers)

    return router
