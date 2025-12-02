from sqlalchemy import insert

from main_bot.database import DatabaseMixin
from main_bot.database.payment.model import Payment


class PaymentCrud(DatabaseMixin):
    async def add_payment(self, **kwargs):
        await self.execute(
            insert(Payment).values(
                **kwargs
            )
        )
