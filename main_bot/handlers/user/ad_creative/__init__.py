from aiogram import Router
from . import handlers, menu, purchase, purchase_menu

def get_router():
    router = Router(name="AdCreative")
    router.include_router(handlers.router)
    router.include_router(menu.router)
    router.include_router(purchase.router)
    router.include_router(purchase_menu.router)
    return router
