"""
Обработчик команд бота.

Предоставляет быстрый доступ к функциям через slash-команды:
- /create_posting, /create_stories, /create_bots - создание контента
- /posting, /stories, /bots - переход в разделы
- /profile, /support, /subscription, /settings - настройки и поддержка
"""
from aiogram import types, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from main_bot.handlers.user.menu import (
    start_posting,
    start_stories,
    start_bots,
    profile,
    support,
)
from main_bot.handlers.user.posting.menu import show_create_post as post_create
from main_bot.handlers.user.stories.menu import show_create_post as story_create
from main_bot.handlers.user.bots.menu import show_create_post as bots_create
from main_bot.handlers.user.profile.profile import show_subscribe, show_setting
import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Commands Handler")
async def commands(message: types.Message, command: CommandObject, state: FSMContext):
    """
    Обработчик slash-команд.
    
    Маршрутизирует команду на соответствующий обработчик.
    """
    variants = {
        # Post
        "create_posting": {
            "cor": post_create,
            "args": (
                message,
                state,
            ),
        },
        "create_stories": {
            "cor": story_create,
            "args": (
                message,
                state,
            ),
        },
        "create_bots": {
            "cor": bots_create,
            "args": (
                message,
                state,
            ),
        },
        # Menu
        "posting": {"cor": start_posting, "args": (message,)},
        "stories": {"cor": start_stories, "args": (message,)},
        "bots": {"cor": start_bots, "args": (message,)},
        "profile": {"cor": profile, "args": (message,)},
        "support": {
            "cor": support,
            "args": (
                message,
                state,
            ),
        },
        # Profile
        "subscription": {"cor": show_subscribe, "args": (message,)},
        "settings": {"cor": show_setting, "args": (message,)},
    }

    handler_data = variants[command.command]
    await handler_data["cor"](*handler_data["args"])


def get_router():
    """Создает роутер для обработки slash-команд."""
    router = Router()
    router.message.register(
        commands,
        Command(
            commands=[
                "create_posting",
                "create_stories",
                "create_bots",
                "posting",
                "stories",
                "bots",
                "profile",
                "support",
                "subscription",
                "settings",
            ]
        ),
    )
    return router
