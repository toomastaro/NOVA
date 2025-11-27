from sqlalchemy import select, insert, update, func

from main_bot.database import DatabaseMixin
from main_bot.database.user.model import User


class UserCrud(DatabaseMixin):
    async def get_users(self):
        return await self.fetch(
            select(User)
        )

    async def get_user(self, user_id: int) -> User:
        return await self.fetchrow(
            select(User).where(
                User.id == user_id
            )
        )

    async def get_count_user_referral(self, user_id: int):
        return await self.fetchrow(
            select(func.count(User.id)).where(
                User.referral_id == user_id
            )
        )

    async def add_user(self, **kwargs):
        await self.execute(
            insert(User).values(
                **kwargs
            )
        )

    async def update_user(self, user_id: int, return_obj: bool = False, **kwargs) -> User | None:
        stmt = update(User).where(User.id == user_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(User)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})
