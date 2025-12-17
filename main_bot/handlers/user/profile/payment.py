"""
Модуль обработки платежей и пополнения баланса.

Поддерживает методы:
- CryptoBot
- Platega (каты)
- Telegram Stars
- Промокоды
"""

import asyncio
import random
import time
import logging

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import LabeledPrice

from main_bot.database.db import db
from main_bot.database.db_types import PaymentMethod
from main_bot.database.user.model import User
from main_bot.handlers.user.profile.balance import show_top_up
from main_bot.handlers.user.profile.profile import show_balance
from main_bot.keyboards import keyboards
from main_bot.states.user import Balance
from main_bot.utils.lang.language import text
from main_bot.utils.payments.crypto_bot import crypto_bot
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


async def safe_delete(message: types.Message):
    """Безопасное удаление сообщения"""
    try:
        await message.delete()
    except Exception:
        pass


@safe_handler("Оплата: выбор метода")
async def choice(call: types.CallbackQuery, state: FSMContext, user: User):
    """Маршрутизатор выбора метода оплаты."""
    temp = call.data.split("|")
    data = await state.get_data()

    if not data:
        await call.answer(text("keys_data_error"))
        await safe_delete(call.message)
        return

    await safe_delete(call.message)

    if temp[1] == "back":
        # Возврат в меню подписки с информацией о балансе
        await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML",
        )
        return

    if temp[1] == "promo":
        await call.message.answer(
            text("input_promo"),
            reply_markup=keyboards.cancel(data="BalanceAmountCancel"),
        )
        return await state.set_state(Balance.input_promo)

    await state.update_data(method=temp[1].upper())
    await call.message.answer(
        text("input_amount"), reply_markup=keyboards.cancel(data="BalanceAmountCancel")
    )
    await state.set_state(Balance.input_amount)


@safe_handler("Оплата: отмена")
async def cancel(call: types.CallbackQuery, state: FSMContext):
    """Отмена ввода суммы."""
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    await safe_delete(call.message)
    await show_top_up(call.message, state)


