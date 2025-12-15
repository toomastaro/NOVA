"""
Пакет обработчиков профиля пользователя.

Содержит модули для:
- Управления балансом и платежами
- Настройки подписок и папок
- Реферальной системы
- Настроек аккаунта (часовой пояс, отчеты)
"""
from aiogram import Router
from . import (
    profile,
    balance,
    payment,
    subscribe,
    subscribe_payment,
    referral,
    settings,
    timezone,
    folders,
    transfer_subscription,
    info,
    report_settings,
)


def get_router():
    """Собирает и возвращает главный роутер профиля."""
    routers = [
        payment.get_router(),
        subscribe_payment.get_router(),
        profile.get_router(),
        balance.get_router(),
        subscribe.get_router(),
        transfer_subscription.get_router(),
        info.get_router(),
        referral.get_router(),
        settings.get_router(),
        timezone.get_router(),
        folders.get_router(),
        report_settings.get_router(),
    ]

    router = Router(name='Profile')
    router.include_routers(*routers)

    return router
