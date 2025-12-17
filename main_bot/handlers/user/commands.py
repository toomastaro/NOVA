"""
Обработчик команд бота.

Предоставляет быстрый доступ к функциям через slash-команд:
- /create_posting, /create_stories, /create_bots - создание контента
- /posting, /stories, /bots - переход в разделы
- /profile, /support, /subscription, /settings - настройки и поддержка
"""
import logging
from typing import Dict, Any

from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from main_bot.handlers.user.bots.menu import show_create_post as bots_create
from main_bot.handlers.user.menu import (
    profile,
    start_bots,
    start_posting,
    start_stories,
    support,
)
from main_bot.handlers.user.posting.menu import show_create_post as post_create
from main_bot.handlers.user.profile.profile import show_setting, show_subscribe
from main_bot.handlers.user.stories.menu import show_create_post as story_create
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Commands Handler")
async def commands(message: types.Message, command: CommandObject, state: FSMContext) -> None:
    """
    Обработчик slash-команд.
    Маршрутизирует команду на соответствующий обработчик.

    Аргументы:
        message (types.Message): Сообщение с командой.
        command (CommandObject): Объект команды.
        state (FSMContext): Контекст состояния FSM.
    """
    variants: Dict[str, Dict[str, Any]] = {
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

    if command.command not in variants:
        logger.warning(f"Неизвестная команда: {command.command}")
        return

    handler_data = variants[command.command]
    await handler_data["cor"](*handler_data["args"])


def get_router() -> Router:
    """
    Создает роутер для обработки slash-команд.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами команд.
    """
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
