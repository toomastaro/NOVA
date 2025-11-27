import asyncio
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from main_bot.database.db import db
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.utils.novastat import novastat_service

router = Router()


class NovaStatStates(StatesGroup):
    waiting_for_channels = State()
    waiting_for_collection_name = State()
    waiting_for_rename_collection = State()
    waiting_for_channel_to_add = State()
    waiting_for_cpm = State()


# --- Entry Point ---
@router.message(F.text == "NOVAстат")
async def novastat_main(message: types.Message, state: FSMContext):
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
async def novastat_main_cb(call: types.CallbackQuery, state: FSMContext):
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
async def novastat_exit(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer(text("start_text"), reply_markup=keyboards.menu())


# --- Settings ---
@router.callback_query(F.data == "NovaStat|settings")
async def novastat_settings(call: types.CallbackQuery):
    settings = await db.get_novastat_settings(call.from_user.id)
    await call.message.edit_text(
        f"<b>Настройки NOVAстат</b>\n\n"
        f"Текущая глубина анализа: {settings.depth_days} дней.\n"
        f"Выберите новое значение:",
        reply_markup=keyboards.settings(settings.depth_days),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("NovaStat|set_depth|"))
async def novastat_set_depth(call: types.CallbackQuery):
    depth = int(call.data.split("|")[2])
    await db.update_novastat_settings(call.from_user.id, depth_days=depth)
    await call.answer(f"Глубина анализа обновлена: {depth} дней")

    # Refresh view
    settings = await db.get_novastat_settings(call.from_user.id)
    await call.message.edit_text(
        f"<b>Настройки NOVAстат</b>\n\n"
        f"Текущая глубина анализа: {settings.depth_days} дней.\n"
        f"Выберите новое значение:",
        reply_markup=keyboards.settings(settings.depth_days),
        parse_mode="HTML",
    )


# --- Collections ---
@router.callback_query(F.data == "NovaStat|collections")
async def novastat_collections(call: types.CallbackQuery):
    collections = await db.get_collections(call.from_user.id)
    if not collections:
        await call.message.edit_text(
            "У вас пока нет коллекций каналов.\n"
            "Создайте первую коллекцию, чтобы быстро получать аналитику.",
            reply_markup=keyboards.collections_list([]),
        )
    else:
        text_list = "<b>Ваши коллекции:</b>\n"
        # We need to fetch channels count for each collection to display properly
        # For now, just list names
        for i, col in enumerate(collections, 1):
            text_list += f"{i}. {col.name}\n"

        await call.message.edit_text(
            text_list,
            reply_markup=keyboards.collections_list(collections),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "NovaStat|col_create")
async def novastat_create_col_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите название для новой коллекции:")
    await state.set_state(NovaStatStates.waiting_for_collection_name)
    await call.answer()


@router.message(NovaStatStates.waiting_for_collection_name)
async def novastat_create_col_finish(message: types.Message, state: FSMContext):
    name = message.text
    await db.create_collection(message.from_user.id, name)
    await message.answer(f"Коллекция '{name}' создана!")

    # Return to collections list
    collections = await db.get_collections(message.from_user.id)
    await message.answer(
        "Ваши коллекции:", reply_markup=keyboards.collections_list(collections)
    )
    await state.clear()


@router.callback_query(F.data.startswith("NovaStat|col_open|"))
async def novastat_open_col(call: types.CallbackQuery):
    col_id = int(call.data.split("|")[2])
    collection = await db.get_collection(col_id)
    channels = await db.get_collection_channels(col_id)

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
async def novastat_delete_col(call: types.CallbackQuery):
    col_id = int(call.data.split("|")[2])
    await db.delete_collection(col_id)
    await call.answer("Коллекция удалена")
    await novastat_collections(call)


@router.callback_query(F.data.startswith("NovaStat|col_rename|"))
async def novastat_rename_col_start(call: types.CallbackQuery, state: FSMContext):
    col_id = int(call.data.split("|")[2])
    await state.update_data(col_id=col_id)
    await call.message.answer("Введите новое название коллекции:")
    await state.set_state(NovaStatStates.waiting_for_rename_collection)
    await call.answer()


@router.message(NovaStatStates.waiting_for_rename_collection)
async def novastat_rename_col_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    col_id = data["col_id"]
    new_name = message.text
    await db.rename_collection(col_id, new_name)
    await message.answer(f"Коллекция переименована в '{new_name}'")

    # Return to collection view
    # We need to manually trigger the view update or just send a new message
    # Sending new message is easier
    collection = await db.get_collection(col_id)
    channels = await db.get_collection_channels(col_id)

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
async def novastat_add_channel_start(call: types.CallbackQuery, state: FSMContext):
    col_id = int(call.data.split("|")[2])
    await state.update_data(col_id=col_id)
    await call.message.answer(
        "Пришлите ссылку на канал или @username (можно списком, каждый с новой строки):"
    )
    await state.set_state(NovaStatStates.waiting_for_channel_to_add)
    await call.answer()


@router.message(NovaStatStates.waiting_for_channel_to_add)
async def novastat_add_channel_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    col_id = data["col_id"]

    text_lines = message.text.strip().split("\n")
    channels_to_add = [line.strip() for line in text_lines if line.strip()]

    if not channels_to_add:
        await message.answer("Не удалось распознать каналы. Попробуйте еще раз.")
        return

    added_count = 0
    for identifier in channels_to_add:
        # Simple validation or error handling could be added here if needed
        await db.add_channel_to_collection(col_id, identifier)
        added_count += 1

    await message.answer(f"Добавлено каналов: {added_count}")

    # Return to collection view
    collection = await db.get_collection(col_id)
    channels = await db.get_collection_channels(col_id)

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
async def novastat_del_channel_list(call: types.CallbackQuery):
    col_id = int(call.data.split("|")[2])
    channels = await db.get_collection_channels(col_id)
    await call.message.edit_text(
        "Выберите канал для удаления:",
        reply_markup=keyboards.collection_channels_delete(col_id, channels),
    )


@router.callback_query(F.data.startswith("NovaStat|col_del_channel|"))
async def novastat_del_channel(call: types.CallbackQuery):
    parts = call.data.split("|")
    col_id = int(parts[2])
    channel_db_id = int(parts[3])

    await db.remove_channel_from_collection(channel_db_id)
    await call.answer("Канал удален")

    # Refresh list
    channels = await db.get_collection_channels(col_id)
    await call.message.edit_reply_markup(
        reply_markup=keyboards.collection_channels_delete(col_id, channels)
    )


# --- Analysis Logic ---
async def process_analysis(message: types.Message, channels: list, state: FSMContext):
    settings = await db.get_novastat_settings(message.from_user.id)
    depth = settings.depth_days

    if len(channels) > 5:
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
    message: types.Message, channels: list, depth: int, state: FSMContext
):
    try:
        await run_analysis_logic(message, channels, depth, state, None)
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при фоновом анализе: {e}")


