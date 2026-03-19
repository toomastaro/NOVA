"""
Обработчики функционала NOVAстат.

Модуль предоставляет:
- Быструю аналитику Telegram-каналов (просмотры, ER)
- Управление коллекциями каналов
- Расчет стоимости рекламы по CPM
- Настройки глубины анализа
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.utils.novastat import novastat_service
from main_bot.utils.lang.language import text

logger = logging.getLogger(__name__)
router = Router()

# Константы
MAX_CHANNELS_SYNC = 5  # Максимум каналов для синхронной обработки
HOURS_TO_ANALYZE = [24, 48, 72]  # Временные интервалы для анализа
MAX_PARALLEL_REQUESTS = 5  # Максимум параллельных запросов к Telegram API
STATUS_UPDATE_INTERVAL = 3  # Минимальный интервал обновления статуса (секунды)


class NovaStatStates(StatesGroup):
    waiting_for_channels = State()
    waiting_for_collection_name = State()
    waiting_for_rename_collection = State()
    waiting_for_channel_to_add = State()
    waiting_for_cpm = State()


# --- Entry Point ---
@router.message(F.text == text("reply_menu:novastat"))
async def novastat_main(message: types.Message, state: FSMContext) -> None:
    """
    Входная точка в меню NOVAстат.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния FSM.
    """
    await state.clear()
    await message.answer(
        "<b>Быстрая аналитика канала!</b>\n"
        "Просто пришлите ссылку на свой телеграм-канал.\n"
        "Если канал приватный, то отправьте ссылку с автоприёмом, чтобы бот смог её открыть.",
        reply_markup=keyboards.main_menu(),
        parse_mode="HTML",
    )
    await state.set_state(NovaStatStates.waiting_for_channels)


@router.callback_query(F.data == "NovaStat|main")
async def novastat_main_cb(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Возврат в главное меню NOVAстат через callback.
    """
    await state.clear()
    await call.message.edit_text(
        "<b>Быстрая аналитика канала!</b>\n"
        "Просто пришлите ссылку на свой телеграм-канал.\n"
        "Если канал приватный, то отправьте ссылку с автоприёмом, чтобы бот смог её открыть.",
        reply_markup=keyboards.main_menu(),
        parse_mode="HTML",
    )
    await state.set_state(NovaStatStates.waiting_for_channels)


