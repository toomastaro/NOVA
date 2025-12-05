from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from datetime import datetime

from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.keyboards import keyboards, InlineExchangeRate
from main_bot.states.user import ExchangeRate
from main_bot.utils.exchange_rates import get_exchange_rates_from_json, format_exchange_rate_from_db
from main_bot.utils.lang.language import text
from main_bot.utils.schedulers import update_exchange_rates_in_db


async def _get_and_format_exchange_rate(user_id: int, state: FSMContext) -> tuple[dict | None, str | None]:
    """
    Helper function to fetch and format exchange rate data.
    Returns tuple of (rate_data, formatted_text)
    """

    user_data = await db.get_user(user_id=user_id)
    user_exchange_rate_id = int(user_data.default_exchange_rate_id)

    all_rates = await db.get_all_exchange_rate()
    if len(all_rates) == 0:
        await update_exchange_rates_in_db()
        all_rates = await db.get_all_exchange_rate()

    if len(all_rates) != 0:
        default_rate = [i for i in all_rates if i.id == user_exchange_rate_id][0]
        last_update = str(default_rate.last_update.strftime("%H:%M %d.%m.%Y"))
        formatted = text("exchange_rate:start_exchange_rate").format(
            default_rate.rate, default_rate.name, last_update
        )

        await state.update_data(all_rates=all_rates, exchange_rate=default_rate)
        return default_rate, formatted
    return None, None


async def start_exchange_rate(message: types.Message, state: FSMContext):
    # Check subscription
    import time
    subscribed_channels = await db.get_subscribe_channels(message.from_user.id)
    has_active_sub = any(ch.subscribe and ch.subscribe > time.time() for ch in subscribed_channels)
    
    if not has_active_sub:
        await message.answer("Эта функция доступна только при наличии хотя бы одной активной оплаченной подписки.")
        return

    await state.set_state(ExchangeRate.input_custom_amount)

    loading_msg = await message.answer(
        "⏳ Fetching exchange rates from multiple sources...",
        parse_mode="HTML",
        reply_markup=InlineExchangeRate.set_exchange_rate()
    )

    default_rate, formatted = await _get_and_format_exchange_rate(
        int(message.from_user.id), state
    )

    if default_rate and formatted:
        await loading_msg.edit_text(
            formatted,
            parse_mode="HTML",
            reply_markup=InlineExchangeRate.set_exchange_rate()
        )


async def settings_of_exchange_rate(call: types.CallbackQuery, state: FSMContext):
    await call.message.delete()
    data = await state.get_data()
    await call.message.answer(
        text=text("exchange_rate:start_exchange_rate:settings"),
        reply_markup=InlineExchangeRate.choose_exchange_rate(data["all_rates"], chosen_exchange_rate_id=data["exchange_rate"].id)
    )


async def choice_of_exchange_resources(call: types.CallbackQuery, state: FSMContext):
    exchange_rate_id = call.data.split("|")[-1]
    data = await state.get_data()

    await db.update_user(
        user_id=int(call.from_user.id),
        return_obj=False,
        default_exchange_rate_id=int(exchange_rate_id)
    )

    await call.message.edit_reply_markup(reply_markup=InlineExchangeRate.choose_exchange_rate(
        data["all_rates"], chosen_exchange_rate_id=int(exchange_rate_id))
    )


async def back_to_start_exchange_rate(call: types.CallbackQuery, state: FSMContext):
    # Check subscription
    import time
    subscribed_channels = await db.get_subscribe_channels(call.from_user.id)
    has_active_sub = any(ch.subscribe and ch.subscribe > time.time() for ch in subscribed_channels)
    
    if not has_active_sub:
        await call.answer("Эта функция доступна только при наличии хотя бы одной активной оплаченной подписки.", show_alert=True)
        return

    await call.message.delete()

    loading_msg = await call.message.answer(
        "⏳ Fetching exchange rates from multiple sources...",
        parse_mode="HTML",
        reply_markup=InlineExchangeRate.set_exchange_rate()
    )

    default_rate, formatted = await _get_and_format_exchange_rate(
        int(call.from_user.id), state
    )

    await loading_msg.edit_text(
        formatted,
        parse_mode="HTML",
        reply_markup=InlineExchangeRate.set_exchange_rate()
    )


async def get_exchange_rate_of_custom_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    exchange_rate = data['exchange_rate'].rate
    amount = message.text
    if amount.replace(".", "").isdigit():
        msg_text = text("exchange_rate:start_exchange_rate:calculate_sum").format(
            float(exchange_rate),
            float(amount),
            float(amount) / float(exchange_rate),
            float(amount),
            float(exchange_rate) * float(amount),
            data['exchange_rate'].last_update.strftime("%H:%M %d.%m.%Y")
        )
        await message.answer(msg_text, reply_markup=keyboards.menu())


def hand_add():
    router = Router()
    router.callback_query.register(back_to_start_exchange_rate,
                                   F.data == "MenuExchangeRate|settings|back")

    router.callback_query.register(choice_of_exchange_resources,
                                    F.data.split("choose_exchange_rate")[0] == "MenuExchangeRate|settings|")

    router.callback_query.register(settings_of_exchange_rate,
                                   F.data == "MenuExchangeRate|settings")

    # Обработчик для кнопки меню "Курс USDT/RUB" - регистрируем ПЕРЕД общим обработчиком текста
    router.message.register(start_exchange_rate, F.text == text('reply_menu:exchange_rate'))

    router.message.register(get_exchange_rate_of_custom_amount, ExchangeRate.input_custom_amount, F.text.regexp(r'^\d+([.,]\d+)?$'))
    
    return router
