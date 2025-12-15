from aiogram import BaseMiddleware, types
from aiogram.filters import CommandObject
from aiogram.types import Update

import logging
from main_bot.database.db import db

logger = logging.getLogger(__name__)


class StartMiddle(BaseMiddleware):
    """
    Middleware для обработки команды /start и регистрации пользователя.
    """
    async def __call__(self, handler, message: types.Message, data):
        command: CommandObject = data.get('command')
        
        # Если это не команда или не команда start, просто передаем управление дальше
        if not command or command.command != 'start':
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
                    if 'utm' in start_utm:
                        ads_tag = start_utm.replace('utm-', "")
                        tag = await db.ad_tag.get_ad_tag(ads_tag)

                        if not tag:
                            ads_tag = None

            try:
                await db.user.add_user(
                    id=user_obj.id,
                    is_premium=user_obj.is_premium or False,
                    referral_id=referral_id,
                    ads_tag=ads_tag
                )
            except Exception as e:
                logger.error(f"Ошибка при регистрации пользователя {user_obj.id}: {e}", exc_info=True)

        return await handler(message, data)


class GetUserMiddleware(BaseMiddleware):
    """
    Middleware для получения объекта пользователя из БД и добавления в data.
    """
    async def __call__(self, handler, event: Update, data):
        user_id = None
        if event.message:
            user_id = event.message.from_user.id
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
        
        if not user_id:
            return await handler(event, data)

        user = await db.user.get_user(user_id)
        data['user'] = user

        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    """
    Global error handler middleware.
    """
    async def __call__(self, handler, event: Update, data):
        try:
            return await handler(event, data)
        except Exception as e:
            handler_name = getattr(handler, '__name__', 'unknown_handler')
            logger.error(
                f"Ошибка в обработчике {handler_name}: {e}",
                exc_info=True
            )


class VersionCheckMiddleware(BaseMiddleware):
    """
    Middleware для автоматической проверки версии бота.
    
    При обновлении версии бота автоматически очищает устаревшие FSM состояния,
    чтобы пользователи работали с актуальной версией без необходимости
    ручного сброса через /start.
    """
    
    async def __call__(self, handler, event: Update, data):
        from config import Config
        
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
