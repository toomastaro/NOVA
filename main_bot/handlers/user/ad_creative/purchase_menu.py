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
from main_bot.keyboards.common import Reply
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = Router(name="AdPurchaseMenu")


@router.message(F.text == "Рекламные закупы")
@safe_handler(
    "Закупы: показ меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_ad_purchase_menu(message: types.Message) -> None:
    """
    Показ меню закупов (сообщение).

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    await show_ad_purchase_menu_internal(message, edit=False)


@router.callback_query(F.data == "AdPurchase|menu")
@safe_handler(
    "Закупы: показ меню (callback)"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_ad_purchase_menu_callback(call: CallbackQuery) -> None:
    """
    Показ меню закупов (callback).

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    await show_ad_purchase_menu_internal(call.message, edit=True)


@safe_handler(
    "Закупы: показ меню (внутренний)"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
        status_text = text("ad_purchase:menu:no_channels")
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

            status_text = text("ad_purchase:menu:client_status").format(client_name)
        else:
            status_text = text("ad_purchase:menu:client_not_found")

    logger.info(
        f"Рендеринг меню закупки рекламы для пользователя {message.chat.id}, количество каналов: {len(user_channels)}"
    )

    # Determine text
    main_text = text("ad_purchase:menu:title_main").format(status_text)

    # Keyboard
    kb = InlineAdPurchase.main_menu()

    if edit:
        await message.edit_text(main_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(main_text, reply_markup=kb, parse_mode="HTML")

    # Перезагрузка главного меню
    await message.answer(text("main_menu:reload"), reply_markup=Reply.menu())


@router.callback_query(F.data == "AdPurchase|check_client_status")
@safe_handler(
    "Закупы: проверка статуса клиента"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def check_client_status(call: CallbackQuery) -> None:
    """
    Проверка статуса подключения технических аккаунтов к каналам пользователя.
    Выполняет фактическую проверку сессии и прав администратора.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    await call.answer(text("ad_purchase:check:start"), show_alert=False)

    user_channels = await db.channel.get_user_channels(call.message.chat.id)
    if not user_channels:
        await call.answer(text("ad_purchase:check:no_channels"), show_alert=True)
        return

    # Группируем каналы по клиентам для оптимизации сессий
    client_groups: Dict[
        int, Dict[str, Any]
    ] = {}  # {client_id: {'client': mt_client, 'channels': [channel]}}
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
        results.append(text("ad_purchase:check:no_client").format(ch.title))

    # 2. Проверка каждой группы клиентов
    for cid, group in client_groups.items():
        mt_client = group["client"]
        channels = group["channels"]
        session_path = Path(mt_client.session_path)
        client_label = mt_client.alias or f"Client {cid}"

        if not session_path.exists():
            for ch in channels:
                results.append(
                    text("ad_purchase:check:no_session").format(ch.title, client_label)
                )
            continue

        try:
            async with SessionManager(session_path) as manager:
                if not manager.client or not await manager.client.is_user_authorized():
                    for ch in channels:
                        results.append(
                            text("ad_purchase:check:not_authorized").format(ch.title, client_label)
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
                        results.append(text("ad_purchase:check:success").format(ch.title))
                    except Exception as e:
                        err_str = str(e)
                        if "ChatAdminRequiredError" in err_str:
                            error_msg = text("ad_purchase:check:admin_required")
                        else:
                            error_msg = text("ad_purchase:check:access_error")
                        results.append(f"❌ <b>{ch.title}</b>: {error_msg}")
                        logger.error(f"Проверка не удалась для {ch.title}: {e}")

        except Exception as e:
            logger.error(f"Ошибка сессии для {client_label}: {e}")
            for ch in channels:
                results.append(
                    text("ad_purchase:check:conn_error").format(ch.title, client_label)
                )

    # Формирование "профессионального" отчета
    success_count = sum(1 for r in results if r.startswith("✅"))
    total_count = len(user_channels)
    results_str = "\n".join(results)

    main_text = text("ad_purchase:report:header").format(
        success_count, total_count, results_str
    )

    # Отправляем новым сообщением
    await call.message.answer(
        text=main_text,
        reply_markup=InlineAdPurchase.close_button(),
        parse_mode="HTML"
    )

    # Старое сообщение - просто подтверждаем проверку во всплывающем уведомлении
    await call.answer(text("ad_purchase:check:finished"))


@router.callback_query(F.data == "AdPurchase|close_report")
@safe_handler("Закупы: закрыть отчет")
async def close_report(call: CallbackQuery) -> None:
    """Удаляет сообщение с отчетом."""
    await call.message.delete()


@router.callback_query(F.data == "AdPurchase|create_menu")
@safe_handler(
    "Закупы: выбор креатива"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
            text("ad_purchase:create:no_creatives"), show_alert=True
        )
        return

    user_channels = await db.channel.get_user_channels(call.from_user.id)
    if not user_channels:
        await call.answer(text("ad_purchase:create:no_channels"), show_alert=True)
        return

    client_model = await db.mt_client_channel.get_preferred_for_stats(
        user_channels[0].chat_id
    ) or await db.mt_client_channel.get_any_client_for_channel(user_channels[0].chat_id)
    if not client_model:
        await call.answer(text("ad_purchase:create:no_client"), show_alert=True)
        return

    await call.message.edit_text(
        text("ad_purchase:create:select_creative"),
        reply_markup=InlineAdPurchase.creative_selection_menu(creatives),
    )


@router.callback_query(F.data == "AdPurchase|list")
@safe_handler(
    "Закупы: список"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
            await call.message.answer(text("ad_purchase:list:no_purchases"))
        else:
            await call.answer(text("ad_purchase:list:no_purchases"), show_alert=True)
        return

    enriched_purchases = []
    for p in purchases:
        creative = await db.ad_creative.get_creative(p.creative_id)
        p.creative_name = creative.name if creative else "Unknown"
        enriched_purchases.append(p)

    enriched_purchases.sort(key=lambda x: x.id, reverse=True)

    main_text = text("ad_purchase:list:title")
    kb = InlineAdPurchase.purchase_list_menu(enriched_purchases)

    if send_new:
        await call.message.answer(main_text, reply_markup=kb)
    else:
        await call.message.edit_text(main_text, reply_markup=kb)

    # Перезагрузка главного меню
    await call.message.answer(text("main_menu:reload"), reply_markup=Reply.menu())
