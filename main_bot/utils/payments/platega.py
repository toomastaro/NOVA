import asyncio
import uuid

from httpx import AsyncClient

from config import Config


class Platega:
    def __init__(self, merchant_id: str, secret_key: str, base_url: str = 'https://app.platega.io'):
        self.base_url = base_url
        self.headers = {
            'X-MerchantId': merchant_id,
            'X-Secret': secret_key,
            'Content-Type': 'application/json'
        }
        self.client = AsyncClient(
            base_url=self.base_url,
            headers=self.headers
        )

    async def create_invoice(self, order_id: str, amount: float, description: str):
        import logging
        logger = logging.getLogger(__name__)

        params = {
          "paymentMethod": 2,
          "id": order_id,
          "paymentDetails": {
            "amount": int(amount),
            "currency": "RUB"
          },
          "description": description,
          "return": Config.BOT_LINK,
          "failedUrl": Config.BOT_LINK,
        }

        try:
            logger.info(f"Platega Creating invoice: {params}")
            res = await self.client.post('/transaction/process', json=params)
            
            logger.info(f"Platega Response Status: {res.status_code}")
            logger.info(f"Platega Response Body: {res.text}")

            res.raise_for_status()
            res_json = res.json()
            
            # Additional h2h call (check if really needed or if pay_url is already in res_json)
            # Documentation says "CreateTransactionResponse" schema. It probably has 'pay_url' or similar.
            # If h2h is required, we keep it.
            h2h_url = await self.h2h_invoice(invoice_id=order_id)
            res_json['qr'] = h2h_url

            return res_json
        except Exception as e:
            logger.error(f"Platega Create Invoice Error: {e}", exc_info=True)
            return {}

    async def h2h_invoice(self, invoice_id: str):
        res = await self.client.get(f'/h2h/{invoice_id}')
        return res.json().get("qr")

    async def check_invoice(self, invoice_id: str):
        res = await self.client.get(f'/transaction/{invoice_id}')
        return res.json()

    async def is_paid(self, invoice_id: str):
        payment = await self.check_invoice(invoice_id)

        if not payment:
            return False

        return payment.get('status') == 'CONFIRMED'


platega_api = Platega(
    merchant_id=Config.PLATEGA_MERCHANT,
    secret_key=Config.PLATEGA_SECRET
)


async def main():
    r = await platega_api.create_invoice(
        order_id=str(uuid.uuid4()),
        amount=10,
        description='123'
    )
    print(r)


if __name__ == '__main__':
    asyncio.run(main())
