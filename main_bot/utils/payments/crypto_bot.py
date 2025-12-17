import json
import logging
from aiocryptopay import AioCryptoPay

from config import Config

logger = logging.getLogger(__name__)


class CryptoBot:
    """
    Класс для работы с Crypto Pay API.
    """

    def __init__(self, api_token: str):
        self.api_token = api_token

    async def get_crypto_bot_sum(self, summa: float, currency: str) -> float | None:
        """
        Рассчитать сумму в крипте по курсу RUB.
        """
        async with AioCryptoPay(token=self.api_token) as crypto_pay:
            crypto_pay: AioCryptoPay

            try:
                courses = await crypto_pay.get_exchange_rates()

                for course in courses:
                    if course.source == currency and course.target == "RUB":
                        return round(float(summa / course.rate), 8)
            except Exception as e:
                logger.error(f"Ошибка получения курсов CryptoBot: {e}")
                return None

    async def create_invoice(
        self, amount: float, asset: str = "USDT", payload: dict = None
    ) -> dict:
        """
        Создать счет на оплату.
        """
        async with AioCryptoPay(token=self.api_token) as crypto_pay:
            crypto_pay: AioCryptoPay

            amount_crypto = await self.get_crypto_bot_sum(summa=amount, currency=asset)

            if not amount_crypto:
                raise ValueError("Не удалось рассчитать сумму в криптовалюте")

            kwargs = {"amount": amount_crypto, "asset": asset}

            if payload:
                # Лимит payload в CryptoBot - 4kb
                kwargs["payload"] = json.dumps(payload)

            invoice = await crypto_pay.create_invoice(**kwargs)

            return {"url": invoice.bot_invoice_url, "invoice_id": invoice.invoice_id}

    async def is_paid(self, invoice_id: int) -> bool:
        """
        Проверить статус оплаты счета.
        """
        async with AioCryptoPay(token=self.api_token) as crypto_pay:
            crypto_pay: AioCryptoPay

            try:
                invoice = await crypto_pay.get_invoices(invoice_ids=invoice_id)
                return invoice.status == "paid"
            except Exception as e:
                logger.error(
                    f"Ошибка проверки статуса счета CryptoBot {invoice_id}: {e}"
                )
                return False

    async def delete_invoice(self, invoice_id: int) -> bool:
        """
        Удалить счет.
        """
        async with AioCryptoPay(token=self.api_token) as crypto_pay:
            crypto_pay: AioCryptoPay

            try:
                await crypto_pay.delete_invoice(invoice_id=invoice_id)
                return True
            except Exception as e:
                logger.error(f"Ошибка при удалении счета CryptoBot {invoice_id}: {e}")
                return False


crypto_bot = CryptoBot(api_token=Config.CRYPTO_BOT_TOKEN)
