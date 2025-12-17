import asyncio
import uuid
import logging
from httpx import AsyncClient

from config import Config

logger = logging.getLogger(__name__)


class Platega:
    """
    Класс для работы с платежным шлюзом Platega.
    """
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

    async def create_invoice(self, order_id: str, amount: float, description: str) -> dict:
        """
        Создать платеж.
        """
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
            logger.info(f"Platega Создание счета: {params}")
            res = await self.client.post('/transaction/process', json=params)
            
            logger.info(f"Platega Статус ответа: {res.status_code}")
            logger.info(f"Platega Тело ответа: {res.text}")

            res.raise_for_status()
            res_json = res.json()
            
            # Маппинг полей ответа для обработчика
            if 'redirect' in res_json:
                res_json['pay_url'] = res_json['redirect']
            
            # Ответ использует 'transactionId', но мы используем 'order_id' как основной ID.
            # Обработчик ожидает 'id'. В ответе Platega может не быть 'id', или 'transactionId' совпадает с order_id.
            if 'transactionId' in res_json:
                res_json['id'] = res_json['transactionId']
            else:
                res_json['id'] = order_id # Возврат к нашему ID

            # Попытка H2H (пропускаем в текущей версии, так как redirect достаточно)
            try:
                pass 
            except Exception as e:
                logger.error(f"Ошибка получения H2H ссылки Platega: {e}")

            return res_json
        except Exception as e:
            logger.error(f"Ошибка создания счета Platega: {e}", exc_info=True)
            return {}

    async def h2h_invoice(self, invoice_id: str):
        """Получить H2H данные (QR код)"""
        res = await self.client.get(f'/h2h/{invoice_id}')
        return res.json().get("qr")

    async def check_invoice(self, invoice_id: str):
        """Проверить статус транзакции"""
        res = await self.client.get(f'/transaction/{invoice_id}')
        return res.json()

    async def is_paid(self, invoice_id: str) -> bool:
        """Проверить, оплачен ли счет"""
        payment = await self.check_invoice(invoice_id)

        if not payment:
            return False

        return payment.get('status') == 'CONFIRMED'
    
    async def cancel_invoice(self, invoice_id: str) -> bool:
        """Отменить платеж Platega"""
        try:
            logger.info(f"Platega Отмена счета: {invoice_id}")
            res = await self.client.post(f'/transaction/{invoice_id}/cancel')
            logger.info(f"Platega Статус отмены: {res.status_code}")
            logger.info(f"Platega Тело отмены: {res.text}")
            
            if res.status_code == 200:
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка отмены счета Platega: {e}", exc_info=True)
            return False


platega_api = Platega(
    merchant_id=Config.PLATEGA_MERCHANT,
    secret_key=Config.PLATEGA_SECRET
)


async def main():
    # Тестовый запуск
    # В продакшене этот код не вызывается
    logging.basicConfig(level=logging.INFO)
    r = await platega_api.create_invoice(
        order_id=str(uuid.uuid4()),
        amount=10,
        description='123'
    )
    logger.info(f"Результат теста: {r}")


if __name__ == '__main__':
    asyncio.run(main())
