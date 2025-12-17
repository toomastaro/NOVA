"""
Модуль операций базы данных для платежных ссылок.
"""

import logging

from sqlalchemy import select, update

from main_bot.database import DatabaseMixin
from main_bot.database.payment_link.model import PaymentLink

logger = logging.getLogger(__name__)


class PaymentLinkCrud(DatabaseMixin):
    """
    Класс для управления платежными ссылками.
    """

    async def create_payment_link(
        self, user_id: int, amount: int, payload: dict, currency: str = "RUB"
    ) -> PaymentLink:
        """
        Создает новую платежную ссылку.

        Аргументы:
            user_id (int): ID пользователя.
            amount (int): Сумма.
            payload (dict): Полезная нагрузка (контекст операции).
            currency (str): Валюта.

        Возвращает:
            PaymentLink: Созданный объект ссылки.
        """
        payment_link = PaymentLink(
            user_id=user_id,
            amount=amount,
            currency=currency,
            payload=payload,
            status="PENDING",
        )
        return await self.add(payment_link)

    async def get_payment_link(self, link_id: str) -> PaymentLink | None:
        """
        Получает платежную ссылку по ID.

        Аргументы:
            link_id (str): UUID ссылки.

        Возвращает:
            PaymentLink | None: Объект ссылки.
        """
        sql = select(PaymentLink).where(PaymentLink.id == link_id)
        return await self.fetchrow(sql)

    async def update_payment_link_status(self, link_id: str, status: str) -> None:
        """
        Обновляет статус платежной ссылки.

        Аргументы:
            link_id (str): UUID ссылки.
            status (str): Новый статус (PENDING, PAID, CANCELED и т.д.).
        """
        sql = update(PaymentLink).where(PaymentLink.id == link_id).values(status=status)
        await self.execute(sql)
