"""
Обработчики расширенного функционала NOVAстат.

Модуль предоставляет:
- Аналитику каналов (просмотры, ER)
- Управление коллекциями и папками
- Расчет стоимости рекламы (CPM)
- Массовый выбор каналов
"""

import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards, InlineNovaStat
from main_bot.keyboards.common import Reply
from main_bot.states.user import NovaStatStates
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler
from main_bot.utils.novastat import novastat_service
from main_bot.utils.report_signature import get_report_signatures
from main_bot.utils.user_settings import get_user_view_mode, set_user_view_mode

logger = logging.getLogger(__name__)

# Константы
MAX_CHANNELS_SYNC = 5  # Максимум каналов для синхронной обработки
MAX_PARALLEL_REQUESTS = 5  # Максимум параллельных запросов
HOURS_TO_ANALYZE = [24, 48, 72]

router = Router()


@router.message(F.text == text("reply_menu:novastat"))
@safe_handler("NOVASTAT: главное меню")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_main(message: types.Message, state: FSMContext) -> None:
    """
    Главное меню аналитики.
    Проверяет подписку и отображает начальный экран NOVAstat.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    subscribed_channels = await db.channel.get_user_channels(message.from_user.id, sort_by="subscribe")
    now_ts = datetime.now(timezone.utc).timestamp()
    has_active_sub = any(
        ch.subscribe and ch.subscribe > now_ts for ch in subscribed_channels
    )

    if not has_active_sub:
        await message.answer(text("novastat_main_no_sub"))
        return

    await state.clear()
    await message.answer(
        text("novastat_main_text"),
        reply_markup=InlineNovaStat.main_menu(),
        parse_mode="HTML",
    )
    await state.set_state(NovaStatStates.waiting_for_channels)


@router.callback_query(F.data == "NovaStat|main")
@safe_handler("NOVASTAT: возврат в меню")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_main_cb(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Возврат в главное меню аналитики через callback.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    subscribed_channels = await db.channel.get_user_channels(call.from_user.id, sort_by="subscribe")
    now_ts = datetime.now(timezone.utc).timestamp()
    has_active_sub = any(
        ch.subscribe and ch.subscribe > now_ts for ch in subscribed_channels
    )

    if not has_active_sub:
        await call.answer(text("novastat_main_no_sub"), show_alert=True)
        return

    await state.clear()
    await call.message.edit_text(
        text("novastat_main_text"),
        reply_markup=InlineNovaStat.main_menu(),
        parse_mode="HTML",
    )
    await state.set_state(NovaStatStates.waiting_for_channels)


@router.callback_query(F.data == "NovaStat|exit")
@safe_handler("NOVASTAT: выход")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_exit(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Выход из меню NOVAstat в главное меню бота.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await state.clear()
    await call.message.delete()
    await call.message.answer(text("main_menu:reload"), reply_markup=Reply.menu())


@router.callback_query(F.data == "NovaStat|settings")
@safe_handler("NOVASTAT: настройки")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_settings(call: types.CallbackQuery) -> None:
    """
    Меню настроек NOVAstat (глубина анализа).

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    settings = await db.novastat.get_novastat_settings(call.from_user.id)
    await call.message.edit_text(
        text("novastat_settings_title").format(settings.depth_days),
        reply_markup=InlineNovaStat.settings(settings.depth_days),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("NovaStat|set_depth|"))
