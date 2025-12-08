import os
import time
from contextlib import asynccontextmanager

import uvicorn
from aiogram import types, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request

from config import Config
from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.user_bot.model import UserBot
from main_bot.handlers import set_main_routers, set_scheduler, dp
from hello_bot.handlers import set_routers
from main_bot.utils.logger import setup_logging

setup_logging()


dispatchers = {}


def set_dispatcher(db_bot: UserBot):
    if db_bot.token in dispatchers:
        return dispatchers[db_bot.token]

    other_dp = set_routers()
    dispatchers[db_bot.token] = other_dp

    return other_dp


@asynccontextmanager
async def lifespan(_app: FastAPI):
    os.environ['TZ'] = 'Europe/Moscow'
    time.tzset()

    set_main_routers()
    set_scheduler()

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"BACKUP_CHAT_ID: {Config.BACKUP_CHAT_ID}")
    if not Config.BACKUP_CHAT_ID:
        logger.warning("BACKUP_CHAT_ID is not set or is 0!")

    await db.create_tables()

    # Bot Setting
    await bot.delete_webhook(
        drop_pending_updates=True
    )
    await bot.set_webhook(
        url=Config.WEBHOOK_DOMAIN + '/webhook/main',
        allowed_updates=[
            'message',
            'callback_query',
            'pre_checkout_query',
            'chat_member',
            'my_chat_member',
        ]
    )

    yield

    await bot.delete_webhook(
        drop_pending_updates=True
    )


app = FastAPI(
    lifespan=lifespan
)


@app.get('/health')
async def health_check():
    return {"status": "ok", "message": "Service is running"}


@app.post('/webhook/main')
async def main_update(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data)

    await dp.feed_update(
        bot=bot,
        update=update
    )


@app.post("/webhook/{token}")
async def other_update(request: Request, token: str):
    data = await request.json()
    update = types.Update.model_validate(data)

    exist = await db.get_bot_by_token(token)
    if not exist:
        return

    try:
        other_bot = Bot(
            token=token,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML
            )
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error creating bot for token {token}: {e}", exc_info=True)
        return

    other_dp = set_dispatcher(exist)
    await other_dp.feed_update(other_bot, update)


@app.post("/webhook/platega")
async def platega_webhook(request: Request):
    headers = request.headers
    merchant_id = headers.get('X-MerchantId')
    secret = headers.get('X-Secret')

    if merchant_id != Config.PLATEGA_MERCHANT or secret != Config.PLATEGA_SECRET:
        return {"status": "error", "message": "Invalid credentials"}

    data = await request.json()
    
    order_id = data.get('id')
    status = data.get('status')
    
    if not order_id or not status:
        return {"status": "error", "message": "Invalid payload"}

    payment_link = await db.get_payment_link(order_id)
    if not payment_link:
        return {"status": "error", "message": "Payment link not found"}

    if payment_link.status == "PAID":
        return {"status": "ok", "message": "Already paid"}

    if status == "CONFIRMED":
        await db.update_payment_link_status(order_id, "PAID")
        
        payload = payment_link.payload
        payment_type = payload.get('type')
        user_id = int(payment_link.user_id)

        # Logic for Balance Top-up
        if payment_type == 'balance':
            amount = payment_link.amount
            user = await db.get_user(user_id=user_id)
            if user:
                await db.update_user(user_id=user.id, balance=user.balance + amount)
                from main_bot.database.types import PaymentMethod
                await db.add_payment(user_id=user.id, amount=amount, method=PaymentMethod.PLATEGA)
                
                try:
                    from main_bot.utils.lang.language import text
                    await bot.send_message(user_id, text('success_payment').format(amount))
                except Exception:
                    pass

        # Logic for Subscription
        elif payment_type == 'subscribe':
            from main_bot.utils.subscribe_service import grant_subscription
            
            chosen = payload.get('chosen')
            total_days = payload.get('total_days')
            service = payload.get('service')
            object_type = payload.get('object_type')
            
            await grant_subscription(user_id, chosen, total_days, service, object_type)
            
            # Referral logic
            referral_id = payload.get('referral_id')
            total_price = payload.get('total_price')
            
            if referral_id:
                ref_user = await db.get_user(referral_id)
                if ref_user:
                    has_purchase = await db.has_purchase(user_id)
                    percent = 15 if has_purchase else 60
                    total_ref_earn = int(total_price / 100 * percent)

                    await db.update_user(
                        user_id=ref_user.id,
                        balance=ref_user.balance + total_ref_earn,
                        referral_earned=ref_user.referral_earned + total_ref_earn
                    )

            try:
                from main_bot.utils.lang.language import text
                await bot.send_message(user_id, text('success_subscribe_pay'))
            except Exception:
                pass

    return {"status": "ok"}


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8099, log_level="warning", access_log=False)
