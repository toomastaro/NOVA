import asyncio
import logging
from datetime import datetime
import html

from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from main_bot.database.db import db
from main_bot.keyboards import keyboards, InlineNovaStat
from main_bot.utils.novastat import novastat_service
from main_bot.utils.lang.language import text
from main_bot.states.user import NovaStatStates
from main_bot.utils.report_signature import get_report_signatures

logger = logging.getLogger(__name__)

router = Router()

# --- Entry Point ---
@router.message(F.text == text('reply_menu:novastat'))
async def novastat_main(message: types.Message, state: FSMContext):
    # Check subscription
    import time
    subscribed_channels = await db.channel.get_subscribe_channels(message.from_user.id)
    has_active_sub = any(ch.subscribe and ch.subscribe > time.time() for ch in subscribed_channels)
    
    if not has_active_sub:
        await message.answer("Эта функция доступна только при наличии хотя бы одной активной оплаченной подписки.")
        return

    await state.clear()
    await message.answer(
        "📊 <b>NOVASTAT: Быстрая аналитика</b>\n\n"
        "Отправьте боту <b>ссылки</b> или <b>юзернеймы</b> каналов, чтобы получить подробную статистику просмотров и ER.\n\n"
        "📝 <b>Как пользоваться:</b>\n"
        "• Пришлите одну ссылку — для детального отчета.\n"
        "• Пришлите список (до 12 шт.) — для массового анализа.\n"
        "• Каждый канал — <b>с новой строки</b>.\n\n"
        "🔒 <b>Для приватных каналов:</b>\n"
        "Используйте ссылку с <b>автоприёмом</b> (без одобрения администратора), чтобы бот мог получить доступ к статистике.",
        reply_markup=InlineNovaStat.main_menu(),
        parse_mode="HTML"
    )
    await state.set_state(NovaStatStates.waiting_for_channels)

@router.callback_query(F.data == "NovaStat|main")
async def novastat_main_cb(call: types.CallbackQuery, state: FSMContext):
    # Check subscription
    import time
    subscribed_channels = await db.channel.get_subscribe_channels(call.from_user.id)
    has_active_sub = any(ch.subscribe and ch.subscribe > time.time() for ch in subscribed_channels)
    
    if not has_active_sub:
        await call.answer("Эта функция доступна только при наличии хотя бы одной активной оплаченной подписки.", show_alert=True)
        return

    await state.clear()
    await call.message.edit_text(
        "📊 <b>NOVASTAT: Быстрая аналитика</b>\n\n"
        "Отправьте боту <b>ссылки</b> или <b>юзернеймы</b> каналов, чтобы получить подробную статистику просмотров и ER.\n\n"
        "📝 <b>Как пользоваться:</b>\n"
        "• Пришлите одну ссылку — для детального отчета.\n"
        "• Пришлите список (до 12 шт.) — для массового анализа.\n"
        "• Каждый канал — <b>с новой строки</b>.\n\n"
        "🔒 <b>Для приватных каналов:</b>\n"
        "Используйте ссылку с <b>автоприёмом</b> (без одобрения администратора), чтобы бот мог получить доступ к статистике.",
        reply_markup=InlineNovaStat.main_menu(),
        parse_mode="HTML"
    )
    await state.set_state(NovaStatStates.waiting_for_channels)

