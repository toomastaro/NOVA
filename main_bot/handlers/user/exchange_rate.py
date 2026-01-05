"""
Обработчики функционала курса валют.

Модуль предоставляет:
- Просмотр актуального курса USDT/RUB
- Расчет сумм по курсу
- Выбор источника курса
- Доступно только при наличии активной подписки
"""

import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import InlineExchangeRate
from main_bot.keyboards.common import Reply
from main_bot.states.user import ExchangeRate
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler
from main_bot.utils.schedulers.extra import update_exchange_rates_in_db
from main_bot.utils.report_signature import get_report_signatures

logger = logging.getLogger(__name__)


async def _check_active_subscription(user_id: int) -> bool:
    """
    Проверяет наличие активной подписки у пользователя.
    """
    return await db.channel.has_active_subscription(user_id)


def serialize_rate(rate: Any) -> Optional[Dict[str, Any]]:
    """
    Сериализует объект курса валюты в словарь.

    Аргументы:
        rate (Any): Объект курса валюты из БД.

    Возвращает:
        Optional[Dict[str, Any]]: Словарь с данными курса или None.
    """
    if not rate:
        return None
    return {
        "id": rate.id,
        "name": rate.name,
        "rate": rate.rate,
        "last_update": rate.last_update.isoformat() if rate.last_update else None,
    }


