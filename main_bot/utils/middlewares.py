"""
Middleware для обработки событий в aiogram.

Этот модуль содержит middleware для:
- Регистрации пользователей при команде /start
- Получения объекта пользователя из БД
- Глобальной обработки ошибок
- Проверки версии бота и сброса устаревших FSM состояний
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, types
from aiogram.filters import CommandObject
from aiogram.types import TelegramObject

from config import Config
from main_bot.database.db import db

logger = logging.getLogger(__name__)


class StartMiddle(BaseMiddleware):
    """
    Middleware для обработки команды /start и регистрации пользователя.

    Проверяет, зарегистрирован ли пользователь. Если нет:
    - Проверяет реферальный код или UTM-метку.
    - Регистрирует пользователя в БД.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Применяем только к Message
        if not isinstance(event, types.Message):
            return await handler(event, data)

        message: types.Message = event
        command: CommandObject = data.get("command")

        # Если это не команда или не команда start, просто передаем управление дальше
        if not command or command.command != "start":
            return await handler(message, data)

        user_obj = message.from_user
        # Проверяем наличие пользователя в БД
        user = await db.user.get_user(user_obj.id)

        if not user:
            referral_id = None
            ads_tag = None

            if command.args:
                start_utm = command.args
                # Проверка на реферальную ссылку (числовой ID)
                if start_utm.isdigit():
                    ref_user = await db.user.get_user(int(start_utm))
                    if ref_user:
                        referral_id = int(start_utm)
                # Проверка на UTM метку
                else:
                    if "utm" in start_utm:
                        ads_tag = start_utm.replace("utm-", "")
                        tag = await db.ad_tag.get_ad_tag(ads_tag)

                        if not tag:
                            ads_tag = None

            try:
                await db.user.add_user(
                    id=user_obj.id,
                    is_premium=user_obj.is_premium or False,
                    referral_id=referral_id,
                    ads_tag=ads_tag,
                )
            except Exception as e:
                logger.error(
                    f"Ошибка при регистрации пользователя {user_obj.id}: {e}",
                    exc_info=True,
                )

        return await handler(message, data)


class GetUserMiddleware(BaseMiddleware):
    """
    Middleware для получения объекта пользователя из БД и добавления его в контекст (data).

    Работает для Message и CallbackQuery.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(
            event, types.Update
        ):  # Проверка типа на всякий случай, хотя middleware принимает event как Update обычно в aiogram 3 но здесь BaseMiddleware
            # В Aiogram 3 BaseMiddleware получает event который может быть Update или сразу Message/Callback (в зависимости от того где зарегистрирован)
            # Здесь предполагается outer middleware, получающая Update? Нет, GetUserMiddleware обычно вешается на router.message/callback_query
            # Если она вешается на диспетчер как outer, то event это Update. Если как inner, то Message.
            # Судя по event.message в коде, это Update.
            if event.message:
                user_id = event.message.from_user.id
            elif event.callback_query:
                user_id = event.callback_query.from_user.id
        elif isinstance(event, types.Message):
            user_id = event.from_user.id
        elif isinstance(event, types.CallbackQuery):
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        user = await db.user.get_user(user_id)
        data["user"] = user

        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    """
    Глобальный обработчик ошибок (Middleware).

    Ловит необработанные исключения в хендлерах и логирует их.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            handler_name = getattr(handler, "__name__", "unknown_handler")
            logger.error(f"Ошибка в обработчике {handler_name}: {e}", exc_info=True)


class VersionCheckMiddleware(BaseMiddleware):
    """
    Middleware для автоматической проверки версии бота.

    При обновлении версии бота автоматически очищает устаревшие FSM состояния,
    чтобы пользователи работали с актуальной версией без необходимости
    ручного сброса через /start.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        state = data.get("state")

        if state:
            try:
                state_data = await state.get_data()
                bot_version = state_data.get("bot_version")

                # Если версия отличается или не установлена
                if bot_version != Config.VERSION:
                    # Логируем только если была старая версия (не первый запуск)
                    if bot_version is not None:
                        logger.debug(
                            f"Обнаружена устаревшая версия бота у пользователя. "
                            f"Старая: {bot_version}, Новая: {Config.VERSION}. Сброс состояния."
                        )
                        # Сбрасываем состояние только если была старая версия
                        await state.clear()

                    # Устанавливаем текущую версию
                    await state.update_data(bot_version=Config.VERSION)
            except Exception as e:
                logger.error(f"Ошибка в VersionCheckMiddleware: {e}", exc_info=True)

        return await handler(event, data)
