from sqlalchemy import select, update

from utils.database_mixin import DatabaseMixin
from hello_bot.database.settings.model import Setting


class SettingCrud(DatabaseMixin):
    async def get_setting(self) -> Setting:
        return await self.fetchrow(
            select(Setting)
        )

    async def update_setting(self, return_obj: bool = False, **kwargs) -> Setting | None:
        stmt = update(Setting).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Setting)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})