async def run_analysis_logic(
    message: types.Message,
    channels: list,
    depth: int,
    state: FSMContext,
    status_msg: types.Message = None,
):
    # Use a single client session for the entire analysis process
    async with novastat_service.get_client() as client:
        # 1. Check Access
        valid_entities = []
        failed = []

        total_channels = len(channels)

        for i, ch in enumerate(channels, 1):
            if status_msg:
                await status_msg.edit_text(
                    f"🔍 Проверяю доступ к каналу {i}/{total_channels}: {ch}...",
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                )

            entity = await novastat_service.check_access(ch, client=client)
            if entity:
                valid_entities.append((ch, entity))
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

        # 2. Collect Stats
        results = []

        for i, (ch_id, entity) in enumerate(valid_entities, 1):
            if status_msg:
                await status_msg.edit_text(
                    f"📊 Собираю статистику: {ch_id} ({i}/{len(valid_entities)})...",
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                )

            # We pass ch_id to collect_stats as per our refactor
            stats = await novastat_service.collect_stats(ch_id, depth, client=client)
            if stats:
                results.append(stats)
            else:
                failed.append(ch_id)

    # 3. Analyze
    if status_msg:
        await status_msg.edit_text(
            "🔄 Анализирую данные...",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )

    # Calculate totals for views and averages for ER
    total_views = {24: 0, 48: 0, 72: 0}
    total_er = {24: 0.0, 48: 0.0, 72: 0.0}
    count = len(results)

    for res in results:
        for h in [24, 48, 72]:
            total_views[h] += res["views"][h]
            total_er[h] += res["er"][h]

    # Views are summed (Total), ER is averaged
    final_views = total_views
    if count > 0:
        avg_er = {h: round(total_er[h] / count, 2) for h in [24, 48, 72]}
    else:
        avg_er = {24: 0.0, 48: 0.0, 72: 0.0}

    # Store results for CPM calculation
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

    if status_msg:
        await status_msg.delete()

    await message.answer(
        report,
        reply_markup=keyboards.analysis_result(),
        parse_mode="HTML",
        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
    )


@router.message(NovaStatStates.waiting_for_channels)
async def novastat_analyze_text(message: types.Message, state: FSMContext):
    text_lines = message.text.strip().split("\n")
    channels = [line.strip() for line in text_lines if line.strip()]

    if not channels:
        await message.answer("Не удалось распознать каналы. Попробуйте еще раз.")
        return

    await process_analysis(message, channels, state)


@router.callback_query(F.data.startswith("NovaStat|col_analyze|"))
async def novastat_analyze_collection(call: types.CallbackQuery, state: FSMContext):
    col_id = int(call.data.split("|")[2])
    channels_db = await db.get_collection_channels(col_id)

    if not channels_db:
        await call.answer("В коллекции нет каналов!", show_alert=True)
        return

    channels = [ch.channel_identifier for ch in channels_db]
    await call.answer()
    await process_analysis(call.message, channels, state)


# --- CPM Calculation ---
@router.callback_query(F.data == "NovaStat|calc_cpm_start")
async def novastat_cpm_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Выберите CPM (стоимость за 1000 просмотров) кнопкой ниже\n"
        "или отправьте своё значение числом.",
        reply_markup=keyboards.cpm_choice(),
    )
    await state.set_state(NovaStatStates.waiting_for_cpm)
    await call.answer()


async def calculate_and_show_price(
    message: types.Message, cpm: int, state: FSMContext, is_edit: bool = False
):
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

    price = {h: int((views[h] / 1000) * cpm) for h in [24, 48, 72]}

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
async def novastat_cpm_cb(call: types.CallbackQuery, state: FSMContext):
    cpm = int(call.data.split("|")[2])
    await calculate_and_show_price(call.message, cpm, state, is_edit=True)
    await call.answer()


@router.message(NovaStatStates.waiting_for_cpm)
async def novastat_cpm_text(message: types.Message, state: FSMContext):
    try:
        cpm = int(message.text.strip())
        await calculate_and_show_price(message, cpm, state)
    except ValueError:
        await message.answer("Пожалуйста, введите число.")
