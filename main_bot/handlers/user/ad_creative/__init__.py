"""
Инициализация модуля рекламных креативов и покупок.

Объединяет роутеры для управления креативами, меню и процессом покупки.
"""

from aiogram import Router

from . import handlers, menu, purchase, purchase_menu


def get_router() -> Router:
    """
    Создает роутер модуля рекламных креативов.

    Возвращает:
        Router: Роутер с подключенными суб-роутерами.
    """
    router = Router(name="AdCreative")
    router.include_router(handlers.router)
    router.include_router(menu.router)
    router.include_router(purchase.router)
    router.include_router(purchase_menu.router)
    return router