async def _get_and_format_exchange_rate(
    user_id: int, state: FSMContext
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Получает и форматирует данные курса валюты.

    Аргументы:
        user_id (int): Telegram ID пользователя.
        state (FSMContext): Контекст состояния.

    Возвращает:
        Tuple[Optional[Any], Optional[str]]: Объект курса и отформатированная строка.
    """

    user_data = await db.user.get_user(user_id=user_id)
    user_exchange_rate_id = int(user_data.default_exchange_rate_id)

    all_rates = await db.exchange_rate.get_all_exchange_rate()
    if len(all_rates) == 0:
        await update_exchange_rates_in_db()
        all_rates = await db.exchange_rate.get_all_exchange_rate()

    if all_rates:
        # Пытаемся найти тариф пользователя, иначе берем первый
        default_rate = next(
            (i for i in all_rates if i.id == user_exchange_rate_id),
            all_rates[0]
        )
        last_update = str(default_rate.last_update.strftime("%H:%M %d.%m.%Y"))
        formatted = text("exchange_rate:start_exchange_rate").format(
            default_rate.rate, default_rate.name, last_update
        )

        await state.update_data(
            all_rates=[serialize_rate(r) for r in all_rates],
            exchange_rate=serialize_rate(default_rate),
        )
        return default_rate, formatted
    return None, None


@safe_handler(
    "Курс валют: главное меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def start_exchange_rate(message: types.Message, state: FSMContext) -> None:
    """
    Отображает главное меню курса валют с возможностью расчета.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    has_active_sub = await _check_active_subscription(message.from_user.id)

    if not has_active_sub:
        await message.answer(text("exchange_rate:no_subscription"))
        return

    await state.set_state(ExchangeRate.input_custom_amount)

    loading_msg = await message.answer(
        text("exchange_rate:loading"),
        parse_mode="HTML",
        reply_markup=InlineExchangeRate.set_exchange_rate(),
    )

    # Удаляем сообщение пользователя ("📈 Курс USDT"), чтобы оно не спамило в чате
    try:
        await message.delete()
    except Exception:
        pass

    default_rate, formatted = await _get_and_format_exchange_rate(
        int(message.from_user.id), state
    )

    if default_rate and formatted:
        await loading_msg.edit_text(
            formatted,
            parse_mode="HTML",
            reply_markup=InlineExchangeRate.set_exchange_rate(),
        )


@safe_handler(
    "Курс валют: настройки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def settings_of_exchange_rate(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Отображает настройки выбора источника курса.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await call.message.delete()
    data = await state.get_data()
    await call.message.answer(
        text=text("exchange_rate:start_exchange_rate:settings"),
        reply_markup=InlineExchangeRate.choose_exchange_rate(
            data["all_rates"], chosen_exchange_rate_id=data["exchange_rate"]["id"]
        ),
    )


@safe_handler(
    "Курс валют: выбор ресурса"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_of_exchange_resources(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Обрабатывает выбор источника курса валюты.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    exchange_rate_id = call.data.split("|")[-1]
    data = await state.get_data()

    await db.user.update_user(
        user_id=int(call.from_user.id),
        return_obj=False,
        default_exchange_rate_id=int(exchange_rate_id),
    )

    await call.message.edit_reply_markup(
        reply_markup=InlineExchangeRate.choose_exchange_rate(
            data["all_rates"], chosen_exchange_rate_id=int(exchange_rate_id)
        )
    )


@safe_handler(
    "Курс валют: возврат"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_to_start_exchange_rate(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Возврат к главному экрану курса валют.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    has_active_sub = await _check_active_subscription(call.from_user.id)

    if not has_active_sub:
        await call.answer(
            text("exchange_rate:no_subscription"),
            show_alert=True,
        )
        return

    await call.message.delete()

    loading_msg = await call.message.answer(
        text("exchange_rate:loading"),
        parse_mode="HTML",
        reply_markup=InlineExchangeRate.set_exchange_rate(),
    )

    default_rate, formatted = await _get_and_format_exchange_rate(
        int(call.from_user.id), state
    )

    await loading_msg.edit_text(
        formatted,
        parse_mode="HTML",
        reply_markup=InlineExchangeRate.set_exchange_rate(),
    )


@safe_handler(
    "Курс валют: расчет суммы"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def get_exchange_rate_of_custom_amount(
    message: types.Message, state: FSMContext
) -> None:
    """
    Рассчитывает сумму по введенному количеству валюты.

    Аргументы:
        message (types.Message): Сообщение с суммой.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    exchange_rate = data["exchange_rate"]["rate"]
    amount = message.text
    if amount.replace(".", "").isdigit():
        last_update_str = data["exchange_rate"]["last_update"]
        last_update_dt = (
            datetime.fromisoformat(last_update_str)
            if last_update_str
            else datetime.now()
        )

        msg_text = text("exchange_rate:start_exchange_rate:calculate_sum").format(
            float(exchange_rate),
            float(amount),
            float(amount) / float(exchange_rate),
            float(amount),
            float(exchange_rate) * float(amount),
            last_update_dt.strftime("%H:%M %d.%m.%Y"),
        )

        user_id = message.from_user.id
        user = await db.user.get_user(user_id)

        msg_text += await get_report_signatures(user, "exchange", message.bot)

        await message.answer(
            msg_text,
            reply_markup=Reply.menu(),
            parse_mode="HTML",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )


@safe_handler(
    "Курс валют: выход"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_to_main_menu(call: types.CallbackQuery) -> None:
    """
    Возврат в главное меню.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    await call.message.delete()
    await call.message.answer("Главное меню", reply_markup=Reply.menu())


def get_router() -> Router:
    """
    Создает роутер для обработки курса валют.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()

    router.callback_query.register(back_to_main_menu, F.data == "MenuExchangeRate|back")

    router.callback_query.register(
        back_to_start_exchange_rate, F.data == "MenuExchangeRate|settings|back"
    )

    router.callback_query.register(
        choice_of_exchange_resources,
        F.data.split("choose_exchange_rate")[0] == "MenuExchangeRate|settings|",
    )

    router.callback_query.register(
        settings_of_exchange_rate, F.data == "MenuExchangeRate|settings"
    )

    # Обработчик для кнопки меню "Курс USDT/RUB" - регистрируем ПЕРЕД общим обработчиком текста
    router.message.register(
        start_exchange_rate, F.text == text("reply_menu:exchange_rate")
    )

    router.message.register(
        get_exchange_rate_of_custom_amount,
        ExchangeRate.input_custom_amount,
        F.text.regexp(r"^\d+([.,]\d+)?$"),
    )

    return router
