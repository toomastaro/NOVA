from aiogram import Router
from . import handlers, menu

def get_router():
    router = Router(name="AdCreative")
    router.include_router(handlers.router)
    router.include_router(menu.router)
    return router
