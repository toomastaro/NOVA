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
from datetime import datetime, timezone
from io import BytesIO


from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from openpyxl import Workbook

from main_bot.database.db import db
from main_bot.database.db_types import AdPricingType, AdTargetType
from main_bot.keyboards import InlineAdPurchase
from main_bot.states.user import AdPurchaseStates
from main_bot.keyboards.common import Reply
from main_bot.utils.lang.language import text
from main_bot.utils.message_utils import reload_main_menu
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
        text("ad_purchase:create:pricing_type"),
        reply_markup=InlineAdPurchase.pricing_type_menu(),
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
        await call.answer(text("ad_purchase:error:pricing_type"))
        return

    await state.update_data(pricing_type=pricing_type)

    await call.message.edit_text(
        text("ad_purchase:create:enter_price"), reply_markup=None
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
        await message.answer(text("ad_purchase:error:invalid_price"))
        return

    await state.update_data(price_value=price)
    await message.answer(text("ad_purchase:create:enter_comment"))
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

    await message.answer(text("ad_purchase:create:success").format(purchase_id))

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

    # Автоопределение на основе подсказок из креатива
    for slot in slots:
        # Проверка существования маппинга
        existing_mappings = await db.ad_purchase.get_link_mappings(purchase_id)
        existing_slot_ids = [m.slot_id for m in existing_mappings]

        if slot.id in existing_slot_ids:
            continue

        target_type = AdTargetType.EXTERNAL
        target_channel_id = None
        track_enabled = False

        # Используем подсказку, если она есть
        if slot.suggested_channel_id:
            target_type = AdTargetType.CHANNEL
            target_channel_id = slot.suggested_channel_id
            track_enabled = True

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
        status_text = text("ad_purchase:mapping:status:no_tracking")
        display_name = None
        channel_url = None
        
        if m.target_type == AdTargetType.CHANNEL and m.target_channel_id:
            display_name = channels_map.get(m.target_channel_id)
            status_text = display_name or text("ad_purchase:mapping:status:unknown_channel")
            
            # Получаем ссылку на канал для левой кнопки
            try:
                chat = await message.bot.get_chat(m.target_channel_id)
                if chat.username:
                    channel_url = f"https://t.me/{chat.username}"
                else:
                    invite = await chat.export_invite_link()
                    channel_url = invite
            except Exception:
                pass
        elif m.target_type == AdTargetType.EXTERNAL:
            status_text = text("ad_purchase:mapping:status:no_tracking")

        links_data.append(
            {
                "slot_id": m.slot_id,
                "original_url": (
                    m.original_url[:30] + "..."
                    if len(m.original_url) > 30
                    else m.original_url
                ),
                "display_name": display_name,
                "status_text": status_text,
                "channel_url": channel_url,
            }
        )

    await message.answer(
        text("ad_purchase:mapping:menu_text").format(len(mappings)),
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
        text("ad_purchase:mapping:edit_action"),
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
        text("ad_purchase:mapping:select_channel"),
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
        await call.answer(text("ad_purchase:mapping:error:not_found"), show_alert=True)
        return

    if not channel.subscribe or channel.subscribe < time.time():
        await call.answer(
            text("ad_purchase:mapping:error:no_sub"),
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
    await call.answer(text("ad_purchase:mapping:success"))

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
    await call.answer(text("ad_purchase:mapping:success"))

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
    await call.answer(text("ad_purchase:mapping:success"))
    # Перезагрузка главного меню
    # При финише маппинга сообщение с отчетом не является триггером
    await reload_main_menu(call.message, delete_trigger=False)
    await call.answer()
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
    await call.message.answer(
        text("ad_purchase:create:cancelled"), reply_markup=Reply.menu(call.from_user.id)
    )


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
        await call.answer(text("ad_purchase:view:not_found"), show_alert=True)
        return

    creative = await db.ad_creative.get_creative(purchase.creative_id)
    creative_name = creative.name if creative else "Unknown"

    # Локализация статуса
    status_map = {
        "active": text("ad_purchase:status:active"),
        "paused": text("ad_purchase:status:paused"),
        "deleted": text("ad_purchase:status:deleted"),
        "completed": text("ad_purchase:status:completed"),
    }
    status_text = status_map.get(purchase.status, purchase.status)

    text_content = text("ad_purchase:view:template").format(
        comment=purchase.comment or "???",
        creative_name=creative_name,
        pricing_type=purchase.pricing_type.value,
        price_value=purchase.price_value,
        comment_val=purchase.comment or "...",
        status=status_text,
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
    await call.answer(text("ad_purchase:deleted_ok"))
    # Перезагрузка главного меню
    # После удаления закупа сообщение со списком не является триггером
    await reload_main_menu(call.message, delete_trigger=False)
    await call.answer()

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
    # Получение информации о закупе
    purchase = await db.ad_purchase.get_purchase(purchase_id)
    if not purchase:
        await call.answer(text("ad_purchase:view:not_found"), show_alert=True)
        return

    # ПОДГОТОВКА ПЕРИОДА
    now = int(datetime.now(timezone.utc).timestamp())
    from_ts = None
    period_key = f"ad_purchase:stats:period_{period}"
    period_name = text(period_key)

    if period == "24h":
        from_ts = now - (24 * 3600)
    elif period == "7d":
        from_ts = now - (7 * 24 * 3600)
    elif period == "30d":
        from_ts = now - (30 * 24 * 3600)

    # 1. Получение пакетной статистики по слотам (ОПТИМИЗАЦИЯ N+1)
    stats_batch = await db.ad_purchase.get_stats_batch_by_slots(
        purchase_id, from_ts=from_ts
    )

    # 2. Агрегация общей статистики
    leads_count = sum(s["leads"] for s in stats_batch.values())
    subs_count = sum(s["subs"] for s in stats_batch.values())
    total_unsubs = sum(s["unsubs"] for s in stats_batch.values())

    # Статистика по каналам
    mappings = await db.ad_purchase.get_link_mappings(purchase_id)
    channels_stats = {}

    for m in mappings:
        if m.target_channel_id:
            slot_data = stats_batch.get(m.slot_id, {"leads": 0, "subs": 0, "unsubs": 0})

            if m.target_channel_id not in channels_stats:
                channels_stats[m.target_channel_id] = {
                    "name": m.target_title or f"ID: {m.target_channel_id}",
                    "leads": 0,
                    "subs": 0,
                    "unsubs": 0,
                }

            channels_stats[m.target_channel_id]["leads"] += slot_data["leads"]
            channels_stats[m.target_channel_id]["subs"] += slot_data["subs"]
            channels_stats[m.target_channel_id]["unsubs"] += slot_data["unsubs"]

    # Формируем статистику в зависимости от типа оплаты
    pricing_type = purchase.pricing_type.value

    if pricing_type == "FIXED":
        # Фиксированная оплата
        description = text("ad_purchase:stats:pricing:fixed").format(
            (purchase.price_value / leads_count) if leads_count > 0 else 0,
            (purchase.price_value / subs_count) if subs_count > 0 else 0,
            purchase.price_value,
        )
    elif pricing_type == "CPL":
        # Оплата за заявку
        total_cost = leads_count * purchase.price_value
        description = text("ad_purchase:stats:pricing:cpl").format(
            purchase.price_value, total_cost
        )
    elif pricing_type == "CPS":
        # Оплата за подписку
        total_cost = subs_count * purchase.price_value
        description = text("ad_purchase:stats:pricing:cps").format(
            purchase.price_value, total_cost
        )
    else:
        # Резервный вариант
        description = text("ad_purchase:stats:pricing:other").format(
            pricing_type, purchase.price_value
        )

    stats_text = text("ad_purchase:stats:template").format(
        name=purchase.comment or "???",
        period=period_name,
        leads=leads_count,
        subs=subs_count,
        unsubs=total_unsubs,
        description=description,
    )

    # Добавление разбивки по каналам
    if channels_stats:
        stats_text += "\n\n<b>📺 По каналам:</b>\n"
        for ch_id, ch_data in channels_stats.items():
            stats_text += text("ad_purchase:stats:channel_row").format(
                name=ch_data["name"],
                leads=ch_data["leads"],
                subs=ch_data["subs"],
                unsubs=ch_data["unsubs"],
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
        text("ad_purchase:global_stats:menu"),
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
    now = int(datetime.now(timezone.utc).timestamp())

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
        await call.answer(text("ad_purchase:global_stats:empty"), show_alert=True)
        return

    await call.answer(text("ad_purchase:global_stats:generating"))

    # ОПТИМИЗАЦИЯ: Пакетное получение статистики для всех закупов
    purchase_ids = [p.id for p in purchases]
    stats_batch = await db.ad_purchase.get_purchases_stats_batch(purchase_ids)

    # 2. Создание Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Statistics"

    # Заголовки
    headers = [
        text("excel:date"),
        text("excel:creative_name"),
        text("excel:comment"),
        text("excel:fix_price"),
        text("excel:cpl_price"),
        text("excel:cps_price"),
        text("excel:leads_count"),
        text("excel:subs_count"),
        text("excel:cost_per_sub"),
        text("excel:cost_per_lead"),
    ]
    ws.append(headers)

    for p in purchases:
        # Получение деталей
        creative = await db.ad_creative.get_creative(p.creative_id)
        creative_name = creative.name if creative else f"Unknown #{p.creative_id}"

        # Статистика (ПАКЕТНО)
        p_stats = stats_batch.get(p.id, {"leads": 0, "subs": 0})
        leads_count = p_stats["leads"]
        subs_count = p_stats["subs"]

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
        document=input_file,
        caption=text("ad_purchase:global_stats:caption").format(period),
    )
    # Перезагрузка главного меню
    await reload_main_menu(call.message)
    await call.answer()


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
            text("ad_purchase:generate:error_invite") + "\n" + "\n".join(errors)
        )
        await call.message.answer(error_text)

    # 2. Получение креатива
    purchase = await db.ad_purchase.get_purchase(purchase_id)
    creative = await db.ad_creative.get_creative(purchase.creative_id)

    if not creative or not creative.raw_message:
        await call.answer(text("ad_purchase:generate:error_creative"), show_alert=True)
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
                    text("ad_purchase:generate:error_too_long_caption"),
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
                    text("ad_purchase:gen_post:caption_too_long"),
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
                    text("ad_purchase:gen_post:caption_too_long"),
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
                    text("ad_purchase:gen_post:text_too_long"),
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
                text("ad_purchase:gen_post:unsupported"), show_alert=True
            )
            return

        success_msg = text("ad_purchase:gen_post:success")
        if replaced_count > 0:
            success_msg += "\n" + text("ad_purchase:gen_post:replaced_stats").format(
                replaced_count
            )
        await call.message.answer(success_msg)

        # Redirect to Purchase List
        from main_bot.handlers.user.ad_creative.purchase_menu import show_purchase_list

        await show_purchase_list(call, send_new=True)

    except Exception as e:
        err_str = str(e)
        if "MESSAGE_TOO_LONG" in err_str:
            await call.answer(
                text("ad_purchase:gen_post:too_long_error"), show_alert=True
            )
        else:
            await call.answer(
                text("ad_purchase:gen_post:send_error").format(e), show_alert=True
            )
