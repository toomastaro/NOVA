"""
Обработчики для переноса подписки между каналами.
Позволяет пользователю перенести оплаченные дни подписки с одного канала (донора) на другие.
"""

import time
from datetime import datetime
import logging

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.keyboards.common import Reply
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler(
    "Перенос: меню подписок"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_transfer_sub_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню выбора канала-донора для переноса подписки"""
    user = await db.user.get_user(user_id=call.from_user.id)
    channels = await db.channel.get_user_channels(user_id=user.id)

    if not channels:
        return await call.answer(text("error_subscription_required"), show_alert=True)

    # Фильтруем только активные подписки для отображения
    now = int(time.time())
    active_channels = [ch for ch in channels if ch.subscribe and ch.subscribe > now]

    if not active_channels:
        return await call.answer(text("error_subscription_required"), show_alert=True)

    await state.update_data(transfer_chosen_recipients=[])

    await call.message.answer(
        text("transfer_sub:choose_donor"),
        reply_markup=keyboards.transfer_sub_choose_donor(channels=active_channels),
    )


@safe_handler(
    "Перенос: выбор донора"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choose_donor(call: types.CallbackQuery, state: FSMContext, user: User):
    """Обработчик выбора канала-донора"""

    temp = call.data.split("|")

    if temp[1] == "cancel":
        # Возврат в меню подписки с информацией о балансе
        await call.message.delete()
        await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML",
        )
        # Перезагрузка главного меню
        await call.message.answer("Главное меню", reply_markup=Reply.menu(call.from_user.id))
        return

    # Навигация
    if temp[1] in ["next", "back"]:
        all_channels = await db.channel.get_user_channels(user_id=user.id, sort_by="subscribe")
        # Фильтруем только активные подписки
        now = int(time.time())
        channels = [ch for ch in all_channels if ch.subscribe and ch.subscribe > now]
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.transfer_sub_choose_donor(
                channels=channels, remover=int(temp[2])
            )
        )

    # Выбран канал-донор
    donor_chat_id = int(temp[1])
    donor_channel = await db.channel.get_channel_by_chat_id(chat_id=donor_chat_id)

    if not donor_channel or not donor_channel.subscribe:
        return await call.answer(text("error_transfer_no_days"), show_alert=True)

    # Проверяем, есть ли дни для переноса
    now = int(time.time())
    days_left = max(0, round((donor_channel.subscribe - now) / 86400))

    if days_left <= 0:
        return await call.answer(text("error_transfer_no_days"), show_alert=True)

    # Получаем все каналы пользователя кроме донора
    all_channels = await db.channel.get_user_channels(user_id=user.id)
    recipient_channels = [ch for ch in all_channels if ch.chat_id != donor_chat_id]

    if not recipient_channels:
        return await call.answer(
            "❌ Нет других каналов для переноса подписки", show_alert=True
        )

    # Сохраняем данные в state
    await state.update_data(
        transfer_donor_chat_id=donor_chat_id,
        transfer_donor_title=donor_channel.title,
        transfer_days_available=days_left,
        transfer_chosen_recipients=[],
    )

    await call.message.delete()
    await call.message.answer(
        text("transfer_sub:choose_recipients").format(
            donor_channel.title, days_left, ""
        ),
        reply_markup=keyboards.transfer_sub_choose_recipients(
            channels=recipient_channels, chosen=[]
        ),
    )


@safe_handler(
    "Перенос: выбор получателя"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choose_recipients(call: types.CallbackQuery, state: FSMContext, user: User):
    """Обработчик выбора каналов-получателей"""

    temp = call.data.split("|")
    data = await state.get_data()

    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    donor_chat_id = data.get("transfer_donor_chat_id")
    donor_title = data.get("transfer_donor_title")
    days_available = data.get("transfer_days_available")
    chosen: list = data.get("transfer_chosen_recipients", [])

    # Получаем каналы-получатели (все кроме донора)
    all_channels = await db.channel.get_user_channels(user_id=user.id)
    recipient_channels = [ch for ch in all_channels if ch.chat_id != donor_chat_id]

    if temp[1] == "cancel":
        # Возврат к выбору донора
        channels = await db.channel.get_user_channels(user_id=user.id, sort_by="subscribe")
        await call.message.delete()
        return await call.message.answer(
            text("transfer_sub:choose_donor"),
            reply_markup=keyboards.transfer_sub_choose_donor(channels=channels),
        )

    # Навигация
    if temp[1] in ["next", "back"]:
        chosen_text = (
            "\n".join(
                f"📺 {ch.title}"
                for ch in recipient_channels
                if ch.chat_id in chosen
            )
            if chosen
            else ""
        )

        return await call.message.edit_text(
            text("transfer_sub:choose_recipients").format(
                donor_title, days_available, chosen_text
            ),
            reply_markup=keyboards.transfer_sub_choose_recipients(
                channels=recipient_channels, chosen=chosen, remover=int(temp[2])
            ),
        )

    # Выбрать всё / Отменить всё
    if temp[1] == "choice_all":
        logger.info(
            f"Перенос: нажато выбрать все, сейчас выбрано: {len(chosen)}, всего каналов: {len(recipient_channels)}"
        )
        if len(chosen) == len(recipient_channels):
            chosen.clear()
        else:
            chosen.clear()
            chosen.extend([ch.chat_id for ch in recipient_channels])
        logger.info(f"Перенос: после выбрать все, выбрано: {chosen}")

    # Выбор/отмена выбора канала (может быть отрицательным ID)
    elif temp[1].lstrip("-").isdigit():
        channel_id = int(temp[1])
        logger.info(f"Перенос: нажат канал {channel_id}, сейчас выбрано: {chosen}")
        if channel_id in chosen:
            chosen.remove(channel_id)
            logger.info(f"Перенос: удален {channel_id}")
        else:
            chosen.append(channel_id)
            logger.info(f"Перенос: добавлен {channel_id}")

    # Перенести подписку
    elif temp[1] == "transfer":
        logger.info(f"Перенос: нажата кнопка переноса, выбрано: {chosen}")
        if not chosen:
            logger.warning("Перенос: не выбраны каналы")
            return await call.answer(
                text("error_transfer_min_recipients"), show_alert=True
            )

        logger.info(f"Перенос: выполнение переноса для {len(chosen)} каналов")
        await execute_transfer(call, state, user, chosen)
        return

    # Обновляем state ПЕРЕД обновлением UI
    await state.update_data(transfer_chosen_recipients=chosen)

    chosen_text = (
        "\n".join(
            f"📺 {ch.title}" for ch in recipient_channels if ch.chat_id in chosen
        )
        if chosen
        else ""
    )

    try:
        await call.message.edit_text(
            text("transfer_sub:choose_recipients").format(
                donor_title, days_available, chosen_text
            ),
            reply_markup=keyboards.transfer_sub_choose_recipients(
                channels=recipient_channels, chosen=chosen, remover=int(temp[2])
            ),
        )
    except Exception:
        # Игнорируем ошибку если сообщение не изменилось
        pass


@safe_handler("Перенос: выполнение")
async def execute_transfer(
    call: types.CallbackQuery, state: FSMContext, user: User, chosen: list
):
    """Выполнить перенос подписки с одного канала на другие."""
    data = await state.get_data()

    donor_chat_id = data.get("transfer_donor_chat_id")
    donor_title = data.get("transfer_donor_title")
    days_available = data.get("transfer_days_available")

    # Обнуляем подписку донора (оставляем до конца текущего дня)
    now_dt = datetime.now()
    end_of_today = datetime(now_dt.year, now_dt.month, now_dt.day, 23, 59, 59)
    end_of_today_ts = int(end_of_today.timestamp())

    await db.channel.update_channel_by_chat_id(
        chat_id=donor_chat_id, subscribe=end_of_today_ts
    )

    # Распределяем дни (целое количество дней на каждого получателя)
    days_per_recipient = int(days_available / len(chosen))
    seconds_per_recipient = days_per_recipient * 86400
    now_ts = int(time.time())

    # Получаем каналы-получатели
    recipient_channels = await db.channel.get_user_channels(
        user_id=user.id, from_array=chosen
    )

    recipients_info = []
    for channel in recipient_channels:
        current_sub = channel.subscribe or 0
        new_sub = max(current_sub, now_ts) + seconds_per_recipient

        await db.channel.update_channel_by_chat_id(
            chat_id=channel.chat_id, subscribe=new_sub
        )

        new_date_str = datetime.fromtimestamp(new_sub).strftime("%d.%m.%Y")
        recipients_info.append(
            f"📺 {channel.title} — до {new_date_str} (+{days_per_recipient} дн.)"
        )

    await state.clear()

    # Показываем результат
    donor_date_str = end_of_today.strftime("%d.%m.%Y")
    await call.message.delete()
    await call.message.answer(
        text("transfer_sub:success").format(
            donor_title, donor_date_str, "\n".join(recipients_info)
        ),
        reply_markup=keyboards.subscription_menu(),
    )
    # Перезагрузка главного меню
    await call.message.answer("Главное меню", reply_markup=Reply.menu(call.from_user.id))


def get_router():
    """Регистрация роутеров переноса подписки."""
    router = Router()
    router.callback_query.register(
        choose_donor, F.data.split("|")[0] == "TransferSubDonor"
    )
    router.callback_query.register(
        choose_recipients, F.data.split("|")[0] == "TransferSubRecipients"
    )
    return router
