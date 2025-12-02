from aiocryptopay import AioCryptoPay

from config import Config


class CryptoBot:
    def __init__(self, api_token: str):
        self.api_token = api_token

    async def get_crypto_bot_sum(self, summa: float, currency: str):
        async with AioCryptoPay(token=self.api_token) as crypto_pay:
            crypto_pay: AioCryptoPay

            courses = await crypto_pay.get_exchange_rates()

            for course in courses:
                if course.source == currency and course.target == 'RUB':
                    return round(float(summa / course.rate), 8)

    async def create_invoice(self, amount: float, asset: str = 'USDT'):
        async with AioCryptoPay(token=self.api_token) as crypto_pay:
            crypto_pay: AioCryptoPay

            amount = await self.get_crypto_bot_sum(
                summa=amount,
                currency=asset
            )
            invoice = await crypto_pay.create_invoice(
                amount=amount,
                asset=asset
            )

            return {
                'url': invoice.bot_invoice_url,
                'invoice_id': invoice.invoice_id
            }

    async def is_paid(self, invoice_id: int):
        async with AioCryptoPay(token=self.api_token) as crypto_pay:
            crypto_pay: AioCryptoPay

            try:
                invoice = await crypto_pay.get_invoices(
                    invoice_ids=invoice_id
                )
            except Exception as e:
                return print(e)

            return invoice.status == 'paid'


crypto_bot = CryptoBot(
    api_token=Config.CRYPTO_BOT_TOKEN
)
