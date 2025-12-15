import logging

from main_bot.database import DatabaseMixin
from main_bot.database.payment.model import Payment
from sqlalchemy import insert

logger = logging.getLogger(__name__)


class PaymentCrud(DatabaseMixin):
    async def add_payment(self, **kwargs):
        await self.execute(insert(Payment).values(**kwargs))
