from sqlalchemy import select, update
from main_bot.database import DatabaseMixin
from main_bot.database.payment_link.model import PaymentLink


class PaymentLinkCrud(DatabaseMixin):
    async def create_payment_link(self, user_id: int, amount: int, payload: dict, currency: str = "RUB") -> PaymentLink:
        payment_link = PaymentLink(
            user_id=user_id,
            amount=amount,
            currency=currency,
            payload=payload,
            status="PENDING"
        )
        return await self.add(payment_link)

    async def get_payment_link(self, link_id: str) -> PaymentLink | None:
        sql = select(PaymentLink).where(PaymentLink.id == link_id)
        return await self.fetchrow(sql)

    async def update_payment_link_status(self, link_id: str, status: str):
        sql = update(PaymentLink).where(PaymentLink.id == link_id).values(status=status)
        await self.execute(sql)
