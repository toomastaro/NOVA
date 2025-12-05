import asyncio
import logging
from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from main_bot.database.db import db
from main_bot.keyboards import keyboards, InlineNovaStat
from main_bot.utils.novastat import novastat_service
from main_bot.utils.lang.language import text
from main_bot.states.user import NovaStatStates

logger = logging.getLogger(__name__)

router = Router()

# --- Entry Point ---
@router.message(F.text == text('reply_menu:novastat'))
async def novastat_main(message: types.Message, state: FSMContext):
    # Check subscription
    import time
    subscribed_channels = await db.get_subscribe_channels(message.from_user.id)
    has_active_sub = any(ch.subscribe and ch.subscribe > time.time() for ch in subscribed_channels)
    
    if not has_active_sub:
        await message.answer("Эта функция доступна только при наличии хотя бы одной активной оплаченной подписки.")
        return

    await state.clear()
    await message.answer(
        "<b>Быстрая аналитика канала!</b>\n"
        "Просто пришлите ссылку на свой телеграм-канал.\n"
        "Если канал приватный, то отправьте ссылку с автоприёмом, чтобы бот смог её открыть.",
        reply_markup=InlineNovaStat.main_menu(),
        parse_mode="HTML"
    )
    await state.set_state(NovaStatStates.waiting_for_channels)

@router.callback_query(F.data == "NovaStat|main")
async def novastat_main_cb(call: types.CallbackQuery, state: FSMContext):
    # Check subscription
    import time
    subscribed_channels = await db.get_subscribe_channels(call.from_user.id)
    has_active_sub = any(ch.subscribe and ch.subscribe > time.time() for ch in subscribed_channels)
    
    if not has_active_sub:
        await call.answer("Эта функция доступна только при наличии хотя бы одной активной оплаченной подписки.", show_alert=True)
        return

    await state.clear()
    await call.message.edit_text(
        "<b>Быстрая аналитика канала!</b>\n"
        "Просто пришлите ссылку на свой телеграм-канал.\n"
        "Если канал приватный, то отправьте ссылку с автоприёмом, чтобы бот смог её открыть.",
        reply_markup=InlineNovaStat.main_menu(),
        parse_mode="HTML"
    )
    await state.set_state(NovaStatStates.waiting_for_channels)

