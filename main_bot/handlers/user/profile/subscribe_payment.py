import asyncio
import random
import time

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import LabeledPrice

from main_bot.database.db import db
from main_bot.database.types import PaymentMethod
from main_bot.database.user.model import User
from main_bot.handlers.user.menu import profile
from main_bot.handlers.user.profile.subscribe import get_pay_info_text
from main_bot.keyboards import keyboards
from main_bot.states.user import Subscribe
from main_bot.utils.lang.language import text
from main_bot.utils.payments.crypto_bot import crypto_bot


async def give_subscribes(state: FSMContext, user: User):
    data = await state.get_data()

    cor = data.get('cor')
    service = data.get('service')
    object_type = data.get('object_type')
    chosen: list = data.get('chosen')
    total_days: int = data.get('total_days')
    total_price: int = data.get('total_price')
    promo_name: str = data.get('promo_name')

    # database method in state / crud
    objects = await cor(
        user_id=user.id,
        sort_by=service
    )
    chosen_objects = [
        i for i in objects
        if i.id in chosen
    ]

    added_time = 86400 * total_days
    for chosen_object in chosen_objects:
        if object_type == 'channels':
            channel = await db.get_channel_by_row_id(
                row_id=chosen_object.id
            )
            subscribe_value = channel.subscribe

            if not subscribe_value:
                subscribe_value = added_time + int(time.time())
            else:
                subscribe_value += added_time

            await db.update_channel_by_chat_id(
                chat_id=channel.chat_id,
                **{"subscribe": subscribe_value}
            )
        else:
            user_bot = await db.get_bot_by_id(
                row_id=chosen_object.id
            )
            subscribe_value = user_bot.subscribe

            if not subscribe_value:
                subscribe_value = added_time + int(time.time())
            else:
                subscribe_value += added_time

            await db.update_bot_by_id(
                row_id=user_bot.id,
                subscribe=subscribe_value
            )

    if promo_name:
        promo = await db.get_promo(promo_name)
        await db.use_promo(promo)

    if user.referral_id:
        ref_user = await db.get_user(user.referral_id)
        if not ref_user:
            return

        has_purchase = await db.has_purchase(user.id)
        percent = 15 if has_purchase else 60
        total_ref_earn = int(total_price / 100 * percent)

        await db.update_user(
            user_id=ref_user.id,
            balance=ref_user.balance + total_ref_earn,
            referral_earned=ref_user.referral_earned + total_ref_earn
        )


async def choice(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')
    data = await state.get_data()

    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == 'back':
        cor = data.get('cor')
        service = data.get('service')
        object_type = data.get('object_type')
        chosen: list = data.get('chosen')

        objects = await cor(
            user_id=user.id,
            sort_by=service
        )
        await call.message.delete()
        return await call.message.answer(
            text(f'subscribe:chosen:{object_type}').format(
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.id in chosen[:10]
                )
            ),
            reply_markup=keyboards.choice_object_subscribe(
                resources=objects,
                chosen=chosen,
            )
        )

    if temp[1] == 'promo':
        input_message = await call.message.answer(
            text('input_promo'),
            reply_markup=keyboards.cancel(
                data='SubscribePromoCancel'
            )
        )
        await call.answer()

        await state.update_data(
            message_id=call.message.message_id,
            input_message_id=input_message.message_id
        )

        return await state.set_state(Subscribe.input_promo)

    if temp[1] == 'balance':
        total_price = data.get('total_price')
        if user.balance < total_price:
            return await call.answer(
                text('error_balance'),
                show_alert=True
            )

        await db.update_user(
            user_id=user.id,
            balance=user.balance - total_price
        )
        await give_subscribes(state, user)

        await state.clear()
        await call.message.delete()
        await call.message.answer(
            text('success_subscribe_pay')
        )

        return await profile(call.message)

    method = temp[1]
    total_price = data.get('total_price')
    await state.update_data(
        method=method
    )
    method = method.upper()

    if method == PaymentMethod.CRYPTO_BOT:
        result = await crypto_bot.create_invoice(
            amount=round(total_price * 1.03, 2),
            asset='USDT'
        )
        pay_url = result.get('url')
        order_id = result.get('invoice_id')

    # stars
    else:
        stars_amount = int(total_price / 1.2)  # Курс: 1 Star = 1.2₽
        prices = [LabeledPrice(label="XTR", amount=stars_amount)]
        order_id = str(random.randint(1, 999))
        pay_url = await call.bot.create_invoice_link(
            title='Stars NovaTg',
            description='Пополнение баланса',
            prices=prices,
            provider_token='',
            payload=order_id,
            currency='XTR'
        )

    if not pay_url:
        return await call.answer(
            text('payment_method_not_available'),
            show_alert=True
        )

    pay_info_text = await get_pay_info_text(state, user)
    await call.message.edit_text(
        pay_info_text,
        reply_markup=keyboards.wait_payment(
            data="WaitSubscribePaymentBack",
            pay_url=pay_url
        )
    )

    end_time = time.time() + 3600
    while time.time() < end_time:
        if method == PaymentMethod.CRYPTO_BOT:
            paid = await crypto_bot.is_paid(order_id)

            if not paid:  # Если НЕ оплачено - ждем
                await asyncio.sleep(5)
                continue

        if method == PaymentMethod.STARS:
            await state.update_data(
                payment_to='subscribe',
                stars_payment=True
            )
            await state.set_state(Subscribe.pay_stars)
            return

        # Если оплачено - начисляем подписку
        await give_subscribes(state, user)

        await state.clear()
        await call.message.delete()
        await call.message.answer(
            text('success_subscribe_pay')
        )
        await profile(call.message)
        return


