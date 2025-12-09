from aiogram import Router
from . import profile, balance, payment, subscribe, subscribe_payment, referral, settings, timezone, folders, transfer_subscription, info


def get_router():
    routers = [
        payment.hand_add(),
        subscribe_payment.hand_add(),
        profile.hand_add(),
        balance.hand_add(),
        subscribe.hand_add(),
        transfer_subscription.hand_add(),
        info.hand_add(),
        referral.hand_add(),
        settings.hand_add(),
        timezone.hand_add(),
        folders.hand_add(),
    ]

    router = Router(name='Profile')
    router.include_routers(*routers)

    return router