@router.callback_query(F.data == "NovaStat|exit")
async def novastat_exit(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()

    from main_bot.keyboards.common import Reply
    await call.message.answer(
        "Главное меню",
        reply_markup=Reply.menu()
    )

# --- Settings ---
@router.callback_query(F.data == "NovaStat|settings")
async def novastat_settings(call: types.CallbackQuery):
    settings = await db.novastat.get_novastat_settings(call.from_user.id)
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
    await db.novastat.update_novastat_settings(call.from_user.id, depth_days=depth)
    await call.answer(f"Глубина анализа обновлена: {depth} дней")
    
    # Refresh view
    settings = await db.novastat.get_novastat_settings(call.from_user.id)
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
    collections = await db.novastat.get_collections(call.from_user.id)
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
    await db.novastat.create_collection(message.from_user.id, name)
    await message.answer(f"Коллекция '{name}' создана!")
    
    # Return to collections list
    collections = await db.novastat.get_collections(message.from_user.id)
    await message.answer(
        "Ваши коллекции:",
        reply_markup=InlineNovaStat.collections_list(collections)
    )
    await state.clear()

@router.callback_query(F.data.startswith("NovaStat|col_open|"))
async def novastat_open_col(call: types.CallbackQuery):
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
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("NovaStat|col_delete|"))
async def novastat_delete_col(call: types.CallbackQuery):
    col_id = int(call.data.split("|")[2])
    await db.novastat.delete_collection(col_id)
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
    await db.novastat.rename_collection(col_id, new_name)
    await message.answer(f"Коллекция переименована в '{new_name}'")
    
    # Return to collection view
    # We need to manually trigger the view update or just send a new message
    # Sending new message is easier
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
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data.startswith("NovaStat|col_add_channel|"))
async def novastat_add_channel_start(call: types.CallbackQuery, state: FSMContext):
    col_id = int(call.data.split("|")[2])
    await state.update_data(col_id=col_id)
    await call.message.answer("Пришлите ссылку на канал или @username (можно списком, каждый с новой строки).\nМаксимум 100 каналов в коллекции.")
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

    # Check limit
    existing = await db.novastat.get_collection_channels(col_id)
    if len(existing) + len(channels_to_add) > 100:
        await message.answer(f"⚠️ Лимит превышен! В коллекции максимум 100 каналов.\nСейчас: {len(existing)}. Попытка добавить: {len(channels_to_add)}.\nДоступно мест: {100 - len(existing)}.")
        return

    added_count = 0
    for identifier in channels_to_add:
        # Simple validation or error handling could be added here if needed
        await db.novastat.add_channel_to_collection(col_id, identifier)
        added_count += 1
    
    await message.answer(f"Добавлено каналов: {added_count}")
    
    # Return to collection view
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
        reply_markup=InlineNovaStat.collection_view(collection, channels),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data.startswith("NovaStat|col_del_channel_list|"))
async def novastat_del_channel_list(call: types.CallbackQuery):
    col_id = int(call.data.split("|")[2])
    channels = await db.novastat.get_collection_channels(col_id)
    await call.message.edit_text(
        "Выберите канал для удаления:",
        reply_markup=InlineNovaStat.collection_channels_delete(col_id, channels)
    )

@router.callback_query(F.data.startswith("NovaStat|col_del_channel|"))
async def novastat_del_channel(call: types.CallbackQuery):
    parts = call.data.split("|")
    col_id = int(parts[2])
    channel_db_id = int(parts[3])
    
    await db.novastat.remove_channel_from_collection(channel_db_id)
    await call.answer("Канал удален")
    
    # Refresh list
    channels = await db.novastat.get_collection_channels(col_id)
    await call.message.edit_reply_markup(
        reply_markup=InlineNovaStat.collection_channels_delete(col_id, channels)
    )

# --- Analysis Logic ---
async def process_analysis(message: types.Message, channels: list, state: FSMContext):
    settings = await db.novastat.get_novastat_settings(message.from_user.id)
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

def _format_stats_body(stats):
    link = stats.get('link')
    title_link = f"<a href='{link}'>{stats['title']}</a>" if link else stats['title']
    
    text = f"📢 Канал: {title_link}\n"
    text += f"👥 Подписчиков: {stats['subscribers']}\n\n"
    
    text += f"👁️ <b>Просмотры:</b>\n"
    text += f"├ 24 часа: {stats['views'].get(24, 0)}\n"
    text += f"├ 48 часов: {stats['views'].get(48, 0)}\n"
    text += f"└ 72 часа: {stats['views'].get(72, 0)}\n\n"
    
    text += f"📈 <b>ER:</b>\n"
    text += f"├ 24 часа: {stats['er'].get(24, 0)}%\n"
    text += f"├ 48 часов: {stats['er'].get(48, 0)}%\n"
    text += f"└ 72 часа: {stats['er'].get(72, 0)}%\n\n"
    return text

