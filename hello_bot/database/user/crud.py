from datetime import timedelta, datetime

from sqlalchemy import select, insert, update, func, and_
from sqlalchemy.dialects.postgresql import insert as p_insert

from utils.database_mixin import DatabaseMixin
from hello_bot.database.user.model import User


class UserCrud(DatabaseMixin):
    async def get_dump_users(self):
        return await self.fetch(
            select(User)
        )

    async def get_users(self, chat_id: int):
        return await self.fetch(
            select(User.id).where(
                User.is_active.is_(True),
                User.walk_captcha.is_(True),
                User.channel_id == chat_id
            )
        )

    async def get_time_users(self, chat_id: int, start_time, end_time, participant: bool = True):
        stmt = select(User).where(
            User.channel_id == chat_id,
            User.created_timestamp > start_time,
            User.created_timestamp < end_time,
            User.is_approved.is_(participant)
        )

        return await self.fetch(stmt)

    async def get_count_users(self, chat_id: int = None) -> dict:
        now = datetime.utcnow()

        start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_week = start_day - timedelta(days=start_day.weekday())
        start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        stmt = select(
            func.count(User.id).label("total_users"),
            func.count().filter(
                User.is_active.is_(True),
                User.walk_captcha.is_(True),
            ).label("active_users"),
            func.count().filter(
                and_(User.walk_captcha.is_(True), User.time_walk_captcha >= start_day.timestamp())
            ).label("day_walks"),
            func.count().filter(
                and_(User.walk_captcha.is_(True), User.time_walk_captcha >= start_week.timestamp())
            ).label("week_walks"),
            func.count().filter(
                and_(User.walk_captcha.is_(True), User.time_walk_captcha >= start_month.timestamp())
            ).label("month_walks"),
        )

        if chat_id:
            stmt = stmt.where(User.channel_id == chat_id)

        res = await self.fetchone(stmt)

        total = res.total_users or 0
        active = res.active_users or 0

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "walk_day": res.day_walks or 0,
            "walk_week": res.week_walks or 0,
            "walk_month": res.month_walks or 0,
        }

    async def get_captcha_users(self, chat_id: int):
        now = datetime.utcnow()

        start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_day = now.replace(hour=23, minute=59, second=0, microsecond=0)

        stmt = select(
            func.count().filter(
                and_(
                    User.created_timestamp > start_day.timestamp(),
                    User.created_timestamp < end_day.timestamp(),
                ),
            ).label("give_captcha"),
            func.count().filter(
                and_(
                    User.created_timestamp > start_day.timestamp(),
                    User.created_timestamp < end_day.timestamp(),
                ),
                User.time_walk_captcha.is_not(None)
            ).label("walk_captcha")
        ).where(User.channel_id == chat_id)

        result = await self.fetchone(stmt)

        try:
            conversion = int(result.walk_captcha / result.give_captcha)
        except ZeroDivisionError:
            conversion = 0

        return {
            "give_captcha": result.give_captcha or 0,
            "walk_captcha": result.walk_captcha or 0,
            "conversion": conversion,
        }

    async def get_count_not_approve_users(self, chat_id: int):
        return await self.fetchrow(
            select(func.count(User.id)).where(
                User.channel_id == chat_id,
                User.is_approved.is_(False)
            )
        )

    async def get_not_approve_users_by_chat_id(self, chat_id: int, get_url: bool = False, limit: int = None, invite_url: str = None):
        stmt = select(User).where(User.channel_id == chat_id)

        if invite_url:
            stmt = stmt.where(User.invite_url == invite_url)
        if limit:
            stmt = stmt.limit(limit)

        return await self.fetch(stmt)

    async def get_invite_urls(self, chat_id: int):
        return await self.fetch(
            select(User.invite_url).where(
                User.invite_url.is_not(None),
                User.channel_id == chat_id,
                User.is_approved.is_(False)
            )
        )

    async def get_user(self, user_id: int) -> User:
        return await self.fetchrow(
            select(User).where(
                User.id == user_id
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

    async def many_insert_user(self, users: list[dict]):
        stmt = p_insert(User).values(users)
        await self.execute(
            stmt.on_conflict_do_nothing(
                index_elements=['id']
            )
        )
