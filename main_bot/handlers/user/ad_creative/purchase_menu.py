"""
Модуль меню закупов рекламы.
Отображает списки закупов, проверяет статус технического аккаунта.

Модуль реализует:
- Отображение главного меню закупов
- Проверку подключения технических аккаунтов к каналам
- Навигацию по списку закупов
"""

import logging
from pathlib import Path
from typing import Dict, Any

from aiogram import Router, F, types
from aiogram.types import CallbackQuery

from main_bot.database.db import db
from main_bot.keyboards import InlineAdPurchase
from utils.error_handler import safe_handler
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = Router(name="AdPurchaseMenu")


@router.message(F.text == "Рекламные закупы")
@safe_handler("Show Ad Purchase Menu")
async def show_ad_purchase_menu(message: types.Message) -> None:
    """
    Показ меню закупов (сообщение).

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    await show_ad_purchase_menu_internal(message, edit=False)


@router.callback_query(F.data == "AdPurchase|menu")
@safe_handler("Show Ad Purchase Menu Callback")
async def show_ad_purchase_menu_callback(call: CallbackQuery) -> None:
    """
    Показ меню закупов (callback).

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    await show_ad_purchase_menu_internal(call.message, edit=True)


@safe_handler("Show Ad Purchase Menu Internal")
async def show_ad_purchase_menu_internal(
    message: types.Message, edit: bool = False
) -> None:
    """
    Внутренняя функция отображения меню закупов.
    Проверяет наличие технического аккаунта клиента в каналах пользователя.

    Аргументы:
        message (types.Message): Сообщение для ответа/редактирования.
        edit (bool): Флаг редактирования сообщения (True = edit, False = answer).
    """
    user_channels = await db.channel.get_user_channels(message.chat.id)

    status_text = ""
    client_name = "NovaClient"

    if not user_channels:
        status_text = "⚠️ Нет подключенных каналов."
    else:
        # Проверяем первый канал для примера
        first_ch = user_channels[0]
        # Получаем клиента
        client_model = await db.mt_client_channel.get_preferred_for_stats(
            first_ch.chat_id
        ) or await db.mt_client_channel.get_any_client_for_channel(first_ch.chat_id)

        if client_model and client_model.client:
            client_name = (
                client_model.client.alias or f"Client #{client_model.client.id}"
            )

            status_text = f"🤖 Клиент: {client_name}\n✅ Статус: Подключен"
        else:
            status_text = "❌ Клиент не найден в каналах."

    logger.info(
        f"Рендеринг меню закупки рекламы для пользователя {message.chat.id}, количество каналов: {len(user_channels)}"
    )

    # Determine text
    main_text = (
        "<b>💰 Рекламные закупы</b>\n\n"
        "Для сбора статистики в канал должен быть добавлен наш технический аккаунт "
        "с правами администратора (Публикация, Редактирование, Удаление).\n\n"
        f"{status_text}"
    )

    # Keyboard
    kb = InlineAdPurchase.main_menu()

    if edit:
        await message.edit_text(main_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(main_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "AdPurchase|check_client_status")
@safe_handler("Check Client Status")
async def check_client_status(call: CallbackQuery) -> None:
    """
    Проверка статуса подключения технических аккаунтов к каналам пользователя.
    Выполняет фактическую проверку сессии и прав администратора.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    await call.answer("⏳ Полная проверка всех каналов...", show_alert=False)

    user_channels = await db.channel.get_user_channels(call.message.chat.id)
    if not user_channels:
        await call.answer("Нет каналов для проверки.", show_alert=True)
        return

    # Группируем каналы по клиентам для оптимизации сессий
    client_groups: Dict[int, Dict[str, Any]] = (
        {}
    )  # {client_id: {'client': mt_client, 'channels': [channel]}}
    no_client_channels = []

    for channel in user_channels:
        client_model = await db.mt_client_channel.get_preferred_for_stats(
            channel.chat_id
        ) or await db.mt_client_channel.get_any_client_for_channel(channel.chat_id)

        if not client_model or not client_model.client:
            no_client_channels.append(channel)
            continue

        mt_client = client_model.client
        if mt_client.id not in client_groups:
            client_groups[mt_client.id] = {"client": mt_client, "channels": []}
        client_groups[mt_client.id]["channels"].append(channel)

    results = []

    # 1. Каналы без клиента
    for ch in no_client_channels:
        results.append(f"❌ <b>{ch.title}</b>: Не назначен помощник")

    # 2. Проверка каждой группы клиентов
    for cid, group in client_groups.items():
        mt_client = group["client"]
        channels = group["channels"]
        session_path = Path(mt_client.session_path)
        client_label = mt_client.alias or f"Client {cid}"

        if not session_path.exists():
            for ch in channels:
                results.append(
                    f"❌ <b>{ch.title}</b>: Нет файла сессии ({client_label})"
                )
            continue

        try:
            async with SessionManager(session_path) as manager:
                if not manager.client or not await manager.client.is_user_authorized():
                    for ch in channels:
                        results.append(
                            f"❌ <b>{ch.title}</b>: Сессия не авторизована ({client_label})"
                        )
                    continue

                # Проверка прав для каждого канала
                for ch in channels:
                    try:
                        # Попытка чтения лога для проверки прав админа
                        async for event in manager.client.iter_admin_log(
                            ch.chat_id, limit=1
                        ):
                            pass
                        results.append(f"✅ <b>{ch.title}</b>")
                    except Exception as e:
                        err_str = str(e)
                        if "ChatAdminRequiredError" in err_str:
                            error_msg = "Нет прав админа"
                        else:
                            error_msg = "Ошибка доступа"
                        results.append(f"❌ <b>{ch.title}</b>: {error_msg}")
                        logger.error(f"Check failed for {ch.title}: {e}")

        except Exception as e:
            logger.error(f"Session error for {client_label}: {e}")
            for ch in channels:
                results.append(
                    f"❌ <b>{ch.title}</b>: Ошибка подключения ({client_label})"
                )

    # Формирование отчета
    success_count = sum(1 for r in results if r.startswith("✅"))
    total_count = len(user_channels)

    report_header = f"📊 <b>Результат проверки ({success_count}/{total_count})</b>"
    report_body = "\n".join(results)

    main_text = (
        "<b>💰 Рекламные закупы</b>\n\n"
        "Для сбора статистики в канал должен быть добавлен наш технический аккаунт "
        "с правами администратора.\n\n"
        f"{report_header}\n"
        f"{report_body}"
    )

    await call.message.edit_text(
        text=main_text, reply_markup=InlineAdPurchase.main_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data == "AdPurchase|create_menu")
@safe_handler("Show Creative Selection")
async def show_creative_selection(call: CallbackQuery) -> None:
    """
    Меню выбора креатива для создания закупа.
    Проверяет наличие креативов, подключенных каналов и тех. аккаунта.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    creatives = await db.ad_creative.get_user_creatives(call.from_user.id)
    if not creatives:
        await call.answer(
            "У вас нет креативов. Сначала создайте креатив.", show_alert=True
        )
        return

    user_channels = await db.channel.get_user_channels(call.from_user.id)
    if not user_channels:
        await call.answer("Нет подключенных каналов!", show_alert=True)
        return

    client_model = await db.mt_client_channel.get_preferred_for_stats(
        user_channels[0].chat_id
    ) or await db.mt_client_channel.get_any_client_for_channel(user_channels[0].chat_id)
    if not client_model:
        await call.answer("Требуется технический аккаунт в канале!", show_alert=True)
        return

    await call.message.edit_text(
        "Выберите креатив для создания закупа:",
        reply_markup=InlineAdPurchase.creative_selection_menu(creatives),
    )


@router.callback_query(F.data == "AdPurchase|list")
@safe_handler("Show Purchase List")
async def show_purchase_list(call: CallbackQuery, send_new: bool = False) -> None:
    """
    Отображает список закупов пользователя.

    Аргументы:
        call (CallbackQuery): Callback запрос.
        send_new (bool): Если True, отправляет новое сообщение, иначе редактирует.
    """
    purchases = await db.ad_purchase.get_user_purchases(call.from_user.id)
    if not purchases:
        if send_new:
            await call.message.answer("У вас пока нет закупов.")
        else:
            await call.answer("У вас пока нет закупов.", show_alert=True)
        return

    enriched_purchases = []
    for p in purchases:
        creative = await db.ad_creative.get_creative(p.creative_id)
        p.creative_name = creative.name if creative else "Unknown"
        enriched_purchases.append(p)

    enriched_purchases.sort(key=lambda x: x.id, reverse=True)

    text = "Ваши закупы:"
    kb = InlineAdPurchase.purchase_list_menu(enriched_purchases)

    if send_new:
        await call.message.answer(text, reply_markup=kb)
    else:
        await call.message.edit_text(text, reply_markup=kb)
