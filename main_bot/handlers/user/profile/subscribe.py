from datetime import datetime

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from httpx import AsyncClient

from config import Config
from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.handlers.user.menu import profile
from main_bot.handlers.user.profile.profile import show_subscribe
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
import logging

logger = logging.getLogger(__name__)


def get_subscribe_list_resources(objects, object_type, sort_by):
    if not objects:
        return text(f'not_found_{object_type}')

    empty_text = ""
    for obj in objects:
        sub_text = text('subscribe_not_found')

        if object_type == 'bots':
            if obj.subscribe:
                sub_text = text('subscribe_date_note').format(
                    datetime.fromtimestamp(obj.subscribe).strftime(
                        '%d.%m.%Y %H:%M'
                    )
                )
        else:
            sub_value = obj.subscribe
            if sub_value:
                sub_text = text('subscribe_date_note').format(
                    datetime.fromtimestamp(sub_value).strftime(
                        '%d.%m.%Y %H:%M'
                    )
                )

        obj_text = text("resource_title").format(obj.title)
        empty_text += obj_text + sub_text + "\n"

    return empty_text


async def get_pay_info_text(state: FSMContext, user: User) -> str:
    data = await state.get_data()

    total_days = data.get('total_days')
    method = data.get('method')
    total_price = data.get('total_price')

    try:
        async with AsyncClient() as client:
            res = await client.get('https://api.coinbase.com/v2/prices/USD-RUB/spot')
            usd_rate = float(res.json().get('data').get('amount', 100))
    except Exception as e:
        logger.error(f"Error fetching USD rate: {e}")
        usd_rate = 100

    total_price_usd = round(total_price / usd_rate, 2)
    total_price_stars = int(total_price / 1.2)  # Курс: 1 Star = 1.2₽

    total_count_resources = data.get('total_count_resources')
    chosen = data.get('chosen')
    service = data.get('service')
    cor = data.get('cor')

    objects = await cor(
        user_id=user.id,
        limit=10,
        sort_by=service
    )

    # Форматируем список каналов с их названиями
    channels_list = "\n".join(
        f"📺 {obj.title}" for obj in objects
        if obj.id in chosen[:10]
    )

    # Форматируем способ оплаты (если выбран)
    method_text = text("pay:info:method").format(text(f'payment:method:{method}')) if method else ""

    return text('pay:info').format(
        channels_list,           # Список каналов
        total_price,             # Цена в рублях
        total_price_usd,         # Цена в USD
        total_price_stars,       # Цена в звездах
        total_days,              # Длительность
        total_count_resources,   # Количество каналов
        method_text              # Способ оплаты
    )


async def choice(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')
    await call.message.delete()

    if temp[1] == 'cancel':
        # Возврат в меню подписки с информацией о балансе
        return await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML"
        )

    service = "subscribe"
    message_text = text('subscribe_text:{}'.format(temp[1]))

    if temp[1] == 'bots':
        cor = db.get_user_bots
        object_type = 'bots'
    else:
        cor = db.get_user_channels
        object_type = 'channels'

    objects = await cor(
        user_id=user.id,
        limit=10,
        sort_by=service
    )
    await state.update_data(
        service=service,
        object_type=object_type,
        cor=cor,
    )
    await call.message.answer(
        message_text.format(
            get_subscribe_list_resources(
                objects=objects,
                object_type=object_type,
                sort_by=service
            )
        ),
        reply_markup=keyboards.choice_period(
            service=service
        )
    )


async def choice_period(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')

    if temp[1] == 'back':
        await call.message.delete()
        # Возврат в меню подписки с информацией о балансе
        return await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML"
        )

    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    cor = data.get('cor')
    service = data.get('service')
    object_type = data.get('object_type')

    objects = await cor(
        user_id=user.id,
        sort_by=service
    )
    if not objects:
        return await call.answer(
            text(f'not_found_{object_type}'),
            show_alert=True
        )

    await state.update_data(
        tariff_id=int(temp[1]),
        chosen=[]
    )

    await call.message.edit_text(
        text(f'subscribe:chosen:{object_type}').format(
            ""
        ),
        reply_markup=keyboards.choice_object_subscribe(
            resources=objects,
            chosen=[]
        )
    )


async def choice_object_subscribe(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    cor = data.get('cor')
    service = data.get('service')
    object_type = data.get('object_type')
    tariff_id = data.get('tariff_id')
    chosen: list = data.get('chosen')

    if temp[1] == 'cancel':
        objects = await cor(
            user_id=user.id,
            limit=10,
            sort_by=service
        )

        await call.message.delete()
        return await call.message.answer(
            text('subscribe_text:{}'.format(object_type)).format(
                get_subscribe_list_resources(
                    objects=objects,
                    object_type=object_type,
                    sort_by=service
                )
            ),
            reply_markup=keyboards.choice_period(
                service=service
            )
        )

    objects = await cor(
        user_id=user.id,
        sort_by=service
    )

    if temp[1] in ['next', 'back']:
        return await call.message.edit_text(
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
                remover=int(temp[2])
            )
        )

    if temp[1] == 'pay':
        if not chosen:
            return await call.answer(
                text('error_min_choice'),
                show_alert=True
            )

        total_count_resources = len(chosen)
        total_days = Config.TARIFFS.get(service).get(tariff_id).get('period')
        total_price = Config.TARIFFS.get(service).get(tariff_id).get('amount') * total_count_resources

        await state.update_data(
            total_price=total_price,
            total_days=total_days,
            total_count_resources=total_count_resources
        )
        pay_info_text = await get_pay_info_text(state, user)

        await call.message.delete()
        return await call.message.answer(
            pay_info_text,
            reply_markup=keyboards.choice_payment_method(
                data='ChoicePaymentMethodSubscribe',
                is_subscribe=True
            )
        )

    if temp[1] == 'choice_all':
        if len(objects) == len(chosen):
            chosen.clear()
        else:
            chosen.extend(
                [i.id for i in objects
                 if i.id not in chosen]
            )

    if temp[1].isdigit():
        resource_id = int(temp[1])
        if resource_id in chosen:
            chosen.remove(resource_id)
        else:
            chosen.append(resource_id)

    await state.update_data(
        chosen=chosen
    )
    await call.message.edit_text(
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
            remover=int(temp[2])
        )
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Subscribe")
    router.callback_query.register(choice_period, F.data.split("|")[0] == "ChoiceSubscribePeriod")
    router.callback_query.register(choice_object_subscribe, F.data.split("|")[0] == "ChoiceResourceSubscribe")
    return router
