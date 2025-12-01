from sqlalchemy import select, update, insert, delete, asc

from main_bot.database import DatabaseMixin
from main_bot.database.channel_bot_captcha.model import ChannelCaptcha


class ChannelCaptchaMessageCrud(DatabaseMixin):
    async def add_channel_captcha(self, **kwargs):
        await self.execute(
            insert(ChannelCaptcha).values(
                **kwargs
            )
        )

    async def get_all_captcha(self, chat_id: int):
        return await self.fetch(
            select(ChannelCaptcha).where(
                ChannelCaptcha.channel_id == chat_id
            ).order_by(asc(ChannelCaptcha.id))
        )

    async def get_captcha(self, message_id: int) -> ChannelCaptcha:
        return await self.fetchrow(
            select(ChannelCaptcha).where(
                ChannelCaptcha.id == message_id
            )
        )

    async def update_captcha(self, captcha_id: int, return_obj: bool = False, **kwargs) -> ChannelCaptcha | None:
        stmt = update(ChannelCaptcha).where(ChannelCaptcha.id == captcha_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(ChannelCaptcha)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})

    async def delete_captcha(self, message_id: int):
        await self.execute(
            delete(ChannelCaptcha).where(
                ChannelCaptcha.id == message_id
            )
        )