async def align_subscribe(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split("|")
    data = await state.get_data()

    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    align_chosen: list = data.get("align_chosen")
    all_sub_objects = await db.get_subscribe_channels(
        user_id=user.id
    )
    
    # Фильтруем только активные подписки
    import time
    now = int(time.time())
    sub_objects = [
        ch for ch in all_sub_objects 
        if ch.subscribe and ch.subscribe > now
    ]

    if temp[1] in ["next", "back"]:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.align_sub(
                sub_objects=sub_objects,
                chosen=align_chosen,
                remover=int(temp[2])
            )
        )

    if temp[1] == "cancel":
        return await back_to_method(call, state)

    if temp[1] == "align":
        chosen_objects = await db.get_user_channels(
            user_id=user.id,
            from_array=align_chosen
        )

        now = int(time.time())
        total_remain_days = sum(
            [
                round((i.subscribe - now) / 86400)
                for i in chosen_objects
                if (i.subscribe - now) > 86400
            ]
        )

        days_per_object = (total_remain_days / len(chosen_objects))
        if not total_remain_days or days_per_object < 1:
            return await call.answer(
                text("error_align_not_have_days")
            )

        for chosen_object in chosen_objects:
            await db.update_channel_by_chat_id(
                chat_id=chosen_object.chat_id,
                subscribe=days_per_object * 86400 + int(time.time())
            )

        await call.answer(
            text("success_align").format(
                len(chosen_objects)
            ),
            show_alert=True
        )
        return await back_to_method(call, state)

    if temp[1] == "choice_all":
        if len(align_chosen) == len(sub_objects):
            align_chosen.clear()
        else:
            objects_ids = [i.chat_id for i in sub_objects]
            align_chosen.extend(objects_ids)

    if temp[1].isdigit():
        resource_id = int(temp[1])
        if resource_id in align_chosen:
            align_chosen.remove(resource_id)
        else:
            align_chosen.append(resource_id)

    await state.update_data(
        align_chosen=align_chosen
    )
    await call.message.edit_reply_markup(
        reply_markup=keyboards.align_sub(
            sub_objects=sub_objects,
            chosen=align_chosen,
            remover=int(temp[2])
        )
    )


async def cancel(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    await call.message.delete()


async def back_to_method(call: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору способа оплаты с экрана ожидания"""
    user = await db.get_user(user_id=call.from_user.id)
    data = await state.get_data()
    
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    await state.update_data(method=None)
    pay_info_text = await get_pay_info_text(state, user)
    
    await call.message.edit_text(
        pay_info_text,
        reply_markup=keyboards.choice_payment_method(
            data='ChoicePaymentMethodSubscribe',
            is_subscribe=True,
            has_promo=data.get('has_promo')
        )
    )




async def get_promo(message: types.Message, state: FSMContext, user: User):
    data = await state.get_data()

    try:
        await message.bot.delete_message(
            message.chat.id,
            data.get('input_message_id')
        )
    except Exception as e:
        print(e)

    name = message.text
    promo = await db.get_promo(name)

    if not promo:
        return await message.answer(
            text('error_promo'),
            reply_markup=keyboards.cancel(
                data='SubscribePromoCancel'
            )
        )

    if not promo.discount:
        return await message.answer(
            text('error_type_promo'),
            reply_markup=keyboards.cancel(
                data='SubscribePromoCancel'
            )
        )

    old_total_price = data.get('total_price')
    total_price = old_total_price - int(old_total_price / 100 * promo.discount)
    message_id = data.get('message_id')

    try:
        await message.bot.delete_message(
            message.chat.id,
            message_id
        )
    except Exception as e:
        print(e)

    await state.update_data(
        old_total_price=old_total_price,
        total_price=total_price,
        has_promo=True,
        promo_name=promo.name
    )
    data = await state.get_data()
    pay_info_text = await get_pay_info_text(state, user)

    await state.clear()
    await state.update_data(data)

    await message.answer(
        text('success_use_discount_promo').format(
            promo.discount
        )
    )
    await message.answer(
        pay_info_text,
        reply_markup=keyboards.choice_payment_method(
            data='ChoicePaymentMethodSubscribe',
            is_subscribe=True,
            has_promo=True
        )
    )


async def success(message: types.Message, state: FSMContext, user: User):
    # ВАЖНО: refund_star_payment убран - он делал возврат денег!
    # Используйте его только для тестирования или реального возврата средств

    data = await state.get_data()

    if not data.get('stars_payment'):
        return
    if data.get('payment_to') != 'subscribe':
        return

    await give_subscribes(state, user)

    await state.clear()
    await message.delete()
    await message.answer(
        text('success_subscribe_pay')
    )
    await profile(message)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoicePaymentMethodSubscribe")
    router.callback_query.register(align_subscribe, F.data.split("|")[0] == "ChoiceResourceAlignSubscribe")
    router.callback_query.register(cancel, F.data.split("|")[0] == "SubscribePromoCancel")
    router.callback_query.register(back_to_method, F.data.split("|")[0] == "WaitSubscribePaymentBack")
    router.message.register(get_promo, Subscribe.input_promo, F.text)
    router.message.register(success, Subscribe.pay_stars, F.successful_payment)
    return router