@safe_handler("NOVASTAT: установка глубины")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_set_depth(call: types.CallbackQuery) -> None:
    """
    Установка глубины анализа.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    depth = int(call.data.split("|")[2])
    await db.novastat.update_novastat_settings(call.from_user.id, depth_days=depth)
    await call.answer(text("novastat_settings_depth_updated").format(depth))

    # Обновление вида
    settings = await db.novastat.get_novastat_settings(call.from_user.id)
    await call.message.edit_text(
        text("novastat_settings_title").format(settings.depth_days),
        reply_markup=InlineNovaStat.settings(settings.depth_days),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "NovaStat|collections")
@safe_handler("NOVASTAT: список коллекций")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_collections(call: types.CallbackQuery) -> None:
    """
    Просмотр списка коллекций каналов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    collections = await db.novastat.get_collections(call.from_user.id)
    if not collections:
        await call.message.edit_text(
            text("novastat_collections_empty"),
            reply_markup=InlineNovaStat.collections_list([]),
        )
    else:
        text_list = text("novastat_collections_list_title")
        for i, col in enumerate(collections, 1):
            text_list += f"{i}. {col.name}\n"

        await call.message.edit_text(
            text_list,
            reply_markup=InlineNovaStat.collections_list(collections),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "NovaStat|col_create")
