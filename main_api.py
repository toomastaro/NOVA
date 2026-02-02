"""
Основной модуль API приложения (FastAPI).

Запускает веб-сервер, настраивает маршруты, вебхуки и фоновые задачи.
Обеспечивает интеграцию с Telegram Bot API, платежными системами (Platega, CryptoBot)
и базой данных.

Переменные:
    app (FastAPI): Экземпляр приложения FastAPI.
    logger (logging.Logger): Логгер модуля.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from aiogram import Bot, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request

from config import Config
from hello_bot.handlers import set_routers
from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.db_types import PaymentMethod, Service
from main_bot.database.user_bot.model import UserBot
from main_bot.handlers import dp, set_main_routers, set_scheduler
from main_bot.utils.lang.language import text
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.logger import setup_logging
from main_bot.utils.schedulers import update_exchange_rates_in_db
from main_bot.utils.subscribe_service import grant_subscription

# Настройка логирования при старте модуля

from utils.error_handler import safe_handler

setup_logging()
logger = logging.getLogger(__name__)

dispatchers = {}


def set_dispatcher(db_bot: UserBot):
    """
    Получает или создает диспетчер для пользовательского бота.

    Если диспетчер уже создан для данного токена, возвращает его.
    Иначе инициализирует новые роутеры.

    Аргументы:
        db_bot (UserBot): Объект бота из базы данных.

    Возвращает:
        Dispatcher: Диспетчер aiogram.
    """
    if db_bot.token in dispatchers:
        return dispatchers[db_bot.token]

    other_dp = set_routers()
    dispatchers[db_bot.token] = other_dp

    return other_dp


async def refresh_all_bot_webhooks():
    """
    Принудительно обновляет вебхуки для всех активных ботов в базе данных.
    Это необходимо для обновления списка allowed_updates (добавление chat_join_request).
    """
    logger.info("Начало принудительного обновления вебхуков всех ботов...")
    try:
        bots = await db.user_bot.get_all_bots()
        logger.info(f"Найдено {len(bots)} ботов для обновления.")
        for bot_data in bots:
            try:
                # Используем BotManager для установки вебхука
                # Он автоматически добавит chat_join_request в allowed_updates
                async with BotManager(bot_data.token) as manager:
                    success = await manager.set_webhook()
                    if success:
                        logger.info(f"Вебхук успешно обновлен для бота @{bot_data.username}")
                    else:
                        logger.warning(f"Не удалось обновить вебхук для бота @{bot_data.username}")
            except Exception as e:
                logger.error(f"Ошибка при работе с BotManager для бота {bot_data.username}: {e}")
    except Exception as e:
        logger.error(f"Критическая ошибка при получении списка ботов: {e}")
    logger.info("Принудительное обновление вебхуков завершено.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Управляет жизненным циклом приложения FastAPI.

    Выполняется при старте и остановке сервера.
    - Старт: Настройка часового пояса, роутеров, БД, планировщика, вебхуков.
    - Стоп: Удаление вебхуков.
    """
    os.environ["TZ"] = "Europe/Moscow"
    time.tzset()

    set_main_routers()

    logger.info(f"BACKUP_CHAT_ID: {Config.BACKUP_CHAT_ID}")
    if not Config.BACKUP_CHAT_ID:
        logger.warning("BACKUP_CHAT_ID is not set or is 0!")

    await db.create_tables()
    await set_scheduler()

    # Обновляем курс валют при старте
    try:
        await update_exchange_rates_in_db()
    except Exception as e:
        logger.exception(f"Ошибка при обновлении курсов валют на старте: {e}")

    # Настройка Webhook для основного бота
    webhook_url = f"{Config.WEBHOOK_DOMAIN}/webhook/main"
    logger.info(f"Установка вебхука: {webhook_url}")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=[
            "message",
            "callback_query",
            "pre_checkout_query",
            "chat_member",
            "my_chat_member",
            "chat_join_request",
        ],
    )

    # 3. Обновляем вебхуки для всех пользовательских ботов (фоновая задача)
    # Это форсирует обновление allowed_updates для всех существующих ботов
    asyncio.create_task(refresh_all_bot_webhooks())

    yield

    # Удаление вебхука и закрытие сессии основного бота
    logger.info("Закрытие сессии основного бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()

    # Закрытие сессий всех пользовательских ботов
    if bot_instances:
        logger.info(f"Закрытие сессий {len(bot_instances)} пользовательских ботов...")
        for token, b_inst in bot_instances.items():
            try:
                await b_inst.session.close()
            except Exception as e:
                logger.error(f"Ошибка при закрытии сессии бота {token[:10]}: {e}")
        bot_instances.clear()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
@safe_handler("API: Health Check", log_start=False)
async def health_check():
    """
    Проверка работоспособности сервиса (Health Check).

    Возвращает:
        dict: Статус сервиса.
    """
    return {"status": "ok", "message": "Service is running"}


@app.post("/webhook/main")
@safe_handler("API: webhook main — приём update")
async def main_update(request: Request):
    """
    Обработчик вебхуков для основного бота.

    Аргументы:
        request (Request): HTTP запрос от Telegram.
    """
    data = await request.json()
    update = types.Update.model_validate(data)

    if update.chat_join_request:
        cjr = update.chat_join_request
        logger.info(f"ОСНОВНОЙ БОТ: Получен chat_join_request от {cjr.from_user.id} в чат {cjr.chat.id}")
    elif update.message:
        logger.debug(f"ОСНОВНОЙ БОТ: Получено сообщение от {update.message.from_user.id}")

    await dp.feed_update(bot=bot, update=update)


@app.post("/webhook/platega")
@safe_handler("API: webhook Platega — обработка платежа")
async def platega_webhook(request: Request):
    """
    Обработчик вебхуков платежной системы Platega.

    Проверяет подпись запроса, статус платежа и начисляет баланс/услугу.

    Аргументы:
        request (Request): HTTP запрос от Platega.

    Возвращает:
        dict: Результат обработки.
    """
    headers = request.headers
    merchant_id = headers.get("X-MerchantId")
    secret = headers.get("X-Secret")

    # Логируем входящий запрос
    logger.info(
        f"Platega Callback: MerchantId={merchant_id}, Secret={'***' if secret else 'None'}"
    )

    if merchant_id != Config.PLATEGA_MERCHANT or secret != Config.PLATEGA_SECRET:
        logger.warning(
            f"Platega: Неверные учетные данные. Ожидалось: {Config.PLATEGA_MERCHANT}, Получено: {merchant_id}"
        )
        return {"status": "error", "message": "Invalid credentials"}

    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Platega: Ошибка парсинга JSON: {e}")
        return {"status": "error", "message": "Invalid JSON"}

    logger.info(f"Platega Payload: {data}")

    order_id = data.get("id")
    status = data.get("status")

    if not order_id or not status:
        logger.warning("Platega: Некорректная нагрузка: нет id или status")
        return {"status": "error", "message": "Invalid payload"}

    payment_link = await db.payment_link.get_payment_link(order_id)
    if not payment_link:
        logger.warning(f"Platega: Ссылка на оплату не найдена для Order ID: {order_id}")
        return {"status": "error", "message": "Payment link not found"}

    if payment_link.status == "PAID":
        logger.info(f"Platega: Заказ {order_id} уже оплачен (PAID)")
        return {"status": "ok", "message": "Already paid"}

    logger.info(f"Platega: Обработка заказа {order_id} со статусом {status}")

    if status == "CONFIRMED":
        await db.payment_link.update_payment_link_status(order_id, "PAID")

        await process_successful_payment(
            user_id=int(payment_link.user_id), payload=payment_link.payload
        )

    return {"status": "ok"}


async def process_successful_payment(user_id: int, payload: dict, amount: float = None):
    """
    Общая логика обработки успешных платежей (Platega и CryptoBot).

    Аргументы:
        user_id (int): Telegram ID пользователя.
        payload (dict): Данные платежа (тип, метод и т.д.).
        amount (float, optional): Сумма платежа. Если не передана, пытаемся взять из payload.
    """
    payment_type = payload.get("type")

    # Логика пополнения баланса
    if payment_type == "balance":
        if amount is None:
            amount = payload.get("amount")

        if not amount:
            logger.error(f"Платеж {payment_type} для пользователя {user_id} без суммы!")
            return

        amount = float(amount)
        logger.info(f"Пополнение баланса {amount} для пользователя {user_id}")

        user = await db.user.get_user(user_id=user_id)
        if user:
            await db.user.update_user(user_id=user.id, balance=user.balance + amount)

            method_str = payload.get("method", "UNKNOWN")

            if method_str == "CRYPTO_BOT":
                method = PaymentMethod.CRYPTO_BOT
            elif method_str == "PLATEGA":
                method = PaymentMethod.PLATEGA
            else:
                method = PaymentMethod.PLATEGA

            await db.payment.add_payment(user_id=user.id, amount=amount, method=method)

            try:
                await bot.send_message(user_id, text("success_payment").format(amount))
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об успехе {user_id}: {e}")

    # Логика подписки
    elif payment_type == "subscribe":
        logger.info(f"Выдача подписки пользователю {user_id}")

        chosen = payload.get("chosen")
        total_days = payload.get("total_days")
        service_name = payload.get("service")
        object_type = payload.get("object_type")
        total_price = payload.get("total_price")

        await grant_subscription(user_id, chosen, total_days, service_name, object_type)

        # Реферальная логика
        referral_id = payload.get("referral_id")

        if referral_id:
            ref_user = await db.user.get_user(referral_id)
            if ref_user:
                try:
                    # Проверяем была ли покупка РАНЕЕ
                    has_purchase = await db.purchase.has_purchase(user_id)
                    percent = 15 if has_purchase else 60
                    total_ref_earn = int(total_price / 100 * percent)

                    logger.info(
                        f"Реферальный бонус {total_ref_earn} для {referral_id} (percent={percent}%)"
                    )

                    await db.user.update_user(
                        user_id=ref_user.id,
                        balance=ref_user.balance + total_ref_earn,
                        referral_earned=ref_user.referral_earned + total_ref_earn,
                    )
                except Exception as e:
                    logger.error(f"Ошибка реферальной логики: {e}")

        # Записываем покупку
        method_str = payload.get("method", "PLATEGA")
        if method_str == "CRYPTO_BOT":
            method = PaymentMethod.CRYPTO_BOT
        else:
            method = PaymentMethod.PLATEGA

        service_enum = Service.POSTING
        if service_name == "stories":
            service_enum = Service.STORIES
        elif object_type == "bots":
            service_enum = Service.BOTS

        await db.purchase.add_purchase(
            user_id=user_id, amount=total_price, method=method, service=service_enum
        )

        try:
            await bot.send_message(user_id, text("success_subscribe_pay"))
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об успехе {user_id}: {e}")


@app.post("/webhook/cryptobot")
@safe_handler("API: webhook CryptoBot — обработка платежа")
async def cryptobot_webhook(request: Request):
    """
    Обработчик вебхуков CryptoBot.

    Проверяет подпись запроса и обрабатывает оплаченные инвойсы.

    Аргументы:
        request (Request): HTTP запрос от CryptoBot.

    Возвращает:
        dict: Результат обработки (ok=True/False).
    """
    try:
        body = await request.body()
        data = await request.json()
    except Exception as e:
        logger.error(f"CryptoBot: Ошибка парсинга JSON: {e}")
        return {"ok": False}

    # Проверка подписи
    signature = request.headers.get("crypto-pay-api-signature")
    if not signature:
        logger.warning("CryptoBot: Отсутствует подпись")
        return {"ok": False}

    token = Config.CRYPTO_BOT_TOKEN
    secret = hashlib.sha256(token.encode()).digest()
    hmac_digest = hmac.new(secret, body, hashlib.sha256).hexdigest()

    if hmac_digest != signature:
        logger.warning(
            f"CryptoBot: Неверная подпись. Получено: {signature}, Вычислено: {hmac_digest}"
        )
        return {"ok": False}

    if data.get("update_type") != "invoice_paid":
        return {"ok": True}

    # Извлечение данных из payload
    invoice = data.get("payload", {})
    custom_payload_str = invoice.get("payload")

    if not custom_payload_str:
        logger.warning("CryptoBot: Отсутствует custom_payload в инвойсе")
        return {"ok": True}

    try:
        custom_payload = json.loads(custom_payload_str)
    except Exception as e:
        logger.error(f"CryptoBot: Ошибка JSON в payload: {e}")
        return {"ok": True}

    user_id = custom_payload.get("user_id")
    if not user_id:
        logger.error("CryptoBot: Нет user_id в payload")
        return {"ok": True}

    logger.info(f"CryptoBot: Инвойс оплачен. Обработка для пользователя {user_id}")

    await process_successful_payment(
        user_id=int(user_id),
        payload=custom_payload,
        amount=float(invoice.get("amount", 0)),
    )

    return {"ok": True}


bot_instances = {}


def get_bot_instance(token: str) -> Bot:
    """
    Получает или создает экземпляр бота для данного токена.
    Использует кэш для предотвращения утечек сессий и лишних соединений.
    """
    if token not in bot_instances:
        logger.info(f"Создание нового экземпляра Bot для токена {token[:10]}...")
        bot_instances[token] = Bot(
            token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    return bot_instances[token]


@app.post("/webhook/{token}")
@safe_handler("API: webhook UserBot — приём update")
async def other_update(request: Request, token: str):
    """
    Обработчик вебхуков для пользовательских ботов.

    Аргументы:
        request (Request): HTTP запрос.
        token (str): Токен бота в URL.
    """
    data = await request.json()
    update = types.Update.model_validate(data)

    if update.chat_join_request:
        cjr = update.chat_join_request
        logger.info(f"ЮЗЕРБОТ ({token[:10]}...): Получен chat_join_request от {cjr.from_user.id} в чат {cjr.chat.id}")

    exist = await db.user_bot.get_bot_by_token(token)
    if not exist:
        logger.warning(f"Получен апдейт для несуществующего в БД бота: {token[:10]}...")
        return

    try:
        other_bot = get_bot_instance(token)
    except Exception as e:
        logger.error(f"Ошибка получения бота для токена {token}: {e}", exc_info=True)
        return

    other_dp = set_dispatcher(exist)
    await other_dp.feed_update(other_bot, update)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099, log_level="warning", access_log=False)