@router.callback_query(F.data == "NovaStat|exit")
async def novastat_exit(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Выход из режима NOVAстат в главное меню бота.
    """
    await state.clear()
    await call.message.delete()
    await call.message.answer(text("start_text"), reply_markup=keyboards.menu(call.from_user.id))


# --- Settings ---
@router.callback_query(F.data == "NovaStat|settings")
async def novastat_settings(call: types.CallbackQuery) -> None:
    """
    Отображение настроек NOVAстат.
    """
    settings = await db.novastat.get_novastat_settings(call.from_user.id)
    await call.message.edit_text(
        f"<b>Настройки NOVAстат</b>\n\n"
        f"Текущая глубина анализа: {settings.depth_days} дней.\n"
        f"Выберите новое значение:",
        reply_markup=keyboards.settings(settings.depth_days),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("NovaStat|set_depth|"))
async def novastat_set_depth(call: types.CallbackQuery) -> None:
    """
    Установка глубины анализа (дней).
    """
    depth = int(call.data.split("|")[2])
    await db.novastat.update_novastat_settings(call.from_user.id, depth_days=depth)
    await call.answer(f"Глубина анализа обновлена: {depth} дней")

    await call.answer(f"Глубина анализа обновлена: {depth} дней")

    # Обновление вида
    settings = await db.novastat.get_novastat_settings(call.from_user.id)
    await call.message.edit_text(
        f"<b>Настройки NOVAстат</b>\n\n"
        f"Текущая глубина анализа: {settings.depth_days} дней.\n"
        f"Выберите новое значение:",
        reply_markup=keyboards.settings(settings.depth_days),
        parse_mode="HTML",
    )


# --- Collections ---
@router.callback_query(F.data == "NovaStat|collections")
async def novastat_collections(call: types.CallbackQuery) -> None:
    """
    Отображение списка коллекций каналов пользователя.
    """
    collections = await db.novastat.get_collections(call.from_user.id)
    if not collections:
        await call.message.edit_text(
            "У вас пока нет коллекций каналов.\n"
            "Создайте первую коллекцию, чтобы быстро получать аналитику.",
            reply_markup=keyboards.collections_list([]),
        )
    else:
        text_list = "<b>Ваши коллекции:</b>\n"
        text_list = "<b>Ваши коллекции:</b>\n"
        # Нам нужно получить количество каналов для каждой коллекции, чтобы отобразить правильно
        # Пока просто перечисляем имена
        for i, col in enumerate(collections, 1):
            text_list += f"{i}. {col.name}\n"

        await call.message.edit_text(
            text_list,
            reply_markup=keyboards.collections_list(collections),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "NovaStat|col_create")
async def novastat_create_col_start(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Начало создания новой коллекции.
    """
    await call.message.answer("Введите название для новой коллекции:")
    await state.set_state(NovaStatStates.waiting_for_collection_name)
    await call.answer()


@router.message(NovaStatStates.waiting_for_collection_name)
async def novastat_create_col_finish(message: types.Message, state: FSMContext) -> None:
    """
    Завершение создания коллекции (сохранение названия).
    """
    name = message.text
    await db.novastat.create_collection(message.from_user.id, name)
    await message.answer(f"Коллекция '{name}' создана!")

    await message.answer(f"Коллекция '{name}' создана!")

    # Возврат к списку коллекций
    collections = await db.novastat.get_collections(message.from_user.id)
    await message.answer(
        "Ваши коллекции:", reply_markup=keyboards.collections_list(collections)
    )
    await state.clear()


@router.callback_query(F.data.startswith("NovaStat|col_open|"))
async def novastat_open_col(call: types.CallbackQuery) -> None:
    """
    Открытие коллекции для просмотра списка каналов и действий.
    """
    col_id = int(call.data.split("|")[2])
    collection = await db.novastat.get_collection(col_id)
    channels = await db.novastat.get_collection_channels(col_id)

    text_msg = f"<b>Коллекция: {collection.name}</b>\n\n"
    if not channels:
        text_msg += "В коллекции пока нет каналов."
    else:
        for i, ch in enumerate(channels, 1):
            text_msg += f"{i}. {ch.channel_identifier}\n"

    await call.message.edit_text(
        text_msg,
        reply_markup=keyboards.collection_view(collection, channels),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("NovaStat|col_delete|"))
async def novastat_delete_col(call: types.CallbackQuery) -> None:
    """
    Удаление коллекции.
    """
    col_id = int(call.data.split("|")[2])
    await db.novastat.delete_collection(col_id)
    await call.answer("Коллекция удалена")
    await novastat_collections(call)


@router.callback_query(F.data.startswith("NovaStat|col_rename|"))
async def novastat_rename_col_start(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Начало переименования коллекции.
    """
    col_id = int(call.data.split("|")[2])
    await state.update_data(col_id=col_id)
    await call.message.answer("Введите новое название коллекции:")
    await state.set_state(NovaStatStates.waiting_for_rename_collection)
    await call.answer()


@router.message(NovaStatStates.waiting_for_rename_collection)
async def novastat_rename_col_finish(message: types.Message, state: FSMContext) -> None:
    """
    Завершение переименования коллекции.
    """
    data = await state.get_data()
    col_id = data["col_id"]
    new_name = message.text
    await db.novastat.rename_collection(col_id, new_name)
    await message.answer(f"Коллекция переименована в '{new_name}'")

    await message.answer(f"Коллекция переименована в '{new_name}'")

    # Возврат к просмотру коллекции
    # Нам нужно вручную вызвать обновление вида или отправить новое сообщение
    # Отправить новое сообщение проще
    collection = await db.novastat.get_collection(col_id)
    channels = await db.novastat.get_collection_channels(col_id)

    text_msg = f"<b>Коллекция: {collection.name}</b>\n\n"
    if not channels:
        text_msg += "В коллекции пока нет каналов."
    else:
        for i, ch in enumerate(channels, 1):
            text_msg += f"{i}. {ch.channel_identifier}\n"

    await message.answer(
        text_msg,
        reply_markup=keyboards.collection_view(collection, channels),
        parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(F.data.startswith("NovaStat|col_add_channel|"))
async def novastat_add_channel_start(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Начало добавления канала в коллекцию.
    """
    col_id = int(call.data.split("|")[2])
    await state.update_data(col_id=col_id)
    await call.message.answer(
        "Пришлите ссылку на канал или @username (можно списком, каждый с новой строки):"
    )
    await state.set_state(NovaStatStates.waiting_for_channel_to_add)
    await call.answer()


@router.message(NovaStatStates.waiting_for_channel_to_add)
async def novastat_add_channel_finish(
    message: types.Message, state: FSMContext
) -> None:
    """
    Завершение добавления канала(ов) в коллекцию.
    """
    data = await state.get_data()
    col_id = data["col_id"]

    text_lines = message.text.strip().split("\n")
    channels_to_add = [line.strip() for line in text_lines if line.strip()]

    if not channels_to_add:
        await message.answer("Не удалось распознать каналы. Попробуйте еще раз.")
        return

    added_count = 0
    for identifier in channels_to_add:
        # Здесь можно добавить простую валидацию или обработку ошибок, если нужно
        await db.novastat.add_channel_to_collection(col_id, identifier)
        added_count += 1

    await message.answer(f"Добавлено каналов: {added_count}")

    # Возврат к просмотру коллекции
    collection = await db.novastat.get_collection(col_id)
    channels = await db.novastat.get_collection_channels(col_id)

    text_msg = f"<b>Коллекция: {collection.name}</b>\n\n"
    if not channels:
        text_msg += "В коллекции пока нет каналов."
    else:
        for i, ch in enumerate(channels, 1):
            text_msg += f"{i}. {ch.channel_identifier}\n"

    await message.answer(
        text_msg,
        reply_markup=keyboards.collection_view(collection, channels),
        parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(F.data.startswith("NovaStat|col_del_channel_list|"))
async def novastat_del_channel_list(call: types.CallbackQuery) -> None:
    """
    Отображение списка каналов для удаления из коллекции.
    """
    col_id = int(call.data.split("|")[2])
    channels = await db.novastat.get_collection_channels(col_id)
    await call.message.edit_text(
        "Выберите канал для удаления:",
        reply_markup=keyboards.collection_channels_delete(col_id, channels),
    )


@router.callback_query(F.data.startswith("NovaStat|col_del_channel|"))
async def novastat_del_channel(call: types.CallbackQuery) -> None:
    """
    Удаление выбранного канала из коллекции.
    """
    parts = call.data.split("|")
    col_id = int(parts[2])
    channel_db_id = int(parts[3])

    await db.novastat.remove_channel_from_collection(channel_db_id)
    await call.answer("Канал удален")

    await call.answer("Канал удален")

    # Обновление списка
    channels = await db.novastat.get_collection_channels(col_id)
    await call.message.edit_reply_markup(
        reply_markup=keyboards.collection_channels_delete(col_id, channels)
    )


# --- Analysis Logic ---
async def process_analysis(
    message: types.Message, channels: List[str], state: FSMContext
) -> None:
    """
    Запускает анализ каналов (синхронно или в фоне в зависимости от количества).

    Если каналов > MAX_CHANNELS_SYNC, запускается фоновая задача.

    Аргументы:
        message (types.Message): Сообщение пользователя для ответа.
        channels (List[str]): Список идентификаторов каналов (username/ссылки).
        state (FSMContext): Контекст состояния.
    """
    settings = await db.novastat.get_novastat_settings(message.from_user.id)
    depth = settings.depth_days

    if len(channels) > MAX_CHANNELS_SYNC:
        await message.answer(
            f"⏳ Запущена фоновая обработка {len(channels)} каналов.\n"
            "Это займет некоторое время. Я пришлю отчет, когда закончу."
        )
        asyncio.create_task(run_analysis_background(message, channels, depth, state))
    else:
        status_msg = await message.answer(
            f"⏳ Начинаю анализ {len(channels)} каналов (глубина {depth} дн.)...",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
        await run_analysis_logic(message, channels, depth, state, status_msg)


async def run_analysis_background(
    message: types.Message, channels: List[str], depth: int, state: FSMContext
) -> None:
    """
    Фоновая обработка анализа большого количества каналов.

    Используется для >MAX_CHANNELS_SYNC каналов, чтобы не блокировать бота.
    """
    try:
        await run_analysis_logic(message, channels, depth, state, None)
    except Exception:
        logger.exception(
            "Фоновый анализ завершился ошибкой для пользователя %s",
            message.from_user.id,
        )
        # Лучше не спамить пользователю об ошибках фона, если он уже ушел,
        # но в рамках MVP можно уведомить
        if message.chat.id:
            try:
                await message.answer(
                    "❌ Произошла внутренняя ошибка при анализе. Попробуйте позже."
                )
            except Exception:
                pass


async def run_analysis_logic(
    message: types.Message,
    channels: List[str],
    depth: int,
    state: FSMContext,
    status_msg: Optional[types.Message] = None,
) -> None:
    """
    Основная логика анализа каналов.

    Этапы:
    1. Проверка доступа к каналам (параллельно)
    2. Сбор статистики (параллельно с ограничением)
    3. Формирование и отправка отчета

    Аргументы:
        message (types.Message): Исходное сообщение.
        channels (List[str]): Список каналов.
        depth (int): Глубина анализа в днях.
        state (FSMContext): Контекст состояния.
        status_msg (Optional[types.Message]): Сообщение для обновления статуса.
    """
    # Используем одну сессию клиента для всего процесса анализа
    async with novastat_service.get_client() as client:
        # 1. Проверка доступа (параллельно)
        valid_entities = []
        failed = []

        total_channels = len(channels)

        if status_msg:
            await status_msg.edit_text(
                f"🔍 Проверяю доступ к {total_channels} каналам...",
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            )

        # Параллельная проверка доступа
        access_tasks = [
            novastat_service.check_access(ch, client=client) for ch in channels
        ]
        access_results = await asyncio.gather(*access_tasks, return_exceptions=True)

        for ch, result in zip(channels, access_results):
            if isinstance(result, Exception):
                logger.warning("Ошибка проверки доступа к каналу %s: %s", ch, result)
                failed.append(ch)
            elif result:
                valid_entities.append((ch, result))
            else:
                failed.append(ch)

        if not valid_entities:
            text_err = (
                "❌ Не удалось получить доступ ни к одному каналу.\n"
                "Скорее всего, ссылки без автоприёма или у бота нет прав доступа."
            )
            if status_msg:
                await status_msg.edit_text(
                    text_err,
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                )
            else:
                await message.answer(
                    text_err,
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                )
            return

        if status_msg:
            await status_msg.edit_text(
                f"✅ Доступ есть к {len(valid_entities)} каналам. Собираю статистику...",
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            )

        # 2. Сбор статистики (параллельно с ограничением)
        results = []

        # Семафор для ограничения количества одновременных запросов
        sem = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

        async def collect_with_limit(ch_id, entity):
            """Сбор статистики с ограничением параллельных запросов."""
            async with sem:
                return await novastat_service.collect_stats(ch_id, depth, client=client)

        # Параллельный сбор статистики
        stats_tasks = [
            collect_with_limit(ch_id, entity) for ch_id, entity in valid_entities
        ]
        stats_results = await asyncio.gather(*stats_tasks, return_exceptions=True)

        for (ch_id, entity), result in zip(valid_entities, stats_results):
            if isinstance(result, Exception):
                logger.warning("Ошибка сбора статистики канала %s: %s", ch_id, result)
                failed.append(ch_id)
            elif result:
                results.append(result)
            else:
                failed.append(ch_id)

    # 3. Анализ
    if status_msg:
        await status_msg.edit_text(
            "🔄 Анализирую данные...",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )

    # Расчет сумм просмотров и средних значений ER
    total_views = {h: 0 for h in HOURS_TO_ANALYZE}
    total_er = {h: 0.0 for h in HOURS_TO_ANALYZE}
    count = len(results)

    for res in results:
        for h in HOURS_TO_ANALYZE:
            total_views[h] += res["views"][h]
            total_er[h] += res["er"][h]

    # Просмотры суммируются (Итого), ER усредняется
    final_views = total_views
    if count > 0:
        avg_er = {h: round(total_er[h] / count, 2) for h in HOURS_TO_ANALYZE}
    else:
        avg_er = {h: 0.0 for h in HOURS_TO_ANALYZE}

        avg_er = {h: 0.0 for h in HOURS_TO_ANALYZE}

    # Сохранение результатов для расчета CPM
    data_to_store = {"last_analysis_views": final_views}
    if count == 1:
        data_to_store["single_channel_info"] = {
            "title": results[0]["title"],
            "username": results[0]["username"],
            "link": results[0].get("link"),
            "subscribers": results[0]["subscribers"],
        }
    else:
        data_to_store["single_channel_info"] = None

    await state.update_data(**data_to_store)

    report = f"📊 <b>Отчет аналитики ({count} каналов)</b>\n\n"

    if count == 1:
        res = results[0]
        link = res.get("link")
        title_link = f"<a href='{link}'>{res['title']}</a>" if link else res["title"]
        report += f"📢 Канал: {title_link}\n"
        report += f"👥 Подписчиков: {res['subscribers']}\n\n"

    report += "👁️ <b>Суммарные просмотры:</b>\n"
    report += f"├ 24 часа: {final_views[24]}\n"
    report += f"├ 48 часов: {final_views[48]}\n"
    report += f"└ 72 часа: {final_views[72]}\n\n"

    report += "📈 <b>Средний ER:</b>\n"
    report += f"├ 24 часа: {avg_er[24]}%\n"
    report += f"├ 48 часов: {avg_er[48]}%\n"
    report += f"└ 72 часа: {avg_er[72]}%\n\n"

    if failed:
        report += f"⚠️ Не удалось обработать: {len(failed)} каналов.\n"

    # Не удаляем status_msg, чтобы пользователь видел прогресс

    await message.answer(
        report,
        reply_markup=keyboards.analysis_result(),
        parse_mode="HTML",
        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
    )


@router.message(NovaStatStates.waiting_for_channels)
async def novastat_analyze_text(message: types.Message, state: FSMContext) -> None:
    """
    Обработка текстового ввода со списком каналов для анализа.
    """
    text_lines = message.text.strip().split("\n")
    channels = [line.strip() for line in text_lines if line.strip()]

    if not channels:
        await message.answer("Не удалось распознать каналы. Попробуйте еще раз.")
        return

    await process_analysis(message, channels, state)


@router.callback_query(F.data.startswith("NovaStat|col_analyze|"))
async def novastat_analyze_collection(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Запуск анализа для сохраненной коллекции.
    """
    col_id = int(call.data.split("|")[2])
    channels_db = await db.novastat.get_collection_channels(col_id)

    if not channels_db:
        await call.answer("В коллекции нет каналов!", show_alert=True)
        return

    channels = [ch.channel_identifier for ch in channels_db]
    await call.answer()
    await process_analysis(call.message, channels, state)


# --- CPM Calculation ---
@router.callback_query(F.data == "NovaStat|calc_cpm_start")
async def novastat_cpm_start(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Начало калькулятора CPM.
    """
    await call.message.edit_text(
        "Выберите CPM (стоимость за 1000 просмотров) кнопкой ниже\n"
        "или отправьте своё значение числом.",
        reply_markup=keyboards.cpm_choice(),
    )
    await state.set_state(NovaStatStates.waiting_for_cpm)
    await call.answer()


async def calculate_and_show_price(
    message: types.Message, cpm: int, state: FSMContext, is_edit: bool = False
) -> None:
    """
    Расчет и отображение стоимости рекламы на основе CPM и собранной статистики.

    Аргументы:
        message (types.Message): Сообщение для ответа.
        cpm (int): Cost Per Mille.
        state (FSMContext): Контекст состояния.
        is_edit (bool): Если True, редактирует сообщение.
    """
    data = await state.get_data()
    views = data.get("last_analysis_views")
    single_info = data.get("single_channel_info")

    if not views:
        if is_edit:
            await message.edit_text(
                "Данные аналитики устарели. Пожалуйста, проведите анализ заново."
            )
        else:
            await message.answer(
                "Данные аналитики устарели. Пожалуйста, проведите анализ заново."
            )
        return

    price = {h: int((views[h] / 1000) * cpm) for h in HOURS_TO_ANALYZE}

    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    report = f"👛 <b>Стоимость рекламы (CPM {cpm}):</b>\n"

    if single_info:
        link = single_info.get("link")
        title_link = (
            f"<a href='{link}'>{single_info['title']}</a>"
            if link
            else single_info["title"]
        )
        report += f"📢 Канал: {title_link}\n"
        report += f"👥 Подписчиков: {single_info['subscribers']}\n\n"

    report += f"├ 24 часа: {price[24]:,} руб.\n".replace(",", " ")
    report += f"├ 48 часов: {price[48]:,} руб.\n".replace(",", " ")
    report += f"└ 72 часа: {price[72]:,} руб.\n".replace(",", " ").replace(".", ",")

    report += "\n👁️ <b>Ожидаемые просмотры:</b>\n"
    report += f"├ 24 часа: {views[24]}\n"
    report += f"├ 48 часов: {views[48]}\n"
    report += f"└ 72 часа: {views[72]}\n\n"

    report += f"Дата расчёта: {date_str}"

    if is_edit:
        await message.edit_text(
            report,
            reply_markup=keyboards.cpm_result(),
            parse_mode="HTML",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
    else:
        await message.answer(
            report,
            reply_markup=keyboards.cpm_result(),
            parse_mode="HTML",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )


@router.callback_query(F.data.startswith("NovaStat|calc_cpm|"))
async def novastat_cpm_cb(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработка выбора CPM через кнопки.
    """
    cpm = int(call.data.split("|")[2])
    await calculate_and_show_price(call.message, cpm, state, is_edit=True)
    await call.answer()


@router.message(NovaStatStates.waiting_for_cpm)
async def novastat_cpm_text(message: types.Message, state: FSMContext) -> None:
    """
    Обработка ввода CPM текстом.
    """
    try:
        cpm = int(message.text.strip())
        await calculate_and_show_price(message, cpm, state)
    except ValueError:
        await message.answer("Пожалуйста, введите число.")
