from aiogram import BaseMiddleware, types
from aiogram.filters import CommandObject
from aiogram.types import Update

import logging
from main_bot.database.db import db

logger = logging.getLogger(__name__)


class StartMiddle(BaseMiddleware):
    async def __call__(self, handler, message: types.Message, data):
        command: CommandObject = data.get('command')
        if command.command != 'start':
            return

        user_obj = message.from_user
        user = await db.get_user(user_obj.id)

        if not user:
            referral_id = None
            ads_tag = None

            if command.args:
                start_utm = command.args
                if start_utm.isdigit():
                    ref_user = await db.get_user(int(start_utm))

                    if ref_user:
                        referral_id = int(start_utm)
                else:
                    if 'utm' in start_utm:
                        ads_tag = start_utm.replace('utm-', "")
                        tag = await db.get_ad_tag(ads_tag)

                        if not tag:
                            ads_tag = None

            await db.add_user(
                id=user_obj.id,
                is_premium=user_obj.is_premium or False,
                referral_id=referral_id,
                ads_tag=ads_tag
            )

        return await handler(message, data)


class GetUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        if event.message:
            user_id = event.message.from_user.id
        else:
            if not event.callback_query:
                return await handler(event, data)

            user_id = event.callback_query.from_user.id

        user = await db.get_user(user_id)
        data['user'] = user

        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(
                f"Ошибка в обработчике {handler.__name__}",
                exc_info=True
            )
