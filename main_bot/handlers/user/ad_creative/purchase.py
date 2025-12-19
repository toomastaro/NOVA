"""
Модуль обработки покупки рекламы.
Управляет созданием закупов, маппингом ссылок и сбором статистики.

Модуль включает:
- Создание закупов (выбор типа оплаты, цены)
- Маппинг ссылок (привязка к каналам или внешним ресурсам)
- Генерацию Excel-отчетов
- Генерацию готовых постов с трекинговыми ссылками
- Статистику по закупам
"""

import copy
import logging
import re
import time
from datetime import datetime
from io import BytesIO


from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from openpyxl import Workbook

from main_bot.database.db import db
from main_bot.database.db_types import AdPricingType, AdTargetType
from main_bot.keyboards import InlineAdPurchase
from main_bot.states.user import AdPurchaseStates
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

router = Router(name="AdPurchase")


@router.callback_query(F.data.startswith("AdPurchase|create|"))
@safe_handler(
    "Закуп: старт создания"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def create_purchase_start(call: CallbackQuery, state: FSMContext) -> None:
    """
    Начало создания закупа.
    Инициализирует процесс выбора типа оплаты.

    Аргументы:
        call (CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    creative_id = int(call.data.split("|")[2])
    await state.update_data(creative_id=creative_id)

    await call.message.edit_text(
        "Выберите тип оплаты:", reply_markup=InlineAdPurchase.pricing_type_menu()
    )
    await state.set_state(AdPurchaseStates.waiting_for_pricing_type)


@router.callback_query(F.data.startswith("AdPurchase|pricing|"))
@safe_handler(
    "Закуп: выбор типа оплаты"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def process_pricing_type(call: CallbackQuery, state: FSMContext) -> None:
    """
    Обработка выбора типа оплаты.

    Аргументы:
        call (CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    pricing_type_str = call.data.split("|")[2]
    # Валидация enum
    try:
        pricing_type = AdPricingType(pricing_type_str)
    except ValueError:
        await call.answer("Ошибка типа оплаты")
        return

    await state.update_data(pricing_type=pricing_type)

    await call.message.edit_text(
        "Введите ставку (целое число, рубли):", reply_markup=None
    )
    await state.set_state(AdPurchaseStates.waiting_for_price)


@router.message(AdPurchaseStates.waiting_for_price)
@safe_handler(
    "Закуп: ввод цены"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def process_price(message: Message, state: FSMContext) -> None:
    """
    Обработка ввода цены.

    Аргументы:
        message (Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    try:
        price = int(message.text.strip())
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное целое число.")
        return

    await state.update_data(price_value=price)
    await message.answer("Введите комментарий к закупу (условия, канал и т.д.):")
    await state.set_state(AdPurchaseStates.waiting_for_comment)


@router.message(AdPurchaseStates.waiting_for_comment)
@safe_handler(
    "Закуп: обработка комментария"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def process_comment(message: Message, state: FSMContext) -> None:
    """
    Обработка комментария и создание закупа.
    После создания переходит к процессу маппинга ссылок.

    Аргументы:
        message (Message): Сообщение с комментарием.
        state (FSMContext): Контекст состояния.
    """
    comment = message.text.strip()
    data = await state.get_data()

    # Создание закупа
    purchase_id = await db.ad_purchase.create_purchase(
        owner_id=message.from_user.id,
        creative_id=data["creative_id"],
        pricing_type=data["pricing_type"],
        price_value=data["price_value"],
        comment=comment,
    )

    await message.answer(f"Закуп #{purchase_id} создан! Переходим к мапингу ссылок...")

    # Запуск логики маппинга
    await start_mapping(message, purchase_id, data["creative_id"])
    await state.clear()


@safe_handler(
    "Закуп: старт маппинга"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def start_mapping(message: Message, purchase_id: int, creative_id: int) -> None:
    """
    Начало процесса маппинга ссылок.
    Создает начальные записи маппинга для всех слотов креатива, если они еще не существуют.

    Аргументы:
        message (Message): Сообщение для ответа.
        purchase_id (int): ID закупа.
        creative_id (int): ID креатива.
    """
    slots = await db.ad_creative.get_slots(creative_id)

    # Автоопределение
    for slot in slots:
        # Проверка существования маппинга
        existing_mappings = await db.ad_purchase.get_link_mappings(purchase_id)
        existing_slot_ids = [m.slot_id for m in existing_mappings]

        if slot.id in existing_slot_ids:
            continue

        target_type = AdTargetType.EXTERNAL
        target_channel_id = None
        track_enabled = False

        # 1. Проверка t.me/username - обрабатывается позже или вручную
        # 2. Проверка invite link - обрабатывается позже или вручную

        await db.ad_purchase.upsert_link_mapping(
            ad_purchase_id=purchase_id,
            slot_id=slot.id,
            original_url=slot.original_url,
            target_type=target_type,
            target_channel_id=target_channel_id,
            track_enabled=track_enabled,
        )

    await show_mapping_menu(message, purchase_id)


@safe_handler(
    "Закуп: меню маппинга"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_mapping_menu(message: Message, purchase_id: int) -> None:
    """
    Отображение меню маппинга ссылок.
    Показывает список ссылок и их статус (привязан/не привязан).

    Аргументы:
        message (Message): Сообщение для ответа.
        purchase_id (int): ID закупа.
    """
    mappings = await db.ad_purchase.get_link_mappings(purchase_id)
    user_channels = await db.channel.get_user_channels(message.chat.id)
    channels_map = {ch.chat_id: ch.title for ch in user_channels}

    links_data = []
    for m in mappings:
        status_text = "❌ Без трекинга"
        if m.target_type == AdTargetType.CHANNEL and m.target_channel_id:
            status_text = channels_map.get(m.target_channel_id, "Неизвестный канал")
        elif m.target_type == AdTargetType.EXTERNAL:
            status_text = "❌ Без трекинга"

        links_data.append(
            {
                "slot_id": m.slot_id,
                "original_url": (
                    m.original_url[:30] + "..."
                    if len(m.original_url) > 30
                    else m.original_url
                ),
                "status_text": status_text,
            }
        )

    await message.answer(
        f"В креативе найдено {len(mappings)} ссылок. Привяжите каждую ссылку к каналу или отключите трекинг.",
        reply_markup=InlineAdPurchase.mapping_menu(purchase_id, links_data),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("AdPurchase|map_link|"))
@safe_handler(
    "Закуп: редактирование маппинга"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def edit_link_mapping(call: CallbackQuery) -> None:
    """
    Редактирование привязки конкретной ссылки.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    _, _, purchase_id, slot_id = call.data.split("|")
    purchase_id = int(purchase_id)
    slot_id = int(slot_id)

    await call.message.edit_text(
        "Выберите действие для этой ссылки:",
        reply_markup=InlineAdPurchase.link_actions_menu(purchase_id, slot_id),
    )


@router.callback_query(F.data.startswith("AdPurchase|select_channel_list|"))
@safe_handler(
    "Закуп: выбор канала"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_channel_list(call: CallbackQuery) -> None:
    """
    Показ списка каналов пользователя для выбора привязки.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    _, _, purchase_id, slot_id = call.data.split("|")
    purchase_id = int(purchase_id)
    slot_id = int(slot_id)

    channels = await db.channel.get_user_channels(call.from_user.id)

    await call.message.edit_text(
        "Выберите канал:",
        reply_markup=InlineAdPurchase.channel_list_menu(purchase_id, slot_id, channels),
    )


@router.callback_query(F.data.startswith("AdPurchase|set_channel|"))
@safe_handler(
    "Закуп: сохранение маппинга канала"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def save_mapping_channel(call: CallbackQuery) -> None:
    """
    Сохранение привязки ссылки к выбранному каналу.
    Проверяет наличие активной подписки у канала.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    _, _, purchase_id, slot_id, channel_id = call.data.split("|")
    purchase_id = int(purchase_id)
    slot_id = int(slot_id)
    channel_id = int(channel_id)

    # Проверка подписки
    channel = await db.channel.get_channel_by_chat_id(channel_id)
    if not channel:
        await call.answer("Канал не найден", show_alert=True)
        return

    if not channel.subscribe or channel.subscribe < time.time():
        await call.answer(
            "У канала нет активной подписки. Продлите подписку для использования.",
            show_alert=True,
        )
        return

    await db.ad_purchase.upsert_link_mapping(
        ad_purchase_id=purchase_id,
        slot_id=slot_id,
        target_type=AdTargetType.CHANNEL,
        target_channel_id=channel_id,
        track_enabled=True,
    )

    # Обновление меню
    await call.message.delete()
    await show_mapping_menu(call.message, purchase_id)


@router.callback_query(F.data.startswith("AdPurchase|set_external|"))
@safe_handler(
    "Закуп: сохранение внешнего маппинга"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def save_mapping_external(call: CallbackQuery) -> None:
    """
    Установка типа 'внешняя ссылка' (без трекинга).

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    _, _, purchase_id, slot_id = call.data.split("|")
    purchase_id = int(purchase_id)
    slot_id = int(slot_id)

    await db.ad_purchase.upsert_link_mapping(
        ad_purchase_id=purchase_id,
        slot_id=slot_id,
        target_type=AdTargetType.EXTERNAL,
        target_channel_id=None,
        track_enabled=False,
    )

    # Обновление меню
    await call.message.delete()
    await show_mapping_menu(call.message, purchase_id)


@router.callback_query(F.data.startswith("AdPurchase|mapping|"))
@safe_handler(
    "Закуп: возврат к маппингу"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_to_mapping(call: CallbackQuery) -> None:
    """
    Возврат к главному меню маппинга.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    purchase_id = int(call.data.split("|")[2])
    await call.message.delete()
    await show_mapping_menu(call.message, purchase_id)


@router.callback_query(F.data.startswith("AdPurchase|save_mapping|"))
@safe_handler(
    "Закуп: завершение маппинга"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def finish_mapping(call: CallbackQuery) -> None:
    """
    Завершение маппинга и переход к просмотру закупа.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    purchase_id = int(call.data.split("|")[2])
    await call.answer("Мапинг сохранен")
    # Возврат к просмотру закупа
    await view_purchase(call, purchase_id)


@router.callback_query(F.data == "AdPurchase|cancel")
@safe_handler(
    "Закуп: отмена"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def cancel_purchase(call: CallbackQuery, state: FSMContext) -> None:
    """
    Отмена процесса создания закупа.

    Аргументы:
        call (CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await state.clear()
    await call.message.delete()
    await call.message.answer("Создание закупа отменено.")


@router.callback_query(F.data.startswith("AdPurchase|view|"))
@safe_handler(
    "Закуп: просмотр (callback)"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def view_purchase_callback(call: CallbackQuery) -> None:
    """
    Callback для просмотра закупа.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    purchase_id = int(call.data.split("|")[2])
    await view_purchase(call, purchase_id)


@safe_handler(
    "Закуп: просмотр деталей"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def view_purchase(call: CallbackQuery, purchase_id: int) -> None:
    """
    Отображение деталей существующего закупа.

    Аргументы:
        call (CallbackQuery): Callback запрос.
        purchase_id (int): ID закупа.
    """
    purchase = await db.ad_purchase.get_purchase(purchase_id)
    if not purchase:
        await call.answer("Закуп не найден", show_alert=True)
        return

    creative = await db.ad_creative.get_creative(purchase.creative_id)
    creative_name = creative.name if creative else "Unknown"

    # Локализация статуса
    status_map = {
        "active": "🟢 Активен",
        "paused": "⏸ На паузе",
        "deleted": "🗑 Удален",
        "completed": "🏁 Завершен",
    }
    status_text = status_map.get(purchase.status, purchase.status)

    text_content = (
        f"💳 <b>Закуп: «{purchase.comment or 'Нет названия'}»</b>\n"
        f"🎨 Креатив: {creative_name}\n"
        f"📊 Тип: {purchase.pricing_type.value}\n"
        f"💸 Ставка: {purchase.price_value} руб.\n"
        f"📋 Комментарий: {purchase.comment or 'Нет'}\n"
        f"📌 Статус: {status_text}"
    )

    # Если сообщение не изменено, edit_text может упасть, поэтому try/except
    try:
        await call.message.edit_text(
            text_content,
            reply_markup=InlineAdPurchase.purchase_view_menu(purchase.id),
            parse_mode="HTML",
        )
    except Exception:
        await call.message.answer(
            text_content,
            reply_markup=InlineAdPurchase.purchase_view_menu(purchase.id),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("AdPurchase|delete|"))
@safe_handler(
    "Закуп: удаление"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def delete_purchase(call: CallbackQuery) -> None:
    """
    Удаление закупа (Soft Delete).

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    purchase_id = int(call.data.split("|")[2])
    await db.ad_purchase.update_purchase_status(purchase_id, "deleted")
    await call.answer("Закуп удален")

    # Проверка оставшихся
    purchases = await db.ad_purchase.get_user_purchases(call.from_user.id)

    if not purchases:
        # Закупов не осталось, переход в главное меню
        await call.message.edit_text(
            "💰 Рекламные закупы", reply_markup=InlineAdPurchase.main_menu()
        )
    else:
        from main_bot.handlers.user.ad_creative.purchase_menu import show_purchase_list

        await show_purchase_list(call)


@router.callback_query(F.data.startswith("AdPurchase|stats|"))
@safe_handler(
    "Закуп: статистика (дефолт)"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_stats_default(call: CallbackQuery) -> None:
    """
    Показ статистики (по умолчанию за все время).

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    purchase_id = int(call.data.split("|")[2])
    await render_purchase_stats(call, purchase_id, "all")


@router.callback_query(F.data.startswith("AdPurchase|stats_period|"))
@safe_handler(
    "Закуп: статистика (период)"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_stats_period(call: CallbackQuery) -> None:
    """
    Показ статистики за выбранный период.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    parts = call.data.split("|")
    purchase_id = int(parts[2])
    period = parts[3]
    await render_purchase_stats(call, purchase_id, period)


@safe_handler(
    "Закуп: расчет статистики"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def render_purchase_stats(
    call: CallbackQuery, purchase_id: int, period: str
) -> None:
    """
    Рендеринг сообщения со статистикой закупа.
    Рассчитывает стоимость, конверсии и отображает данные.

    Аргументы:
        call (CallbackQuery): Callback запрос.
        purchase_id (int): ID закупа.
        period (str): Период (24h, 7d, 30d, all).
    """
    now = int(time.time())

    if period == "24h":
        from_ts = now - (24 * 3600)
        period_name = "24 часа"
    elif period == "7d":
        from_ts = now - (7 * 24 * 3600)
        period_name = "7 дней"
    elif period == "30d":
        from_ts = now - (30 * 24 * 3600)
        period_name = "30 дней"
    else:  # за все время
        from_ts = None
        period_name = "всё время"

    to_ts = now

    # Получение информации о закупе
    purchase = await db.ad_purchase.get_purchase(purchase_id)
    if not purchase:
        await call.answer("Закуп не найден", show_alert=True)
        return

    # Получение статистики
    leads_count = await db.ad_purchase.get_leads_count(purchase_id)
    subs_count = await db.ad_purchase.get_subscriptions_count(
        purchase_id, from_ts, to_ts
    )

    # Статистика по каналам
    mappings = await db.ad_purchase.get_link_mappings(purchase_id)
    channels_stats = {}
    total_unsubs = 0

    for m in mappings:
        if m.target_channel_id:
            # Инициализация подсчета
            if m.target_channel_id not in channels_stats:
                channel = await db.channel.get_channel_by_chat_id(m.target_channel_id)
                channels_stats[m.target_channel_id] = {
                    "name": channel.title if channel else f"ID: {m.target_channel_id}",
                    "leads": 0,
                    "subs": 0,
                    "unsubs": 0,
                }

            # Лиды (привязанные к слоту)
            slot_leads = await db.ad_purchase.get_leads_by_slot(purchase_id, m.slot_id)
            channels_stats[m.target_channel_id]["leads"] += len(slot_leads)

            # Подписки (связанные со слотом/каналом)
            slot_subs_all = await db.ad_purchase.get_subscriptions_by_slot(
                purchase_id, m.slot_id, from_ts, to_ts
            )

            # Фильтрация
            active_subs = [s for s in slot_subs_all if s.status == "active"]
            left_subs = [s for s in slot_subs_all if s.status != "active"]

            channels_stats[m.target_channel_id]["subs"] += len(active_subs)
            channels_stats[m.target_channel_id]["unsubs"] += len(left_subs)
            total_unsubs += len(left_subs)

    # Формируем статистику в зависимости от типа оплаты
    pricing_type = purchase.pricing_type.value

    if pricing_type == "FIXED":
        # Фиксированная оплата
        description = (
            f"💵 Цена заявки/подписки: "
            f"{(purchase.price_value / leads_count) if leads_count > 0 else 0:.2f}₽ / "
            f"{(purchase.price_value / subs_count) if subs_count > 0 else 0:.2f}₽\n"
            f"💳 Тип оплаты: Фиксированная\n"
            f"💰 Цена: {purchase.price_value} руб."
        )
    elif pricing_type == "CPL":
        # Оплата за заявку
        total_cost = leads_count * purchase.price_value
        description = (
            f"💵 Цена заявки: {purchase.price_value}₽\n"
            f"💳 Тип оплаты: По заявкам\n"
            f"💰 Цена: {total_cost} руб."
        )
    elif pricing_type == "CPS":
        # Оплата за подписку
        total_cost = subs_count * purchase.price_value
        description = (
            f"💵 Цена подписки: {purchase.price_value}₽\n"
            f"💳 Тип оплаты: По подпискам\n"
            f"💰 Цена: {total_cost} руб."
        )
    else:
        # Резервный вариант
        description = (
            f"💵 Тип оплаты: {pricing_type}\n💸 Ставка: {purchase.price_value} руб."
        )

    stats_text = (
        f"📊 <b>Статистика закупа: «{purchase.comment or 'Нет названия'}»</b>\n"
        f"Период: {period_name}\n\n"
        f"📎 Заявок: {leads_count}\n"
        f"👥 Присоединились: {subs_count}\n"
        f"📉 Отписалось: {total_unsubs}\n"
        f"{description}"
    )

    # Добавление разбивки по каналам
    if channels_stats:
        stats_text += "\n\n<b>📺 По каналам:</b>\n"
        for ch_id, ch_data in channels_stats.items():
            stats_text += (
                f"• {ch_data['name']}:\n"
                f"{ch_data['leads']} заявок | {ch_data['subs']} подписок | {ch_data['unsubs']} отписок\n"
            )

    try:
        await call.message.edit_text(
            stats_text,
            reply_markup=InlineAdPurchase.stats_period_menu(purchase_id),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        await call.answer()


@router.callback_query(F.data == "AdPurchase|global_stats")
@safe_handler(
    "Закуп: меню общей статистики"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_global_stats_menu(call: CallbackQuery) -> None:
    """
    Меню глобальной статистики пользователя.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    await call.message.edit_text(
        "Выберите период создания закупов для получения Excel-отчета по всем закупам.",
        reply_markup=InlineAdPurchase.global_stats_period_menu(),
    )


@router.callback_query(F.data.startswith("AdPurchase|global_stats_period|"))
@safe_handler(
    "Закуп: генерация Excel (все закупы)"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_global_stats(call: CallbackQuery) -> None:
    """
    Генерация и отправка общего отчета по закупам в формате Excel.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    period = call.data.split("|")[2]
    now = int(time.time())

    if period == "24h":
        from_ts = now - (24 * 3600)
        period_name = "24_hours"
    elif period == "7d":
        from_ts = now - (7 * 24 * 3600)
        period_name = "7_days"
    elif period == "30d":
        from_ts = now - (30 * 24 * 3600)
        period_name = "30_days"
    else:  # за все время
        from_ts = 0
        period_name = "all_time"

    to_ts = now
    user_id = call.from_user.id

    # 1. Получение закупов за этот период
    all_purchases = await db.ad_purchase.get_user_purchases(user_id)
    purchases = [
        p
        for p in all_purchases
        if p.created_timestamp >= from_ts and p.created_timestamp <= to_ts
    ]

    if not purchases:
        await call.answer("За этот период закупов не найдено.", show_alert=True)
        return

    await call.answer("Генерация отчета...")

    # 2. Создание Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Statistics"

    # Заголовки
    headers = [
        "Дата",
        "Название креатива",
        "Комментарий",
        "Фикс цена",
        "Цена заявки",
        "Цена подписчика",
        "Заявок подано",
        "Подписок",
        "Цена за подписчика",
        "Цена за заявку",
    ]
    ws.append(headers)

    for p in purchases:
        # Получение деталей
        creative = await db.ad_creative.get_creative(p.creative_id)
        creative_name = creative.name if creative else f"Unknown #{p.creative_id}"

        # Статистика (За все время для этого закупа)
        leads_count = await db.ad_purchase.get_leads_count(p.id)
        subs_count = await db.ad_purchase.get_subscriptions_count(p.id, None, None)

        # Цены
        fix_price = p.price_value if p.pricing_type.value == "FIXED" else 0
        cpl_price = p.price_value if p.pricing_type.value == "CPL" else 0
        cps_price = p.price_value if p.pricing_type.value == "CPS" else 0

        # Расчеты
        total_spend = 0
        if p.pricing_type.value == "FIXED":
            total_spend = p.price_value
        elif p.pricing_type.value == "CPL":
            total_spend = p.price_value * leads_count
        elif p.pricing_type.value == "CPS":
            total_spend = p.price_value * subs_count

        cost_per_sub = (total_spend / subs_count) if subs_count > 0 else 0
        cost_per_lead = (total_spend / leads_count) if leads_count > 0 else 0

        # Форматирование даты
        date_str = datetime.fromtimestamp(p.created_timestamp).strftime(
            "%d.%m.%Y %H:%M"
        )

        row = [
            date_str,
            creative_name,
            p.comment or "",
            fix_price,
            cpl_price,
            cps_price,
            leads_count,
            subs_count,
            round(cost_per_sub, 2),
            round(cost_per_lead, 2),
        ]
        ws.append(row)

    # Автоширина
    for column in ws.columns:
        max_length = 0
        column = [cell for cell in column]
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except Exception:
                pass
        adjusted_width = max_length + 2
        ws.column_dimensions[column[0].column_letter].width = adjusted_width

    # Сохранение в память
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    input_file = BufferedInputFile(
        file_stream.getvalue(), filename=f"stats_{period_name}.xlsx"
    )

    await call.message.answer_document(
        document=input_file, caption=f"📊 Статистика закупов за период: {period}"
    )


@router.callback_query(F.data.startswith("AdPurchase|gen_post|"))
@safe_handler(
    "Закуп: генерация рекламного поста"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def generate_post(call: CallbackQuery) -> None:
    """
    Генерация поста с замененными ссылками для публикации.
    Автоматически создает ref-ссылки для ботов и invite-ссылки для каналов.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    purchase_id = int(call.data.split("|")[2])

    # 1. Проверка пригласительных ссылок
    mappings, errors = await db.ad_purchase.ensure_invite_links(purchase_id, call.bot)

    # Показ ошибок если есть
    if errors:
        error_text = (
            "⚠️ Не удалось создать invite-ссылки для некоторых каналов:\n"
            + "\n".join(errors)
        )
        await call.message.answer(error_text)

    # 2. Получение креатива
    purchase = await db.ad_purchase.get_purchase(purchase_id)
    creative = await db.ad_creative.get_creative(purchase.creative_id)

    if not creative or not creative.raw_message:
        await call.answer("Ошибка: креатив не найден или пуст", show_alert=True)
        return

    # 3. Подготовка сообщения
    message_data = copy.deepcopy(creative.raw_message)

    # Генерация ref-ссылок для ботов
    for m in mappings:
        # Проверка, является ли ссылка ссылкой на бота
        if m.track_enabled and not m.ref_param:
            # Попытка определить юзернейм бота
            bot_username_match = re.match(
                r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)(?:\?|$)", m.original_url
            )

            if bot_username_match and "/" not in bot_username_match.group(1):
                # Похоже на ссылку бота
                bot_username = bot_username_match.group(1)
                ref_param = f"ref_{purchase_id}_{m.slot_id}"

                await db.ad_purchase.upsert_link_mapping(
                    ad_purchase_id=purchase_id, slot_id=m.slot_id, ref_param=ref_param
                )

                # Обновление локального объекта
                m.ref_param = ref_param

                # Установка типа цели BOT если еще не установлено
                if m.target_type != AdTargetType.BOT:
                    await db.ad_purchase.upsert_link_mapping(
                        ad_purchase_id=purchase_id,
                        slot_id=m.slot_id,
                        target_type=AdTargetType.BOT,
                    )
                    m.target_type = AdTargetType.BOT

    # Create a map of original_url -> replacement_link
    url_map = {}
    replaced_count = 0
    for m in mappings:
        original_key = m.original_url.rstrip("/")

        # Priority 1: invite_link (for channels)
        if m.invite_link:
            url_map[original_key] = m.invite_link
            replaced_count += 1
        # Priority 2: ref-link (for bots)
        elif m.ref_param and m.target_type == AdTargetType.BOT:
            # Extract bot username from original URL
            bot_username_match = re.match(
                r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)", m.original_url
            )
            if bot_username_match:
                bot_username = bot_username_match.group(1)
                ref_link = f"https://t.me/{bot_username}?start={m.ref_param}"
                url_map[original_key] = ref_link
                # Also map the un-normalized version just in case
                url_map[m.original_url] = ref_link
                replaced_count += 1

    # Helper to replace in text
    def replace_links_in_entities(text_content, entities):
        if not entities:
            return
        for entity in entities:
            # Handle text_link (formatted links)
            if entity.get("type") == "text_link":
                url = entity.get("url")
                if url:
                    # Try exact match first, then normalized
                    normalized_url = url.rstrip("/")
                    if url in url_map:
                        entity["url"] = url_map[url]
                    elif normalized_url in url_map:
                        entity["url"] = url_map[normalized_url]

            # Handle url (raw links)
            elif entity.get("type") == "url":
                offset = entity.get("offset")
                length = entity.get("length")
                url = text_content[offset : offset + length]

                if url:
                    normalized_url = url.rstrip("/")
                    target_url = None
                    if url in url_map:
                        target_url = url_map[url]
                    elif normalized_url in url_map:
                        target_url = url_map[normalized_url]

                    if target_url:
                        entity["type"] = "text_link"
                        entity["url"] = target_url

    # Replace in caption/text entities
    if "entities" in message_data:
        replace_links_in_entities(
            message_data.get("text", ""), message_data["entities"]
        )

    if "caption_entities" in message_data:
        replace_links_in_entities(
            message_data.get("caption", ""), message_data["caption_entities"]
        )

    # Replace in inline keyboard
    if (
        "reply_markup" in message_data
        and "inline_keyboard" in message_data["reply_markup"]
    ):
        for row in message_data["reply_markup"]["inline_keyboard"]:
            for btn in row:
                if "url" in btn:
                    if btn["url"] in url_map:
                        btn["url"] = url_map[btn["url"]]

    # 4. Send to user
    try:
        chat_id = call.from_user.id
        reply_markup = message_data.get("reply_markup")

        # Helper to safely create entities
        def safe_entities(ent_list):
            if not ent_list:
                return None
            try:
                # Filter out nulls if any
                return [types.MessageEntity(**e) for e in ent_list if e]
            except Exception:
                return None

        final_entities = safe_entities(message_data.get("entities"))
        final_caption_entities = safe_entities(message_data.get("caption_entities"))

        if "photo" in message_data:
            photo_id = message_data["photo"][-1]["file_id"]
            caption = message_data.get("caption", "")
            if len(caption) > 1024:
                await call.answer(
                    "Ошибка: Подпись к медиа слишком длинная (макс. 1024 символа).",
                    show_alert=True,
                )
                return
            await call.bot.send_photo(
                chat_id=chat_id,
                photo=photo_id,
                caption=caption if caption else None,
                caption_entities=final_caption_entities,
                reply_markup=reply_markup,
                parse_mode=None,
            )
        elif "video" in message_data:
            video_id = message_data["video"]["file_id"]
            caption = message_data.get("caption", "")
            if len(caption) > 1024:
                await call.answer(
                    "Ошибка: Подпись к медиа слишком длинная (макс. 1024 символа).",
                    show_alert=True,
                )
                return
            await call.bot.send_video(
                chat_id=chat_id,
                video=video_id,
                caption=caption if caption else None,
                caption_entities=final_caption_entities,
                reply_markup=reply_markup,
                parse_mode=None,
            )
        elif "animation" in message_data:
            animation_id = message_data["animation"]["file_id"]
            caption = message_data.get("caption", "")
            if len(caption) > 1024:
                await call.answer(
                    "Ошибка: Подпись к медиа слишком длинная (макс. 1024 символа).",
                    show_alert=True,
                )
                return
            await call.bot.send_animation(
                chat_id=chat_id,
                animation=animation_id,
                caption=caption if caption else None,
                caption_entities=final_caption_entities,
                reply_markup=reply_markup,
                parse_mode=None,
            )
        elif "text" in message_data:
            text_content = message_data["text"]
            if len(text_content) > 4096:
                await call.answer(
                    "Ошибка: Текст сообщения слишком длинный (макс. 4096 символов).",
                    show_alert=True,
                )
                return
            await call.bot.send_message(
                chat_id=chat_id,
                text=text_content,
                entities=final_entities,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=None,
            )
        else:
            await call.answer(
                "Неподдерживаемый тип сообщения для генерации", show_alert=True
            )
            return

        success_msg = "☝️☝️☝️ ваш пост для закупа ☝️☝️☝️\n\n✅ Готово! Перешлите это админу для размещения."
        if replaced_count > 0:
            success_msg += f"\n📎 Заменено ссылок: {replaced_count}"
        await call.message.answer(success_msg)

        # Redirect to Purchase List
        from main_bot.handlers.user.ad_creative.purchase_menu import show_purchase_list

        await show_purchase_list(call, send_new=True)

    except Exception as e:
        err_str = str(e)
        if "MESSAGE_TOO_LONG" in err_str:
            await call.answer(
                "Ошибка: Сообщение слишком длинное для отправки.", show_alert=True
            )
        else:
            await call.answer(f"Ошибка при отправке: {e}", show_alert=True)
