from sqlalchemy import select, update, insert, delete, func, asc

from main_bot.database import DatabaseMixin
from main_bot.database.channel_bot_hello.model import ChannelHelloMessage


class ChannelHelloMessageCrud(DatabaseMixin):
    async def get_next_id_hello_message(self):
        max_id = await self.fetchrow(
            select(func.max(ChannelHelloMessage.id))
        )

        if not max_id:
            max_id = 0

        return max_id + 1

    async def add_channel_hello_message(self, **kwargs):
        await self.execute(
            insert(ChannelHelloMessage).values(
                **kwargs
            )
        )

    async def get_hello_messages(self, chat_id: int, active: bool = False):
        stmt = select(ChannelHelloMessage).where(
            ChannelHelloMessage.channel_id == chat_id
        ).order_by(asc(ChannelHelloMessage.id))

        if active:
            stmt = stmt.where(ChannelHelloMessage.is_active.is_(True))

        return await self.fetch(stmt)

    async def get_hello_message(self, message_id: int) -> ChannelHelloMessage:
        return await self.fetchrow(
            select(ChannelHelloMessage).where(
                ChannelHelloMessage.id == message_id
            )
        )

    async def update_hello_message(self, message_id: int, return_obj: bool = False, **kwargs) -> ChannelHelloMessage | None:
        stmt = update(ChannelHelloMessage).where(ChannelHelloMessage.id == message_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(ChannelHelloMessage)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})

    async def delete_hello_message(self, message_id: int):
        await self.execute(
            delete(ChannelHelloMessage).where(
                ChannelHelloMessage.id == message_id
            )
        )