@router.callback_query(F.data == "NovaStat|exit")
async def novastat_exit(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer(
        text("start_text"),
        reply_markup=keyboards.menu()
    )

# --- Settings ---
@router.callback_query(F.data == "NovaStat|settings")
async def novastat_settings(call: types.CallbackQuery):
    settings = await db.get_novastat_settings(call.from_user.id)
    await call.message.edit_text(
        f"<b>Настройки NOVAстат</b>\n\n"
        f"Текущая глубина анализа: {settings.depth_days} дней.\n"
        f"Выберите новое значение:",
        reply_markup=InlineNovaStat.settings(settings.depth_days),
        parse_mode="HTML"
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
        reply_markup=InlineNovaStat.settings(settings.depth_days),
        parse_mode="HTML"
    )

# --- Collections ---
@router.callback_query(F.data == "NovaStat|collections")
async def novastat_collections(call: types.CallbackQuery):
    collections = await db.get_collections(call.from_user.id)
    if not collections:
        await call.message.edit_text(
            "У вас пока нет коллекций каналов.\n"
            "Создайте первую коллекцию, чтобы быстро получать аналитику.",
            reply_markup=InlineNovaStat.collections_list([])
        )
    else:
        text_list = "<b>Ваши коллекции:</b>\n"
        # We need to fetch channels count for each collection to display properly
        # For now, just list names
        for i, col in enumerate(collections, 1):
            text_list += f"{i}. {col.name}\n"
            
        await call.message.edit_text(
            text_list,
            reply_markup=InlineNovaStat.collections_list(collections),
            parse_mode="HTML"
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
        "Ваши коллекции:",
        reply_markup=InlineNovaStat.collections_list(collections)
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
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML"
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
    col_id = data['col_id']
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
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data.startswith("NovaStat|col_add_channel|"))
async def novastat_add_channel_start(call: types.CallbackQuery, state: FSMContext):
    col_id = int(call.data.split("|")[2])
    await state.update_data(col_id=col_id)
    await call.message.answer("Пришлите ссылку на канал или @username (можно списком, каждый с новой строки):")
    await state.set_state(NovaStatStates.waiting_for_channel_to_add)
    await call.answer()

@router.message(NovaStatStates.waiting_for_channel_to_add)
async def novastat_add_channel_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    col_id = data['col_id']
    
    text_lines = message.text.strip().split('\n')
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
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data.startswith("NovaStat|col_del_channel_list|"))
async def novastat_del_channel_list(call: types.CallbackQuery):
    col_id = int(call.data.split("|")[2])
    channels = await db.get_collection_channels(col_id)
    await call.message.edit_text(
        "Выберите канал для удаления:",
        reply_markup=InlineNovaStat.collection_channels_delete(col_id, channels)
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
        reply_markup=InlineNovaStat.collection_channels_delete(col_id, channels)
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
        status_msg = await message.answer(f"⏳ Начинаю анализ {len(channels)} каналов (глубина {depth} дн.)...", link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        await run_analysis_logic(message, channels, depth, state, status_msg)

async def run_analysis_background(message: types.Message, channels: list, depth: int, state: FSMContext):
    try:
        await run_analysis_logic(message, channels, depth, state, None)
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при фоновом анализе: {e}")

async def run_analysis_logic(message: types.Message, channels: list, depth: int, state: FSMContext, status_msg: types.Message = None):
    # Новая логика с кэшированием
    results = []
    failed = []
    
    total_channels = len(channels)
    
    for i, ch in enumerate(channels, 1):
        if status_msg:
            await status_msg.edit_text(f"📊 Собираю статистику: {ch} ({i}/{total_channels})...", link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        
        # collect_stats теперь использует кэш и external MtClient
        stats = await novastat_service.collect_stats(ch, depth, horizon=24)
        
        if stats:
            # Проверить структуру результата
            if 'views' not in stats or 'er' not in stats:
                logger.error(f"Invalid stats structure for {ch}: {stats}")
                failed.append({"channel": ch, "error": "Неверная структура данных"})
                continue
            
            # Проверить наличие всех горизонтов и заполнить отсутствующие нулями
            missing_horizons = []
            for h in [24, 48, 72]:
                if h not in stats['views']:
                    stats['views'][h] = 0
                    missing_horizons.append(h)
                if h not in stats['er']:
                    stats['er'][h] = 0.0
            
            if missing_horizons:
                logger.warning(f"Missing horizons {missing_horizons} for {ch}, filled with zeros. This is normal for cached data.")
            
            logger.info(f"Successfully collected stats for {ch}: views={stats['views']}, er={stats['er']}")
            results.append(stats)
        else:
            # Проверить, есть ли ошибка в кэше
            cache = await db.get_cache(ch, 24)
            if cache and cache.error_message:
                failed.append({"channel": ch, "error": cache.error_message})
            else:
                failed.append({"channel": ch, "error": "Не удалось получить статистику"})

    if not results:
        text_err = (
            "❌ Не удалось получить статистику ни по одному каналу.\n"
        )
        if failed:
            text_err += "\nОшибки:\n"
            for f in failed[:5]:  # Показать первые 5 ошибок
                text_err += f"• {f['channel']}: {f['error']}\n"
        
        if status_msg:
            await status_msg.edit_text(text_err, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        else:
            await message.answer(text_err, link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        return

    # 3. Analyze
    if status_msg:
        await status_msg.edit_text("🔄 Анализирую данные...", link_preview_options=types.LinkPreviewOptions(is_disabled=True))

    # Calculate totals for views and averages for ER
    total_views = {24: 0, 48: 0, 72: 0}
    total_er = {24: 0.0, 48: 0.0, 72: 0.0}
    count = len(results)
    
    for res in results:
        for h in [24, 48, 72]:
            total_views[h] += res['views'][h]
            total_er[h] += res['er'][h]
            
    # Views are summed (Total), ER is averaged
    final_views = total_views 
    if count > 0:
        avg_er = {h: round(total_er[h] / count, 2) for h in [24, 48, 72]}
    else:
        avg_er = {24: 0.0, 48: 0.0, 72: 0.0}
    
    # Store results for CPM calculation
    data_to_store = {'last_analysis_views': final_views}
    if count == 1:
        data_to_store['single_channel_info'] = {
            'title': results[0]['title'],
            'username': results[0]['username'],
            'link': results[0].get('link'),
            'subscribers': results[0]['subscribers']
        }
    else:
        data_to_store['single_channel_info'] = None
        
    await state.update_data(**data_to_store)
    
    report = f"📊 <b>Отчет аналитики ({count} каналов)</b>\n\n"
    
    if count == 1:
        res = results[0]
        link = res.get('link')
        title_link = f"<a href='{link}'>{res['title']}</a>" if link else res['title']
        report += f"📢 Канал: {title_link}\n"
        report += f"👥 Подписчиков: {res['subscribers']}\n\n"

    report += f"👁️ <b>Суммарные просмотры:</b>\n"
    report += f"├ 24 часа: {final_views[24]}\n"
    report += f"├ 48 часов: {final_views[48]}\n"
    report += f"└ 72 часа: {final_views[72]}\n\n"
    
    report += f"📈 <b>Средний ER:</b>\n"
    report += f"├ 24 часа: {avg_er[24]}%\n"
    report += f"├ 48 часов: {avg_er[48]}%\n"
    report += f"└ 72 часа: {avg_er[72]}%\n\n"
    
    if failed:
        report += f"⚠️ Не удалось обработать: {len(failed)} каналов.\n"

    if status_msg:
        await status_msg.delete()
    
    await message.answer(report, reply_markup=InlineNovaStat.analysis_result(), parse_mode="HTML", link_preview_options=types.LinkPreviewOptions(is_disabled=True))


@router.message(NovaStatStates.waiting_for_channels)
async def novastat_analyze_text(message: types.Message, state: FSMContext):
    text_lines = message.text.strip().split('\n')
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
        reply_markup=InlineNovaStat.cpm_choice()
    )
    await state.set_state(NovaStatStates.waiting_for_cpm)
    await call.answer()

async def calculate_and_show_price(message: types.Message, cpm: int, state: FSMContext, user_id: int, is_edit: bool = False):
    data = await state.get_data()
    views = data.get('last_analysis_views')
    single_info = data.get('single_channel_info')
    
    if not views:
        if is_edit:
             await message.edit_text("Данные аналитики устарели. Пожалуйста, проведите анализ заново.")
        else:
             await message.answer("Данные аналитики устарели. Пожалуйста, проведите анализ заново.")
        return
        
    # Fetch user's exchange rate
    user = await db.get_user(user_id)
    if user and user.default_exchange_rate_id:
        exchange_rate_obj = await db.get_exchange_rate(user.default_exchange_rate_id)
        rate = exchange_rate_obj.rate if exchange_rate_obj else 100.0
    else:
        rate = 100.0
    
    price_rub = {h: int((views[h] / 1000) * cpm) for h in [24, 48, 72]}
    price_usdt = {h: round(price_rub[h] / rate, 2) for h in [24, 48, 72]}
    
    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    report = f"👛 <b>Стоимость рекламы (CPM {cpm}):</b>\n"
    
    if single_info:
        link = single_info.get('link')
        title_link = f"<a href='{link}'>{single_info['title']}</a>" if link else single_info['title']
        report += f"📢 Канал: {title_link}\n"
        report += f"👥 Подписчиков: {single_info['subscribers']}\n\n"
    
    report += f"├ 24 часа: {price_rub[24]:,} руб. / {price_usdt[24]} usdt\n".replace(",", " ")
    report += f"├ 48 часов: {price_rub[48]:,} руб. / {price_usdt[48]} usdt\n".replace(",", " ")
    report += f"└ 72 часа: {price_rub[72]:,} руб. / {price_usdt[72]} usdt\n".replace(",", " ").replace(".", ",")
    
    report += f"\n👁️ <b>Ожидаемые просмотры:</b>\n"
    report += f"├ 24 часа: {views[24]}\n"
    report += f"├ 48 часов: {views[48]}\n"
    report += f"└ 72 часа: {views[72]}\n\n"
    
    report += f"Дата расчёта: {date_str}"
    
    if is_edit:
        await message.edit_text(report, reply_markup=InlineNovaStat.cpm_result(), parse_mode="HTML", link_preview_options=types.LinkPreviewOptions(is_disabled=True))
    else:
        await message.answer(report, reply_markup=InlineNovaStat.cpm_result(), parse_mode="HTML", link_preview_options=types.LinkPreviewOptions(is_disabled=True))

@router.callback_query(F.data.startswith("NovaStat|calc_cpm|"))
async def novastat_cpm_cb(call: types.CallbackQuery, state: FSMContext):
    cpm = int(call.data.split("|")[2])
    await calculate_and_show_price(call.message, cpm, state, call.from_user.id, is_edit=True)
    await call.answer()

@router.message(NovaStatStates.waiting_for_cpm)
async def novastat_cpm_text(message: types.Message, state: FSMContext):
    try:
        cpm = int(message.text.strip())
        await calculate_and_show_price(message, cpm, state, message.from_user.id)
    except ValueError:
        await message.answer("Пожалуйста, введите число.")
