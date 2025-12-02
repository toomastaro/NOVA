from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.utils.token import validate_token, TokenValidationError
from aiogram.exceptions import TelegramUnauthorizedError

from config import Config


class BotManager:
    def __init__(self, token: str):
        self.token = token
        self.bot: Bot | None = None

    async def __aenter__(self):
        await self.validate_token()
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
            await self.bot.session.close()
            self.bot = None

    async def validate_token(self):
        """Проверяет валидность токена и авторизацию."""
        try:
            validate_token(self.token)
        except TokenValidationError:
            return False

        await self.open()

        try:
            me = await self.bot.get_me()
            return me
        except TelegramUnauthorizedError:
            return False
        except Exception as e:
            print(f"Ошибка при валидации токена: {e}")
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
            return True
        except Exception as e:
            print(f"Ошибка при установке вебхука: {e}")
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
            print(f"Ошибка при получении статуса вебхука: {e}")
            return None