@safe_handler("Оплата: назад к методам")
async def back_to_method(call: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору способа оплаты с экрана ожидания"""
    try:
        await call.answer()
    except Exception:
        pass

    data = await state.get_data()

    # Отменяем платеж Platega если он был создан
    payment_method = data.get("payment_method")
    payment_order_id = data.get("payment_order_id")

    logger.info(
        f"back_to_method (balance): метод_оплаты={payment_method}, id_заказа_оплаты={payment_order_id}"
    )

    if payment_method == PaymentMethod.PLATEGA and payment_order_id:
        try:
            # Platega не имеет публичного API для отмены, поэтому просто обновляем статус в БД
            await db.payment_link.update_payment_link_status(
                payment_order_id, "CANCELLED"
            )
            msg = f"Платежная ссылка Platega {payment_order_id} помечена как CANCELLED в БД"
            logger.info(msg)
        except Exception as e:
            logger.error(f"Не удалось отменить платежную ссылку Platega: {e}")

    if payment_method == PaymentMethod.CRYPTO_BOT and payment_order_id:
        try:
            invoice_id = int(payment_order_id)
            await crypto_bot.delete_invoice(invoice_id)
            logger.info(f"Отменен счет CryptoBot {invoice_id}")
        except Exception as e:
            logger.error(f"Не удалось отменить счет CryptoBot: {e}")

    # Сбрасываем флаг ожидания оплаты чтобы прервать цикл
    await state.update_data(waiting_payment=False)

    await state.clear()
    await safe_delete(call.message)

    user = await db.user.get_user(user_id=call.from_user.id)
    await call.message.answer(
        text("balance_text").format(user.balance),
        reply_markup=keyboards.subscription_menu(),
        parse_mode="HTML",
    )


@safe_handler("Оплата: ввод промокода")
async def get_promo(message: types.Message, state: FSMContext, user: User):
    """Обработка ввода промокода."""
    name = message.text

    promo = await db.promo.get_promo(name)
    if not promo:
        return await message.answer(
            text("error_promo"),
            reply_markup=keyboards.cancel(data="BalanceAmountCancel"),
        )
    if not promo.amount:
        return await message.answer(
            text("error_type_promo"),
            reply_markup=keyboards.cancel(data="BalanceAmountCancel"),
        )

    await db.promo.use_promo(promo)
    await db.user.update_user(user_id=user.id, balance=user.balance + promo.amount)
    user = await db.user.get_user(user_id=user.id)

    await state.clear()
    await message.answer(text("success_use_balance_promo").format(promo.amount))
    await message.answer(
        text("balance_text").format(user.balance),
        reply_markup=keyboards.subscription_menu(),
        parse_mode="HTML",
    )


@safe_handler("Оплата: ввод суммы")
async def get_amount(message: types.Message, state: FSMContext):
    """Обработка ввода суммы пополнения и создание счета."""
    try:
        amount = int(message.text)
    except ValueError:
        return await message.answer(
            text("error_input"),
            reply_markup=keyboards.cancel(data="BalanceAmountCancel"),
        )
    if amount < 10:
        return await message.answer(
            text("error_min_amount"),
            reply_markup=keyboards.cancel(data="BalanceAmountCancel"),
        )

    data = await state.get_data()
    await state.clear()

    method = data.get("method")
    method_name = text("payment:method:{}".format(method.lower()))
    method = method.upper()

    if method == PaymentMethod.CRYPTO_BOT:
        balance_payload = {
            "user_id": message.from_user.id,
            "type": "balance",
            "amount": amount,
            "method": "CRYPTO_BOT",
        }
        result = await crypto_bot.create_invoice(
            amount=round(amount * 1.03, 2), asset="USDT", payload=balance_payload
        )
        pay_url = result.get("url")
        order_id = result.get("invoice_id")

    elif method == PaymentMethod.PLATEGA:
        from main_bot.utils.payments.platega import platega_api

        # Создаем постоянную платежную ссылку
        payment_link = await db.payment_link.create_payment_link(
            user_id=message.from_user.id, amount=amount, payload={"type": "balance"}
        )

        result = await platega_api.create_invoice(
            order_id=str(payment_link.id),
            amount=amount,
            description="Пополнение баланса NovaTg",
        )
        pay_url = result.get("pay_url")
        order_id = result.get(
            "id"
        )  # Это внутренний ID Platega, но мы отслеживаем по нашему ID переданному выше

    # stars
    else:
        stars_amount = int(amount / 1.2)  # Курс: 1 Star = 1.2₽
        prices = [LabeledPrice(label="XTR", amount=stars_amount)]
        order_id = str(random.randint(1, 999))
        pay_url = await message.bot.create_invoice_link(
            title="Stars NovaTg",
            description="Пополнение баланса",
            prices=prices,
            provider_token="",
            payload=order_id,
            currency="XTR",
        )

    if not pay_url:
        return await message.answer(
            text("payment_method_not_available"),
            reply_markup=keyboards.back(data="BalanceAmountCancel"),
        )

    wait_msg = await message.answer(
        text("wait_payment").format(amount, method_name),
        reply_markup=keyboards.wait_payment(data="cancel_bal_pay", pay_url=pay_url),
    )

    # Устанавливаем флаг что ожидаем оплату и сохраняем данные для отмены
    await state.update_data(
        waiting_payment=True,
        amount=amount,
        payment_order_id=order_id,
        payment_method=method,
    )

    end_time = time.time() + 3600
    while time.time() < end_time:
        # Проверяем не отменил ли пользователь оплату
        current_data = await state.get_data()
        if not current_data.get("waiting_payment"):
            import logging

            logging.getLogger(__name__).info(
                f"Оплата баланса отменена пользователем для метода {method}"
            )
            return

        if method == PaymentMethod.CRYPTO_BOT:
            paid = await crypto_bot.is_paid(order_id)

            if not paid:  # Если НЕ оплачено - ждем
                await asyncio.sleep(5)
                continue

            # Если оплачено - начисляем баланс
            user = await db.user.get_user(user_id=message.from_user.id)
            user = await db.user.update_user(
                user_id=user.id, return_obj=True, balance=user.balance + amount
            )
            await db.payment.add_payment(user_id=user.id, amount=amount, method=method)
            await safe_delete(wait_msg)
            await message.answer(text("success_payment").format(amount))
            await show_balance(message, user)
            return

        if method == PaymentMethod.PLATEGA:
            # Вебхук обрабатывает оплату и зачисление.
            # Мы просто следим за обновлением статуса в БД, чтобы очистить UI.
            payment_link = await db.payment_link.get_payment_link(order_id)
            if payment_link and payment_link.status == "PAID":
                await safe_delete(wait_msg)
                # Сообщение об успехе отправляется вебхуком
                # Просто обновляем вид баланса для пользователя
                user = await db.user.get_user(user_id=message.from_user.id)
                await show_balance(message, user)
                await state.clear()
                return

            await asyncio.sleep(5)
            continue

        if method == PaymentMethod.STARS:
            await state.update_data(
                amount=amount, payment_to="balance", stars_payment=True
            )
            await state.set_state(Balance.pay_stars)
            return


async def process_pre_checkout_query(call: types.PreCheckoutQuery):
    await call.answer(ok=True)


@safe_handler("Оплата: успех")
async def success(message: types.Message, state: FSMContext):
    # ВАЖНО: refund_star_payment убран - он делал возврат денег!
    # Используйте его только для тестирования или реального возврата средств

    data = await state.get_data()

    if not data.get("stars_payment"):
        return
    if data.get("payment_to") != "balance":
        return

    amount = data.get("amount")
    method = PaymentMethod.STARS

    user = await db.user.get_user(user_id=message.from_user.id)
    user = await db.user.update_user(
        user_id=user.id, return_obj=True, balance=user.balance + amount
    )
    await db.payment.add_payment(user_id=user.id, amount=amount, method=method)

    await state.clear()
    await message.answer(text("success_payment").format(amount))
    await show_balance(message, user)


def get_router():
    """Регистрация роутеров платежей."""
    router = Router()
    router.callback_query.register(
        choice, F.data.split("|")[0] == "ChoicePaymentMethod"
    )
    router.callback_query.register(
        cancel, F.data.split("|")[0] == "BalanceAmountCancel"
    )
    router.callback_query.register(back_to_method, lambda c: c.data == "cancel_bal_pay")
    router.message.register(get_promo, Balance.input_promo, F.text)
    router.message.register(get_amount, Balance.input_amount, F.text)
    router.pre_checkout_query.register(process_pre_checkout_query)
    router.message.register(success, Balance.pay_stars, F.successful_payment)
    return router
