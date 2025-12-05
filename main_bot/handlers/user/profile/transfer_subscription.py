"""
Обработчики для переноса подписки между каналами
"""
import time
from datetime import datetime

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text


async def show_transfer_sub_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню выбора канала-донора для переноса подписки"""
    user = await db.get_user(user_id=call.from_user.id)
    all_channels = await db.get_subscribe_channels(user_id=user.id)
    
    # Фильтруем только активные подписки (не истекшие)
    now = int(time.time())
    channels = [
        ch for ch in all_channels 
        if ch.subscribe and ch.subscribe > now
    ]
    
    if not channels:
        return await call.answer(
            text("error_transfer_no_channels"),
            show_alert=True
        )
    
    await state.update_data(
        transfer_chosen_recipients=[]
    )
    
    await call.message.answer(
        text("transfer_sub:choose_donor"),
        reply_markup=keyboards.transfer_sub_choose_donor(
            channels=channels
        )
    )


async def choose_donor(call: types.CallbackQuery, state: FSMContext, user: User):
    """Обработчик выбора канала-донора"""
    temp = call.data.split('|')
    
    if temp[1] == 'cancel':
        # Возврат в меню подписки с информацией о балансе
        from main_bot.utils.lang.language import text
        
        await call.message.delete()
        return await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML"
        )
    
    # Навигация
    if temp[1] in ['next', 'back']:
        all_channels = await db.get_subscribe_channels(user_id=user.id)
        # Фильтруем только активные подписки
        now = int(time.time())
        channels = [
            ch for ch in all_channels 
            if ch.subscribe and ch.subscribe > now
        ]
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.transfer_sub_choose_donor(
                channels=channels,
                remover=int(temp[2])
            )
        )
    
    # Выбран канал-донор
    donor_chat_id = int(temp[1])
    donor_channel = await db.get_channel_by_chat_id(chat_id=donor_chat_id)
    
    if not donor_channel or not donor_channel.subscribe:
        return await call.answer(
            text("error_transfer_no_days"),
            show_alert=True
        )
    
    # Проверяем, есть ли дни для переноса
    now = int(time.time())
    days_left = max(0, round((donor_channel.subscribe - now) / 86400))
    
    if days_left <= 0:
        return await call.answer(
            text("error_transfer_no_days"),
            show_alert=True
        )
    
    # Получаем все каналы пользователя кроме донора
    all_channels = await db.get_user_channels(user_id=user.id)
    recipient_channels = [ch for ch in all_channels if ch.chat_id != donor_chat_id]
    
    if not recipient_channels:
        return await call.answer(
            "❌ Нет других каналов для переноса подписки",
            show_alert=True
        )
    
    # Сохраняем данные в state
    await state.update_data(
        transfer_donor_chat_id=donor_chat_id,
        transfer_donor_title=donor_channel.title,
        transfer_days_available=days_left,
        transfer_chosen_recipients=[]
    )
    
    await call.message.delete()
    await call.message.answer(
        text("transfer_sub:choose_recipients").format(
            donor_channel.title,
            days_left,
            ""
        ),
        reply_markup=keyboards.transfer_sub_choose_recipients(
            channels=recipient_channels,
            chosen=[]
        )
    )


async def choose_recipients(call: types.CallbackQuery, state: FSMContext, user: User):
    """Обработчик выбора каналов-получателей"""
    temp = call.data.split('|')
    data = await state.get_data()
    
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()
    
    donor_chat_id = data.get('transfer_donor_chat_id')
    donor_title = data.get('transfer_donor_title')
    days_available = data.get('transfer_days_available')
    chosen: list = data.get('transfer_chosen_recipients', [])
    
    # Получаем каналы-получатели (все кроме донора)
    all_channels = await db.get_user_channels(user_id=user.id)
    recipient_channels = [ch for ch in all_channels if ch.chat_id != donor_chat_id]
    
    if temp[1] == 'cancel':
        # Возврат к выбору донора
        channels = await db.get_subscribe_channels(user_id=user.id)
        await call.message.delete()
        return await call.message.answer(
            text("transfer_sub:choose_donor"),
            reply_markup=keyboards.transfer_sub_choose_donor(
                channels=channels
            )
        )
    
    # Навигация
    if temp[1] in ['next', 'back']:
        chosen_text = "\n".join(
            f"📺 {ch.title}" for ch in recipient_channels
            if ch.chat_id in chosen[:10]
        ) if chosen else ""
        
        return await call.message.edit_text(
            text("transfer_sub:choose_recipients").format(
                donor_title,
                days_available,
                chosen_text
            ),
            reply_markup=keyboards.transfer_sub_choose_recipients(
                channels=recipient_channels,
                chosen=chosen,
                remover=int(temp[2])
            )
        )
    
    # Выбрать всё / Отменить всё
    if temp[1] == 'choice_all':
        if len(chosen) == len(recipient_channels):
            chosen.clear()
        else:
            chosen = [ch.chat_id for ch in recipient_channels]
    
    # Выбор/отмена выбора канала
    elif temp[1].isdigit():
        channel_id = int(temp[1])
        if channel_id in chosen:
            chosen.remove(channel_id)
        else:
            chosen.append(channel_id)
    
    # Перенести подписку
    elif temp[1] == 'transfer':
        if not chosen:
            return await call.answer(
                text("error_transfer_min_recipients"),
                show_alert=True
            )
        
        await execute_transfer(call, state, user, chosen)
        return
    
    # Обновляем state и клавиатуру
    await state.update_data(
        transfer_chosen_recipients=chosen
    )
    
    chosen_text = "\n".join(
        f"📺 {ch.title}" for ch in recipient_channels
        if ch.chat_id in chosen[:10]
    ) if chosen else ""
    
    await call.message.edit_text(
        text("transfer_sub:choose_recipients").format(
            donor_title,
            days_available,
            chosen_text
        ),
        reply_markup=keyboards.transfer_sub_choose_recipients(
            channels=recipient_channels,
            chosen=chosen,
            remover=int(temp[2])
        )
    )


async def execute_transfer(call: types.CallbackQuery, state: FSMContext, user: User, chosen: list):
    """Выполнить перенос подписки"""
    data = await state.get_data()
    
    donor_chat_id = data.get('transfer_donor_chat_id')
    donor_title = data.get('transfer_donor_title')
    days_available = data.get('transfer_days_available')
    
    # Получаем канал-донор
    donor_channel = await db.get_channel_by_chat_id(chat_id=donor_chat_id)
    
    # Вычисляем конец сегодняшнего дня (23:59:59)
    now = datetime.now()
    end_of_today = datetime(now.year, now.month, now.day, 23, 59, 59)
    end_of_today_timestamp = int(end_of_today.timestamp())
    
    # Обнуляем подписку донора до конца сегодняшнего дня
    await db.update_channel_by_chat_id(
        chat_id=donor_chat_id,
        subscribe=end_of_today_timestamp
    )
    
    # Распределяем дни между получателями
    days_per_recipient = days_available // len(chosen)
    seconds_per_recipient = days_per_recipient * 86400
    
    # Получаем каналы-получатели
    recipient_channels = await db.get_user_channels(
        user_id=user.id,
        from_array=chosen
    )
    
    recipients_info = []
    for channel in recipient_channels:
        # Добавляем дни к текущей подписке или создаем новую
        if channel.subscribe and channel.subscribe > int(time.time()):
            new_subscribe = channel.subscribe + seconds_per_recipient
        else:
            new_subscribe = int(time.time()) + seconds_per_recipient
        
        await db.update_channel_by_chat_id(
            chat_id=channel.chat_id,
            subscribe=new_subscribe
        )
        
        # Форматируем дату для отображения
        new_date = datetime.fromtimestamp(new_subscribe).strftime('%d.%m.%Y')
        recipients_info.append(f"📺 {channel.title} — подписка до {new_date} (+{days_per_recipient} дн.)")
    
    # Форматируем дату донора
    donor_date = end_of_today.strftime('%d.%m.%Y')
    
    # Очищаем state
    await state.clear()
    
    # Показываем результат
    await call.message.delete()
    await call.message.answer(
        text("transfer_sub:success").format(
            donor_title,
            donor_date,
            "\n".join(recipients_info)
        ),
        reply_markup=keyboards.subscription_menu()
    )


def hand_add():
    """Регистрация обработчиков"""
    router = Router()
    router.callback_query.register(choose_donor, F.data.split("|")[0] == "TransferSubDonor")
    router.callback_query.register(choose_recipients, F.data.split("|")[0] == "TransferSubRecipients")
    return router