async def run_analysis_logic(message: types.Message, channels: list, depth: int, state: FSMContext, status_msg: types.Message = None):
    # Initial status - removed redundant edit
    # if status_msg:
    #      await status_msg.edit_text(...)
    
    total_views = {24: 0, 48: 0, 72: 0}
    total_er = {24: 0.0, 48: 0.0, 72: 0.0}
    total_subs = 0
    valid_count = 0
    results = []
    
    for i, ch in enumerate(channels, 1):
        # Collect
        stats = await novastat_service.collect_stats(ch, depth, horizon=24, bot=message.bot)
        
        if stats:
            valid_count += 1
            results.append(stats)
            
            # Если каналов больше 1, отправляем отчет по каждому сразу
            if len(channels) > 1:
                ind_report = f"📊 <b>Аналитика канала ({i}/{len(channels)})</b>\n\n"
                ind_report += _format_stats_body(stats)
                try:
                    await message.answer(ind_report, parse_mode="HTML", link_preview_options=types.LinkPreviewOptions(is_disabled=True))
                except Exception as e:
                    logger.error(f"Failed to send individual report for {ch}: {e}")
                    # Try simplified message
                    await message.answer(f"📊 Аналитика ({ch}): получена (ошибка форматирования)", link_preview_options=types.LinkPreviewOptions(is_disabled=True))

            # Accumulate
            total_subs += stats.get('subscribers', 0)
            for h in [24, 48, 72]:
                total_views[h] = total_views.get(h, 0) + stats.get('views', {}).get(h, 0)
                total_er[h] = total_er.get(h, 0) + stats.get('er', {}).get(h, 0)
        else:
            # Error checks
            error_text = f"❌ Не удалось получить статистику: {html.escape(str(ch))}"
            cache = await db.novastat_cache.get_cache(str(ch), 24)
            if cache and cache.error_message:
                error_text += f"\nПричина: {html.escape(cache.error_message)}"
                
            await message.answer(error_text, link_preview_options=types.LinkPreviewOptions(is_disabled=True))

    # Delete initial processing status
    if status_msg:
        await status_msg.delete()

    if valid_count == 0:
        await message.answer("❌ Не удалось получить данные ни по одному каналу.")
        return

    # Prepare Summary
    summary_views = total_views
    summary_er = {h: round(total_er[h] / valid_count, 2) for h in [24, 48, 72]}
    
    # Save for CPM
    await state.update_data(last_analysis_views=summary_views)
    
    if len(channels) == 1:
        # Single channel case: This IS the report.
        stats = results[0]
        
        single_info = {
            'title': stats['title'],
            'username': stats['username'],
            'link': stats.get('link'),
            'subscribers': stats['subscribers']
        }
        await state.update_data(single_channel_info=single_info)
        
        report = f"📊 <b>Отчет аналитики</b>\n\n"
        report += _format_stats_body(stats)
        
        await message.answer(report, reply_markup=InlineNovaStat.analysis_result(), parse_mode="HTML", link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        
    else:
        # Summary
        await state.update_data(single_channel_info=None)
        
        report = f"📊 <b>ОБЩИЙ ОТЧЕТ ({valid_count} каналов)</b>\n\n"
        report += f"👥 <b>Общее кол-во подписчиков:</b> {total_subs}\n\n"
        report += f"👁️ <b>Суммарные просмотры:</b>\n"
        report += f"├ 24 часа: {summary_views[24]}\n"
        report += f"├ 48 часов: {summary_views[48]}\n"
        report += f"└ 72 часа: {summary_views[72]}\n\n"
        
        report += f"📈 <b>Средний ER:</b>\n"
        report += f"├ 24 часа: {summary_er[24]}%\n"
        report += f"├ 48 часов: {summary_er[48]}%\n"
        report += f"└ 72 часа: {summary_er[72]}%\n\n"
        
        await message.answer(report, reply_markup=InlineNovaStat.analysis_result(), parse_mode="HTML", link_preview_options=types.LinkPreviewOptions(is_disabled=True))


@router.message(NovaStatStates.waiting_for_channels)
async def novastat_analyze_text(message: types.Message, state: FSMContext):
    text_lines = message.text.strip().split('\n')
    channels = [line.strip() for line in text_lines if line.strip()]
    
    if not channels:
        await message.answer("Не удалось распознать каналы. Попробуйте еще раз.")
        return
        
    if len(channels) > 12:
        await message.answer("⚠️ Можно проверить не более 12 каналов за раз.\nДля большего количества используйте Коллекции или отправляйте частями.")
        return

    await process_analysis(message, channels, state)

@router.callback_query(F.data.startswith("NovaStat|col_analyze|"))
async def novastat_analyze_collection(call: types.CallbackQuery, state: FSMContext):
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
    user = await db.user.get_user(user_id)
    if user and user.default_exchange_rate_id:
        exchange_rate_obj = await db.exchange_rate.get_exchange_rate(user.default_exchange_rate_id)
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
    
    # Добавляем подписи
    report += await get_report_signatures(user, 'cpm', message.bot)
    
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


# --- My Channels Selection ---
@router.callback_query(F.data == "NovaStat|my_channels")
async def novastat_my_channels(call: types.CallbackQuery, state: FSMContext):
    folders = await db.user_folder.get_folders(
        user_id=call.from_user.id
    )
    channels = await db.channel.get_user_channels_without_folders(
        user_id=call.from_user.id
    )
    
    await state.update_data(
        chosen=[],
        chosen_folders=[],
        current_folder_id=None
    )
    
    await call.message.edit_text(
        text("choice_channels:post").format(0, ""),
        reply_markup=keyboards.choice_objects(
            resources=channels,
            chosen=[],
            folders=folders,
            data="ChoiceNovaStatChannels"
        )
    )
    await state.set_state(NovaStatStates.choosing_my_channels)


@router.callback_query(F.data.startswith("ChoiceNovaStatChannels"))
async def novastat_choice_channels(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer("Ошибка: данные состояния потеряны")
        return await call.message.delete()

    chosen: list = data.get("chosen", [])
    current_folder_id = data.get("current_folder_id")

    # Determine objects
    if current_folder_id:
        folder = await db.user_folder.get_folder_by_id(current_folder_id)
        objects = []
        if folder and folder.content:
            for chat_id in folder.content:
                channel = await db.channel.get_channel_by_chat_id(int(chat_id))
                if channel:
                    objects.append(channel)
        folders = []
    else:
        objects = await db.channel.get_user_channels_without_folders(
            user_id=call.from_user.id
        )
        folders = await db.user_folder.get_folders(
            user_id=call.from_user.id
        )

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
            folders = await db.user_folder.get_folders(
                user_id=call.from_user.id
            )
            # Reset pagination
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = '0'
            else:
                temp.append('0')
        else:
            return await novastat_main_cb(call, state)

    # PAGINATION
    if temp[1] in ['next', 'back']:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                remover=int(temp[2]),
                data="ChoiceNovaStatChannels"
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

        if resource_type == 'folder':
            await state.update_data(current_folder_id=resource_id)
            folder = await db.user_folder.get_folder_by_id(resource_id)
            objects = []
            if folder and folder.content:
                for chat_id in folder.content:
                    channel = await db.channel.get_channel_by_chat_id(int(chat_id))
                    if channel:
                        objects.append(channel)
            folders = []
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = '0'
            else:
                temp.append('0')
        else:
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                chosen.append(resource_id)

    await state.update_data(chosen=chosen)
    
    # Display logic for formatted list of chosen channels
    display_objects = await db.channel.get_user_channels(
        user_id=call.from_user.id,
        from_array=chosen[:10]
    )

    if chosen:
        channels_list = "<blockquote expandable>" + "\n".join(
            text("resource_title").format(obj.title) for obj in display_objects
        ) + "</blockquote>"
    else:
        channels_list = ""
    
    remover_val = int(temp[2]) if temp[1] in ['choice_all', 'next', 'back'] or temp[1].replace("-", "").isdigit() else 0
    
    await call.message.edit_text(
        text("choice_channels:post").format(
            len(chosen),
            channels_list
        ),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            remover=remover_val,
            data="ChoiceNovaStatChannels"
        )
    )
