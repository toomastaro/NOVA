import logging
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.utils.token import validate_token, TokenValidationError
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.types import User

from config import Config

logger = logging.getLogger(__name__)


class BotManager:
    """
    Менеджер для управления экземпляром бота и его вебхуками.
    """
    def __init__(self, token: str):
        self.token = token
        self.bot: Bot | None = None
        self._me: User | None = None

    async def __aenter__(self):
        is_valid = await self.validate_token()
        if not is_valid:
            logger.error(f"Неверный токен передан в BotManager: {self.token[:10]}...")
            # Мы могли бы выбросить исключение здесь, если это критично,
            # но оригинальный код возвращал 'self' в любом случае.
            # Оставим как есть, но залогируем.
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def open(self):
        """Создает экземпляр бота, если он еще не создан."""
        if not self.bot:
            self.bot = Bot(
                token=self.token,
                default=DefaultBotProperties(
                    parse_mode=ParseMode.HTML
                )
            )

    async def close(self):
        """Закрывает сессию бота, если она открыта."""
        if self.bot:
            try:
                await self.bot.session.close()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии сессии бота: {e}")
            self.bot = None
            # Мы не очищаем self._me, так как информация о пользователях, вероятно, останется той же,
            # если мы переоткроем, но для безопасности можно и очистить.
            # Оставляем кешированным для производительности при повторном использовании менеджера.

    async def validate_token(self) -> User | bool:
        """
        Проверяет валидность токена и авторизацию.
        Кеширует результат get_me() для производительности.
        """
        # 1. Локальная валидация
        try:
            validate_token(self.token)
        except TokenValidationError:
            logger.error("Ошибка валидации токена: Неверный формат")
            return False

        # 2. Убеждаемся, что экземпляр бота существует
        await self.open()

        # 3. Возвращаем кешированную информацию, если есть
        if self._me:
            return self._me

        # 4. Сетевая валидация (get_me)
        try:
            me = await self.bot.get_me()
            self._me = me
            return me
        except TelegramUnauthorizedError:
            logger.error("Ошибка валидации токена: TelegramUnauthorizedError")
            return False
        except Exception as e:
            logger.error(f"Ошибка при валидации токена: {e}", exc_info=True)
            return False

    async def set_webhook(self, delete: bool = False) -> bool:
        """Устанавливает или удаляет вебхук."""
        me = await self.validate_token()
        if not me:
            return False

        webhook_url = Config.WEBHOOK_URL_BOT.format(Config.WEBHOOK_DOMAIN, self.token)

        try:
            await self.bot.delete_webhook(drop_pending_updates=True)
            if not delete:
                result = await self.bot.set_webhook(
                    url=webhook_url,
                    drop_pending_updates=True,
                    allowed_updates=[
                        "message",
                        "callback_query",
                        "chat_member",
                        "my_chat_member",
                        "chat_join_request",
                    ]
                )
                return result
            # Если delete=True, мы уже удалили его выше.
            return True
        except Exception as e:
            logger.error(f"Ошибка при установке вебхука: {e}", exc_info=True)
            return False

    async def status(self) -> bool | None:
        """Проверяет, установлен ли корректный вебхук."""
        me = await self.validate_token()
        if not me:
            return False

        webhook_url = Config.WEBHOOK_URL_BOT.format(Config.WEBHOOK_DOMAIN, self.token)

        try:
            info = await self.bot.get_webhook_info()
            return info.url == webhook_url
        except Exception as e:
            logger.error(f"Ошибка при получении статуса вебхука: {e}", exc_info=True)
            return None