@safe_handler("NOVASTAT: коллекция — старт создания")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_create_col_start(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Начало создания новой коллекции.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await call.message.answer(text("novastat_col_create_enter_name"))
    await state.set_state(NovaStatStates.waiting_for_collection_name)
    await call.answer()


@router.message(NovaStatStates.waiting_for_collection_name)
@safe_handler("NOVASTAT: коллекция — сохранение имени")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_create_col_finish(message: types.Message, state: FSMContext) -> None:
    """
    Завершение создания коллекции (сохранение названия).

    Аргументы:
        message (types.Message): Сообщение с названием.
        state (FSMContext): Контекст состояния.
    """
    name = message.text
    await db.novastat.create_collection(message.from_user.id, name)
    await message.answer(text("novastat_col_create_success").format(name))

    # Возврат к списку коллекций
    collections = await db.novastat.get_collections(message.from_user.id)
    await message.answer(
        text("novastat_collections_list_title"),
        reply_markup=InlineNovaStat.collections_list(collections),
    )
    # Перезагрузка главного меню
    await message.answer(text("main_menu:reload"), reply_markup=Reply.menu())
    await state.clear()


@router.callback_query(F.data.startswith("NovaStat|col_open|"))
@safe_handler("NOVASTAT: коллекция — открытие")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_open_col(call: types.CallbackQuery) -> None:
    """
    Открытие конкретной коллекции.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    col_id = int(call.data.split("|")[2])
    collection = await db.novastat.get_collection(col_id)
    channels = await db.novastat.get_collection_channels(col_id)

    text_msg = text("novastat_col_view_title").format(collection.name)
    if not channels:
        text_msg += text("novastat_col_view_no_channels")
    else:
        for i, ch in enumerate(channels, 1):
            text_msg += f"{i}. {ch.channel_identifier}\n"

    await call.message.edit_text(
        text_msg,
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("NovaStat|col_delete|"))
@safe_handler("NOVASTAT: коллекция — удаление")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_delete_col(call: types.CallbackQuery) -> None:
    """
    Удаление коллекции.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    col_id = int(call.data.split("|")[2])
    await db.novastat.delete_collection(col_id)
    await call.answer(text("novastat_col_delete_success"))
    await call.message.answer(text("main_menu:reload"), reply_markup=Reply.menu())
    await novastat_collections(call)


@router.callback_query(F.data.startswith("NovaStat|col_rename|"))
@safe_handler("NOVASTAT: коллекция — старт переименования")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_rename_col_start(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Начало переименования коллекции.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    col_id = int(call.data.split("|")[2])
    await state.update_data(col_id=col_id)
    await call.message.answer(text("novastat_col_rename_enter_name"))
    await state.set_state(NovaStatStates.waiting_for_rename_collection)
    await call.answer()


@router.message(NovaStatStates.waiting_for_rename_collection)
@safe_handler("NOVASTAT: коллекция — завершение переименования")
async def novastat_rename_col_finish(message: types.Message, state: FSMContext) -> None:
    """
    Завершение переименования коллекции.

    Аргументы:
        message (types.Message): Сообщение с новым названием.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    col_id = data["col_id"]
    new_name = message.text
    await db.novastat.rename_collection(col_id, new_name)
    await message.answer(text("novastat_col_rename_success").format(new_name))

    collection = await db.novastat.get_collection(col_id)
    channels = await db.novastat.get_collection_channels(col_id)

    text_msg = text("novastat_col_view_title").format(collection.name)
    if not channels:
        text_msg += text("novastat_col_view_no_channels")
    else:
        for i, ch in enumerate(channels, 1):
            text_msg += f"{i}. {ch.channel_identifier}\n"

    await message.answer(
        text_msg,
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML",
    )
    # Перезагрузка главного меню
    await message.answer(text("main_menu:reload"), reply_markup=Reply.menu())
    await state.clear()


@router.callback_query(F.data.startswith("NovaStat|col_add_channel|"))
@safe_handler("NOVASTAT: коллекция — старт добавления каналов")
async def novastat_add_channel_start(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Начало добавления каналов в коллекцию.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    col_id = int(call.data.split("|")[2])
    await state.update_data(col_id=col_id)
    await call.message.answer(text("novastat_col_add_ch_enter_identifiers"))
    await state.set_state(NovaStatStates.waiting_for_channel_to_add)
    await call.answer()


@router.message(NovaStatStates.waiting_for_channel_to_add)
@safe_handler("NOVASTAT: коллекция — завершение добавления каналов")
async def novastat_add_channel_finish(
    message: types.Message, state: FSMContext
) -> None:
    """
    Завершение добавления каналов в коллекцию.

    Аргументы:
        message (types.Message): Сообщение со списком каналов.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    col_id = data["col_id"]

    text_lines = message.text.strip().split("\n")
    channels_to_add = [line.strip() for line in text_lines if line.strip()]

    if not channels_to_add:
        await message.answer(text("novastat_col_add_ch_invalid"))
        return

    # Проверка лимита
    existing = await db.novastat.get_collection_channels(col_id)
    if len(existing) + len(channels_to_add) > 100:
        await message.answer(
            text("novastat_col_add_ch_limit_exceeded").format(
                len(existing), len(channels_to_add), 100 - len(existing)
            )
        )
        return

    added_count = 0
    for identifier in channels_to_add:
        await db.novastat.add_channel_to_collection(col_id, identifier)
        added_count += 1

    await message.answer(text("novastat_col_add_ch_success").format(added_count))

    # Возврат к просмотру коллекции
    collection = await db.novastat.get_collection(col_id)
    channels = await db.novastat.get_collection_channels(col_id)

    text_msg = text("novastat_col_view_title").format(collection.name)
    if not channels:
        text_msg += text("novastat_col_view_no_channels")
    else:
        for i, ch in enumerate(channels, 1):
            text_msg += f"{i}. {ch.channel_identifier}\n"

    await message.answer(
        text_msg,
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML",
    )
    # Перезагрузка главного меню
    await message.answer(text("main_menu:reload"), reply_markup=Reply.menu())
    await state.clear()


@router.callback_query(F.data.startswith("NovaStat|col_del_channel_list|"))
@safe_handler("NOVASTAT: коллекция — список на удаление")
async def novastat_del_channel_list(call: types.CallbackQuery) -> None:
    """
    Показ списка каналов для удаления из коллекции.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    col_id = int(call.data.split("|")[2])
    channels = await db.novastat.get_collection_channels(col_id)
    await call.message.edit_text(
        text("novastat_col_del_ch_select"),
        reply_markup=InlineNovaStat.collection_channels_delete(col_id, channels),
    )


@router.callback_query(F.data.startswith("NovaStat|col_del_channel|"))
@safe_handler("NOVASTAT: коллекция — удаление канала")
async def novastat_del_channel(call: types.CallbackQuery) -> None:
    """
    Удаление конкретного канала из коллекции.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    parts = call.data.split("|")
    col_id = int(parts[2])
    channel_db_id = int(parts[3])

    await db.novastat.remove_channel_from_collection(channel_db_id)
    await call.answer(text("novastat_col_del_ch_success"))

    # Обновление списка
    channels = await db.novastat.get_collection_channels(col_id)
    await call.message.edit_reply_markup(
        reply_markup=InlineNovaStat.collection_channels_delete(col_id, channels)
    )
    # Перезагрузка главного меню
    await call.message.answer(text("main_menu:reload"), reply_markup=Reply.menu())


# --- Логика анализа ---
async def process_analysis(
    message: types.Message, channels: List[str], state: FSMContext
) -> None:
    """
    Запуск процесса анализа списка каналов.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        channels (List[str]): Список идентификаторов каналов.
        state (FSMContext): Контекст состояния.
    """
    settings = await db.novastat.get_novastat_settings(message.from_user.id)
    depth = settings.depth_days

    if len(channels) > MAX_CHANNELS_SYNC:
        await message.answer(text("novastat_analysis_background_started").format(len(channels)))
        asyncio.create_task(run_analysis_background(message, channels, depth, state))
    else:
        status_msg = await message.answer(
            text("novastat_analysis_sync_started").format(len(channels), depth),
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
        await run_analysis_logic(message, channels, depth, state, status_msg)


@safe_handler(
    "NOVASTAT: фоновый анализ"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def run_analysis_background(
    message: types.Message, channels: List[str], depth: int, state: FSMContext
) -> None:
    """
    Фоновая задача анализа (обертка над логикой).

    Аргументы:
        message (types.Message): Сообщение пользователя.
        channels (List[str]): Список каналов.
        depth (int): Глубина анализа.
        state (FSMContext): Контекст состояния.
    """
    await run_analysis_logic(message, channels, depth, state, None)


def _format_stats_body(stats: Dict[str, Any]) -> str:
    """
    Форматирование тела статистики для отчета.

    Аргументы:
        stats (Dict[str, Any]): Данные статистики.

    Возвращает:
        str: Отформатированная строка HTML.
    """
    link = stats.get("link")
    title_link = (
        f"<a href='{link}'>{html.escape(stats['title'])}</a>"
        if link
        else html.escape(stats["title"])
    )

    return text("novastat_analysis_channel_body_main").format(
        title_link,
        stats["subscribers"],
        stats["views"].get(24, 0),
        stats["views"].get(48, 0),
        stats["views"].get(72, 0),
        stats["er"].get(24, 0),
        stats["er"].get(48, 0),
        stats["er"].get(72, 0),
    )


async def run_analysis_logic(
    message: types.Message,
    channels: List[str],
    depth: int,
    state: FSMContext,
    status_msg: Optional[types.Message] = None,
) -> None:
    """
    Основная логика анализа каналов.
    Выполняет запросы параллельно, агрегирует результаты и отправляет отчеты.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        channels (List[str]): Список каналов.
        depth (int): Глубина анализа.
        state (FSMContext): Контекст состояния.
        status_msg (Optional[types.Message]): Сообщение статуса для обновления/удаления.
    """
    total_views = {24: 0, 48: 0, 72: 0}
    total_er = {24: 0.0, 48: 0.0, 72: 0.0}
    total_subs = 0
    valid_count = 0
    results = []

    # Семафор для ограничения нагрузки
    sem = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

    async def _analyze_channel(idx: int, ch: str):
        """Вспомогательная функция для одного канала."""
        async with sem:
            try:
                stats = await novastat_service.collect_stats(
                    ch, depth, horizon=24, bot=message.bot
                )
                return idx, ch, stats, None
            except Exception as e:
                return idx, ch, None, e

    # Запускаем параллельно
    tasks = [_analyze_channel(i, ch) for i, ch in enumerate(channels, 1)]
    analysis_results = await asyncio.gather(*tasks)

    # Обрабатываем результаты по порядку
    for i, ch, stats, error in sorted(analysis_results, key=lambda x: x[0]):
        if stats:
            valid_count += 1
            results.append(stats)

            # Отправка индивидуального отчета (если каналов > 1)
            if len(channels) > 1:
                ind_report = text("novastat_analysis_report_header_ind").format(
                    i, len(channels)
                )
                ind_report += _format_stats_body(stats)
                try:
                    await message.answer(
                        ind_report,
                        parse_mode="HTML",
                        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                    )
                except Exception:
                    logger.error("Не удалось отправить отчет для %s", ch)

            # Агрегация данных
            total_subs += stats.get("subscribers", 0)
            for h in HOURS_TO_ANALYZE:
                total_views[h] = total_views.get(h, 0) + stats.get("views", {}).get(
                    h, 0
                )
                total_er[h] = total_er.get(h, 0) + stats.get("er", {}).get(h, 0)

        else:
            # Обработка ошибки
            error_reason = "Неизвестная ошибка"
            cache = await db.novastat_cache.get_cache(str(ch), 24)
            if cache and cache.error_message:
                error_reason = cache.error_message
            elif error:
                error_reason = str(error)

            logger.warning("Ошибка анализа канала %s: %s", ch, error_reason)

            error_text = text("novastat_analysis_error_collect").format(
                html.escape(str(ch))
            )
            error_text += "\n" + text("novastat_analysis_error_reason").format(
                html.escape(error_reason)
            )

            await message.answer(
                error_text,
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            )

    # Удаление начального статуса
    if status_msg:
        try:
            await status_msg.delete()
        except TelegramBadRequest:
            pass

    if valid_count == 0:
        await message.answer(text("novastat_analysis_error_all_failed"))
        return

    # Подготовка сводки
    summary_views = total_views
    summary_er = {h: round(total_er[h] / valid_count, 2) for h in HOURS_TO_ANALYZE}

    # Сохранение для CPM
    await state.update_data(last_analysis_views=summary_views)

    if len(channels) == 1:
        # Один канал: это и есть отчет.
        stats = results[0]

        single_info = {
            "title": stats["title"],
            "username": stats["username"],
            "link": stats.get("link"),
            "subscribers": stats["subscribers"],
        }
        await state.update_data(single_channel_info=single_info)

        report = text("novastat_analysis_report_header_summary")
        report += _format_stats_body(stats)

        await message.answer(
            report,
            reply_markup=InlineNovaStat.analysis_result(),
            parse_mode="HTML",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
        # Подгружаем главное меню
        await message.answer(text("novastat_analysis_caption"), reply_markup=Reply.menu())

    else:
        # Сводка
        await state.update_data(single_channel_info=None)

        report = text("novastat_analysis_report_header_summary_multi").format(
            valid_count
        )
        report += text("novastat_analysis_summary_subs").format(total_subs)
        report += text("novastat_analysis_summary_views").format(
            summary_views[24], summary_views[48], summary_views[72]
        )
        report += text("novastat_analysis_summary_er").format(
            summary_er[24], summary_er[48], summary_er[72]
        )

        await message.answer(
            report,
            reply_markup=InlineNovaStat.analysis_result(),
            parse_mode="HTML",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
        # Подгружаем главное меню
        await message.answer(
            text("novastat_analysis_caption_multi"), reply_markup=Reply.menu()
        )


@router.message(NovaStatStates.waiting_for_channels)
@safe_handler("NOVASTAT: анализ текста")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_analyze_text(message: types.Message, state: FSMContext) -> None:
    """
    Обработка ввода списка каналов текстом.

    Аргументы:
        message (types.Message): Сообщение с каналами.
        state (FSMContext): Контекст состояния.
    """
    text_lines = message.text.strip().split("\n")
    channels = [line.strip() for line in text_lines if line.strip()]

    if not channels:
        await message.answer(text("novastat_col_add_ch_invalid"))
        return

    if len(channels) > 12:
        await message.answer(text("novastat_analysis_text_limit_exceeded"))
        return

    await process_analysis(message, channels, state)


@router.callback_query(F.data.startswith("NovaStat|col_analyze|"))
@safe_handler("NOVASTAT: анализ коллекции")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_analyze_collection(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Запуск анализа для всей коллекции.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    col_id = int(call.data.split("|")[2])
    channels_db = await db.novastat.get_collection_channels(col_id)

    if not channels_db:
        await call.answer(text("novastat_analysis_col_no_channels"), show_alert=True)
        return

    channels = [ch.channel_identifier for ch in channels_db]
    await call.answer()
    await process_analysis(call.message, channels, state)


# --- Расчет CPM ---
@router.callback_query(F.data == "NovaStat|calc_cpm_start")
@safe_handler(
    "NOVASTAT: CPM — старт"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_cpm_start(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Запуск калькулятора CPM (выбор цены).

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await call.message.edit_text(
        "Выберите CPM (стоимость за 1000 просмотров) кнопкой ниже\n"
        "или отправьте своё значение числом.",
        reply_markup=InlineNovaStat.cpm_choice(),
    )
    await state.set_state(NovaStatStates.waiting_for_cpm)
    await call.answer()


async def calculate_and_show_price(
    message: types.Message,
    cpm: int,
    state: FSMContext,
    user_id: int,
    is_edit: bool = False,
) -> None:
    """
    Расчет стоимости рекламы по CPM.

    Аргументы:
        message (types.Message): Сообщение для ответа/редактирования.
        cpm (int): Значение CPM (Cost Per Mille).
        state (FSMContext): Контекст состояния.
        user_id (int): ID пользователя.
        is_edit (bool): Если True, редактирует сообщение, иначе отправляет новое.
    """
    data = await state.get_data()
    views = data.get("last_analysis_views")
    single_info = data.get("single_channel_info")

    if not views:
        if is_edit:
            await message.edit_text(text("novastat_cpm_error_outdated"))
        else:
            await message.answer(text("novastat_cpm_error_outdated"))
        return

    # Получение курса валют пользователя
    user = await db.user.get_user(user_id)
    if user and user.default_exchange_rate_id:
        exchange_rate_obj = await db.exchange_rate.get_exchange_rate(
            user.default_exchange_rate_id
        )
        rate = exchange_rate_obj.rate if exchange_rate_obj else 100.0
    else:
        rate = 100.0

    price_rub = {}
    for h in HOURS_TO_ANALYZE:
        # Обработка возможных строковых ключей из JSON сериализации
        val = views.get(h) or views.get(str(h)) or 0
        price_rub[h] = int((val / 1000) * cpm)

    price_usdt = {h: round(price_rub[h] / rate, 2) for h in HOURS_TO_ANALYZE}

    date_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")

    report = text("novastat_cpm_report_header").format(cpm)

    if single_info:
        link = single_info.get("link")
        title_link = (
            f"<a href='{link}'>{html.escape(single_info['title'])}</a>"
            if link
            else html.escape(single_info["title"])
        )
        report += text("novastat_cpm_channel_info").format(
            title_link, single_info["subscribers"]
        )

    report += f"├ 24 часа: {price_rub[24]:,} руб. / {price_usdt[24]} usdt\n".replace(
        ",", " "
    )
    report += f"├ 48 часов: {price_rub[48]:,} руб. / {price_usdt[48]} usdt\n".replace(
        ",", " "
    )
    report += f"└ 72 часа: {price_rub[72]:,} руб. / {price_usdt[72]} usdt\n".replace(
        ",", " "
    ).replace(".", ",")

    report += text("novastat_cpm_expected_views").format(
        views.get(24) or views.get("24") or 0,
        views.get(48) or views.get("48") or 0,
        views.get(72) or views.get("72") or 0,
    )

    report += text("novastat_cpm_date_calc").format(date_str)

    # Добавляем подписи
    report += await get_report_signatures(user, "cpm", message.bot)

    if is_edit:
        await message.edit_text(
            report,
            reply_markup=InlineNovaStat.cpm_result(),
            parse_mode="HTML",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
    else:
        await message.answer(
            report,
            reply_markup=InlineNovaStat.cpm_result(),
            parse_mode="HTML",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )

    # Подгружаем главное меню после расчета CPM
    await message.answer(text("novastat_cpm_finished"), reply_markup=Reply.menu())


@router.callback_query(F.data.startswith("NovaStat|calc_cpm|"))
@safe_handler(
    "NOVASTAT: CPM — выбор значения"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_cpm_cb(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Выбор значения CPM из предустановленных вариантов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    cpm = int(call.data.split("|")[2])
    await calculate_and_show_price(
        call.message, cpm, state, call.from_user.id, is_edit=True
    )
    await call.answer()


@router.message(NovaStatStates.waiting_for_cpm)
@safe_handler(
    "NOVASTAT: CPM — ввод текста"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_cpm_text(message: types.Message, state: FSMContext) -> None:
    """
    Ввод значения CPM текстом.

    Аргументы:
        message (types.Message): Сообщение со значением CPM.
        state (FSMContext): Контекст состояния.
    """
    try:
        cpm = int(message.text.strip())
        await calculate_and_show_price(message, cpm, state, message.from_user.id)
    except ValueError:
        await message.answer(text("novastat_cpm_invalid_input"))


# --- My Channels Selection ---
@router.callback_query(F.data == "NovaStat|my_channels")
@safe_handler(
    "NOVASTAT: выбор моих каналов"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_my_channels(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Открытие меню выбора собственных каналов для анализа.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    view_mode = await get_user_view_mode(call.from_user.id)

    # Если view_mode == 'channels', просто грузим все каналы
    # Иначе грузим без папок + папки (как было)
    if view_mode == "channels":
        channels = await db.channel.get_user_channels(user_id=call.from_user.id)
        folders = []
    else:
        raw_folders = await db.user_folder.get_folders(user_id=call.from_user.id)
        # В режиме папок скрываем каналы без папок (как в постинге) и пустые папки
        folders = [f for f in raw_folders if f.content]
        channels = []

    await state.update_data(chosen=[], chosen_folders=[], current_folder_id=None)

    try:
        await call.message.edit_text(
            text("choice_channels:novastat").format(0, ""),
            reply_markup=keyboards.choice_objects(
                resources=channels,
                chosen=[],
                folders=folders,
                data="ChoiceNovaStatChannels",
                view_mode=view_mode,
            ),
        )
    except TelegramBadRequest:
        pass

    await state.set_state(NovaStatStates.choosing_my_channels)


@router.callback_query(F.data.startswith("ChoiceNovaStatChannels"))
@safe_handler(
    "NOVASTAT: обработка выбора каналов"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def novastat_choice_channels(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Обработчик выбора каналов/папок в меню "Мои каналы".
    Поддерживает пагинацию, вход в папки, переключение вида.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer("Ошибка: данные состояния потеряны")
        return await call.message.delete()

    chosen: list = data.get("chosen", [])
    current_folder_id = data.get("current_folder_id")

    view_mode = await get_user_view_mode(call.from_user.id)

    # Переключение вида
    if temp[1] == "switch_view":
        view_mode = "channels" if view_mode == "folders" else "folders"
        await set_user_view_mode(call.from_user.id, view_mode)
        if view_mode == "channels":
            await state.update_data(current_folder_id=None)
            current_folder_id = None

        # Сбрасываем пагинацию
        temp = list(temp)
        if len(temp) > 2:
            temp[2] = "0"
        else:
            temp.append("0")

    # Determine objects
    if view_mode == "channels":
        objects = await db.channel.get_user_channels(user_id=call.from_user.id)
        folders = []
    elif current_folder_id:
        folder = await db.user_folder.get_folder_by_id(current_folder_id)
        objects = []
        if folder and folder.content:
            chat_ids = [int(chat_id) for chat_id in folder.content]
            # Оптимизация: получаем все каналы папки одним запросом
            objects = await db.channel.get_user_channels(
                user_id=call.from_user.id, from_array=chat_ids
            )
        folders = []
    else:
        objects = await db.channel.get_user_channels_without_folders(
            user_id=call.from_user.id
        )
        raw_folders = await db.user_folder.get_folders(user_id=call.from_user.id)
        folders = [f for f in raw_folders if f.content]

    # NEXT STEP (Analyze)
    if temp[1] == "next_step":
        if not chosen:
            return await call.answer("Выберите хотя бы один канал", show_alert=True)

        real_chosen = []
        for cid in chosen:
            ch = await db.channel.get_channel_by_chat_id(cid)
            if ch:
                real_chosen.append(ch.chat_id)

        await process_analysis(call.message, real_chosen, state)
        return

    # CANCEL
    if temp[1] == "cancel":
        if current_folder_id:
            await state.update_data(current_folder_id=None)
            objects = await db.channel.get_user_channels_without_folders(
                user_id=call.from_user.id
            )
            raw_folders = await db.user_folder.get_folders(user_id=call.from_user.id)
            folders = [f for f in raw_folders if f.content]
            # Reset pagination
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = "0"
            else:
                temp.append("0")
        else:
            return await novastat_main_cb(call, state)

    # PAGINATION
    if temp[1] in ["next", "back"]:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                remover=int(temp[2]),
                data="ChoiceNovaStatChannels",
                view_mode=view_mode,
            )
        )

    # CHOICE ALL
    if temp[1] == "choice_all":
        current_ids = [i.chat_id for i in objects]
        all_selected = all(cid in chosen for cid in current_ids)

        if all_selected:
            for cid in current_ids:
                if cid in chosen:
                    chosen.remove(cid)
        else:
            for cid in current_ids:
                if cid not in chosen:
                    chosen.append(cid)

    # SELECT ITEM/FOLDER
    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])
        resource_type = temp[3] if len(temp) > 3 else None

        if resource_type == "folder":
            await state.update_data(current_folder_id=resource_id)
            folder = await db.user_folder.get_folder_by_id(resource_id)
            objects = []
            if folder and folder.content:
                chat_ids = [int(chat_id) for chat_id in folder.content]
                # Оптимизация: получаем все каналы папки одним запросом
                objects = await db.channel.get_user_channels(
                    user_id=call.from_user.id, from_array=chat_ids
                )
            folders = []
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = "0"
            else:
                temp.append("0")
        else:
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                chosen.append(resource_id)

    await state.update_data(chosen=chosen)

    # Display logic for formatted list of chosen channels
    display_objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, from_array=chosen[:10]
    )

    if chosen:
        channels_list = (
            "<blockquote expandable>"
            + "\n".join(
                text("resource_title").format(obj.title) for obj in display_objects
            )
            + "</blockquote>"
        )
    else:
        channels_list = ""

    remover_val = (
        int(temp[2])
        if temp[1] in ["choice_all", "next", "back"]
        or temp[1].replace("-", "").isdigit()
        else 0
    )

    try:
        await call.message.edit_text(
            text("choice_channels:novastat").format(len(chosen), channels_list),
            reply_markup=keyboards.choice_objects(
                resources=(
                    display_objects if view_mode == "channels" else objects
                ),  # If generic logic, resources should be passed correctly
                chosen=chosen,
                folders=folders,
                remover=remover_val,
                data="ChoiceNovaStatChannels",
                view_mode=view_mode,
            ),
        )
    except TelegramBadRequest:
        pass
