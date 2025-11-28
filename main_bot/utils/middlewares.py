import re
from aiogram import BaseMiddleware, types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import CommandObject
from aiogram.types import Update

from main_bot.database.db import db
from main_bot.utils.functions import create_emoji
from utils.logger import logger


class StartMiddle(BaseMiddleware):
    async def __call__(self, handler, message: types.Message, data):
        command: CommandObject = data.get("command")
        if command.command != "start":
            return

        user_obj = message.from_user
        user = await db.get_user(user_obj.id)

        # Обрабатываем параметры startchannel (когда бот добавляется в канал)
        if command.args:
            await self._handle_start_params(message, command.args, user_obj)

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
                    if "utm" in start_utm:
                        ads_tag = start_utm.replace("utm-", "")
                        tag = await db.get_ad_tag(ads_tag)

                        if not tag:
                            ads_tag = None

            await db.add_user(
                id=user_obj.id,
                is_premium=user_obj.is_premium or False,
                referral_id=referral_id,
                ads_tag=ads_tag,
            )

        return await handler(message, data)

    async def _handle_start_params(self, message: types.Message, args: str, user_obj: types.User):
        """Обрабатывает специальные параметры start команды"""
        try:
            # Проверяем, есть ли параметры для добавления канала
            if "startchannel" in args or re.search(r'channel.*=(\d+)', args):
                await self._handle_channel_addition(message, args, user_obj)

        except Exception as e:
            logger.error(f"Ошибка обработки start параметров: {e}")

    async def _handle_channel_addition(self, message: types.Message, args: str, user_obj: types.User):
        """Обрабатывает добавление канала через start параметры"""
        try:
            # Пытаемся извлечь ID канала из параметров
            channel_match = re.search(r'channel.*=(\d+)', args)
            if not channel_match:
                return

            # Получаем ID канала из параметров URL
            channel_id_str = channel_match.group(1)
            chat_id = -int('100' + channel_id_str)

            logger.info(f"Пользователь {user_obj.id} пытается добавить канал через start: {chat_id}")

            # Проверяем, не добавлен ли уже канал
            user_channel = await db.get_channel_admin_row(chat_id=chat_id, user_id=user_obj.id)
            if user_channel:
                await message.answer("ℹ️ Канал уже добавлен в ваш список")
                return

            # Проверяем, является ли бот админом канала
            try:
                bot_member = await message.bot.get_chat_member(chat_id, message.bot.id)
                if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                    await message.answer(
                        "❌ Бот не является администратором канала. Пожалуйста, добавьте бота в администраторы канала с необходимыми правами."
                    )
                    return
            except Exception:
                await message.answer(
                    "❌ Не удалось проверить статус бота в канале. Убедитесь, что бот добавлен в канал как администратор."
                )
                return

            # Проверяем права пользователя
            try:
                user_member = await message.bot.get_chat_member(chat_id, user_obj.id)
                if user_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                    await message.answer("❌ Вы не являетесь администратором этого канала")
                    return

                if user_member.status == ChatMemberStatus.ADMINISTRATOR:
                    rights = {
                        user_member.can_post_messages,
                        user_member.can_edit_messages,
                        user_member.can_delete_messages,
                    }
                    if False in rights:
                        await message.answer("❌ У вас недостаточно прав в канале")
                        return
            except Exception:
                await message.answer("❌ Не удалось проверить ваши права в канале")
                return

            # Получаем информацию о канале
            try:
                chat = await message.bot.get_chat(chat_id)
            except Exception:
                await message.answer("❌ Не удалось получить информацию о канале")
                return

            # Создаем emoji для канала
            channel = await db.get_channel_by_chat_id(chat_id)
            if channel:
                emoji_id = channel.emoji_id
            else:
                if chat.photo:
                    photo_bytes = await message.bot.download(chat.photo.big_file_id)
                else:
                    photo_bytes = None
                emoji_id = await create_emoji(user_obj.id, photo_bytes)

            # Добавляем канал в базу данных
            await db.add_channel(
                chat_id=chat_id,
                title=chat.title,
                admin_id=user_obj.id,
                emoji_id=emoji_id,
            )

            await message.answer(
                f"✅ Канал <tg-emoji emoji-id=\"{emoji_id}\">👤</tg-emoji> {chat.title} успешно добавлен!\n\n"
                f"Теперь вы можете использовать его для постинга. Перейдите в меню 📝 Постинг для создания постов.",
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error(f"Ошибка при добавлении канала через start: {e}")
            await message.answer("❌ Произошла ошибка при добавлении канала")


class GetUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        if event.message:
            user_id = event.message.from_user.id
        else:
            if not event.callback_query:
                return await handler(event, data)

            user_id = event.callback_query.from_user.id

        user = await db.get_user(user_id)
        data["user"] = user

        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        try:
            return await handler(event, data)
        except Exception as e:
            logger.opt(exception=e).error(f"Ошибка в обработчике {handler.__name__}")
