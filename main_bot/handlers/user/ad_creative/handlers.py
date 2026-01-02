"""
Модуль обработчиков для управления рекламными креативами.

Позволяет создавать, просматривать и удалять креативы.
Модуль обеспечивает:
- Парсинг контента из сообщений для создания слотов
- CRUD операции над креативами
- Навигацию по списку креативов
"""

import json
from typing import List, Dict, Any

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy import update

from main_bot.database.db import db
from main_bot.database.ad_creative.model import AdCreative
from main_bot.keyboards import InlineAdCreative
from main_bot.states.user import AdCreativeStates
from main_bot.utils.lang.language import text
from main_bot.utils.message_utils import reload_main_menu
from utils.error_handler import safe_handler

router = Router(name="AdCreative")


@router.callback_query(F.data == "AdCreative|create")
@safe_handler(
    "Креативы: старт создания"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def create_creative_start(call: CallbackQuery, state: FSMContext) -> None:
    """
    Начало процесса создания креатива.
    Переводит пользователя в состояние ожидания контента.

    Аргументы:
        call (CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await call.message.edit_text(
        text("ad_creative:create_start_text"),
        reply_markup=InlineAdCreative.create_creative_cancel(),
    )
    await state.set_state(AdCreativeStates.waiting_for_content)
    # Перезагрузка главного меню
    await reload_main_menu(call.message)
    await call.answer()


@router.message(AdCreativeStates.waiting_for_content)
@safe_handler(
    "Креативы: обработка контента"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def process_creative_content(message: Message, state: FSMContext) -> None:
    """
    Обработка пересланного контента для создания креатива.
    Парсит сущности (ссылки, text_link) и кнопки из сообщения.

    Аргументы:
        message (Message): Сообщение с контентом.
        state (FSMContext): Контекст состояния.
    """
    raw_message = json.loads(message.model_dump_json(exclude_defaults=True))

    if message.entities:
        raw_message["entities"] = [e.model_dump(mode="json") for e in message.entities]
    if message.caption_entities:
        raw_message["caption_entities"] = [
            e.model_dump(mode="json") for e in message.caption_entities
        ]

    slots: List[Dict[str, Any]] = []
    slot_index = 1

    def add_slot(url: str, loc_type: str, meta: Dict[str, Any]):
        nonlocal slot_index
        slots.append(
            {
                "slot_index": slot_index,
                "original_url": url,
                "location_type": loc_type,
                "location_meta": meta,
            }
        )
        slot_index += 1

    # 1. Entities
    if message.caption_entities:
        for i, entity in enumerate(message.caption_entities):
            if entity.type == "text_link":
                add_slot(entity.url, "text", {"entity_index": i, "field": "caption"})
            elif entity.type == "url":
                # Extract URL from text
                url = message.caption[entity.offset : entity.offset + entity.length]
                add_slot(url, "text", {"entity_index": i, "field": "caption"})

    if message.entities:
        for i, entity in enumerate(message.entities):
            if entity.type == "text_link":
                add_slot(entity.url, "text", {"entity_index": i, "field": "text"})
            elif entity.type == "url":
                url = message.text[entity.offset : entity.offset + entity.length]
                add_slot(url, "text", {"entity_index": i, "field": "text"})

    # 2. Inline Keyboard
    if message.reply_markup and message.reply_markup.inline_keyboard:
        for r, row in enumerate(message.reply_markup.inline_keyboard):
            for c, btn in enumerate(row):
                if btn.url:
                    add_slot(btn.url, "button", {"button_row": r, "button_col": c})

    if not slots:
        await message.answer(
            text("ad_creative:no_links_found"),
            reply_markup=InlineAdCreative.create_creative_cancel(),
        )
        return

    # Create Creative
    creative_id = await db.ad_creative.create_creative(
        owner_id=message.from_user.id,
        name=text("ad_creative:default_name"),  # Временное имя
        raw_message=raw_message,
    )

    await db.ad_creative.create_slots_for_creative(creative_id, slots)

    # Показ найденных ссылок
    links_text = "\n".join(
        [f"{s['slot_index']}. {s['original_url'][:50]}" for s in slots]
    )
    await message.answer(
        text("ad_creative:slots_found").format(len(slots), links_text),
        disable_web_page_preview=True,
    )

    await message.answer(text("ad_creative:enter_name"))
    await state.update_data(creative_id=creative_id)
    await state.set_state(AdCreativeStates.entering_name)


@router.message(AdCreativeStates.entering_name)
@safe_handler(
    "Креативы: обработка имени"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def process_creative_name(message: Message, state: FSMContext) -> None:
    """
    Обработка ввода имени креатива.
    Завершает создание креатива.

    Аргументы:
        message (Message): Сообщение с именем.
        state (FSMContext): Контекст состояния.
    """
    name = message.text.strip()
    if not name:
        await message.answer(text("ad_creative:empty_name"))
        return

    data = await state.get_data()
    creative_id = data.get("creative_id")

    query = update(AdCreative).where(AdCreative.id == creative_id).values(name=name)
    await db.execute(query)

    await state.update_data(name=name)
    
    # Вместо завершения, переходим к выбору ресурсов
    channels = await db.channel.get_user_channels(message.from_user.id)
    await state.update_data(selected_resource_ids=[])
    
    await message.answer(
        text("ad_creative:select_resources_text"),
        reply_markup=InlineAdCreative.resource_selection_menu(channels, []),
    )
    await state.set_state(AdCreativeStates.selecting_resources)


@router.callback_query(F.data == "AdCreative|list")
@safe_handler(
    "Креативы: список"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def list_creatives(call: CallbackQuery) -> None:
    """
    Отображение списка креативов пользователя.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    creatives = await db.ad_creative.get_user_creatives(call.from_user.id)

    creatives_with_slots = []
    for c in creatives:
        slots = await db.ad_creative.get_slots(c.id)
        c.slots = slots  # Манкипатчинг для отображения
        creatives_with_slots.append(c)

    if not creatives_with_slots:
        await call.message.edit_text(
            text("ad_creative:list_empty"), reply_markup=InlineAdCreative.menu()
        )
        return

    await call.message.edit_text(
        text("ad_creative:list_title"),
        reply_markup=InlineAdCreative.creative_list(creatives_with_slots),
    )


@router.callback_query(F.data == "AdCreative|cancel_creation")
@safe_handler(
    "Креативы: отмена создания"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def cancel_creation(call: CallbackQuery, state: FSMContext) -> None:
    """
    Отмена создания креатива.

    Аргументы:
        call (CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await state.clear()
    await call.message.edit_text(
        text("ad_creative:cancelled"), reply_markup=InlineAdCreative.menu()
    )


@router.callback_query(F.data.startswith("AdCreative|delete|"))
@safe_handler(
    "Креативы: удаление"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def delete_creative(call: CallbackQuery) -> None:
    """
    Удаление креатива (Soft Delete - пометка удаленным).

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    creative_id = int(call.data.split("|")[2])
    await db.ad_creative.update_creative_status(creative_id, "deleted")
    await call.answer(text("ad_creative:deleted"))
    # Перезагрузка главного меню
    await reload_main_menu(call.message)

    # Проверка оставшихся
    creatives = await db.ad_creative.get_user_creatives(call.from_user.id)
    if not creatives:
        await call.message.edit_text(
            text("ad_creative:menu_title"), reply_markup=InlineAdCreative.menu()
        )
    else:
        await list_creatives(call)


@router.callback_query(F.data.startswith("AdCreative|view|"))
@safe_handler(
    "Креативы: просмотр"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def view_creative(call: CallbackQuery) -> None:
    """
    Просмотр подробной информации о креативе.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    creative_id = int(call.data.split("|")[2])
    creative = await db.ad_creative.get_creative(creative_id)
    if not creative:
        await call.answer(text("ad_creative:not_found"))
        return

    slots = await db.ad_creative.get_slots(creative_id)
    links_text = "\n".join([f"{s.slot_index}. {s.original_url[:50]}" for s in slots])

    text_content = text("ad_creative:view_template").format(
        name=creative.name,
        created=creative.created_timestamp,
        count=len(slots),
        links=links_text,
    )

    await call.message.edit_text(
        text_content,
        reply_markup=InlineAdCreative.creative_view(creative_id),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "AdCreative|back")
@safe_handler(
    "Креативы: возврат в админ-меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_to_menu(call: CallbackQuery) -> None:
    """
    Возврат в меню закупки рекламы.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    # Возврат в меню покупки рекламы
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=text("btn_ad_creatives"), callback_data="AdBuyMenu|creatives"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=text("btn_ad_purchases"), callback_data="AdBuyMenu|purchases"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=text("btn_back"), callback_data="AdBuyMenu|back"
                )
            ],
        ]
    )
    await call.message.edit_text(text("ad_buy_menu:title"), reply_markup=kb)


@router.callback_query(F.data == "AdCreative|menu")
@safe_handler(
    "Креативы: меню креативов"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_to_ad_menu(call: CallbackQuery) -> None:
    """
    Возврат в меню управления креативами.

    Аргументы:
        call (CallbackQuery): Callback запрос.
    """
    await call.message.edit_text(
        text("ad_creative:menu_title"), reply_markup=InlineAdCreative.menu()
    )


@router.callback_query(AdCreativeStates.selecting_resources, F.data.startswith("AdCreative|toggle_res|"))
@safe_handler("Креативы: переключение ресурса")
async def toggle_resource(call: CallbackQuery, state: FSMContext) -> None:
    """Переключение выбора ресурса (канала) для авто-маппинга"""
    chat_id = int(call.data.split("|")[2])
    data = await state.get_data()
    selected = data.get("selected_resource_ids", [])
    
    if chat_id in selected:
        selected.remove(chat_id)
    else:
        selected.append(chat_id)
        
    await state.update_data(selected_resource_ids=selected)
    
    channels = await db.channel.get_user_channels(call.from_user.id)
    await call.message.edit_reply_markup(
        reply_markup=InlineAdCreative.resource_selection_menu(channels, selected)
    )
    await call.answer()


@router.callback_query(AdCreativeStates.selecting_resources, F.data == "AdCreative|confirm_resources")
@safe_handler("Креативы: подтверждение ресурсов и авто-маппинг")
async def confirm_resources(call: CallbackQuery, state: FSMContext) -> None:
    """Запуск процесса авто-маппинга и завершение создания креатива"""
    data = await state.get_data()
    creative_id = data.get("creative_id")
    selected_ids = data.get("selected_resource_ids", [])
    name = data.get("name")
    
    await call.message.edit_text("⏳ Запускаю автоматическую проверку ссылок...")
    
    from sqlalchemy import update
    from main_bot.database.ad_creative.model import AdCreativeLinkSlot
    
    # 1. Сохраняем имя креатива (которое ввели на прошлом шаге)
    query = update(AdCreative).where(AdCreative.id == creative_id).values(name=name)
    await db.execute(query)
    
    # 2. Получаем слоты
    slots = await db.ad_creative.get_slots(creative_id)
    auto_mapped_count = 0
    
    for slot in slots:
        found_channel_id = None
        orig_url = slot.original_url.lower().strip()
        
        # А) Проверка публичных ссылок t.me/username
        if "t.me/" in orig_url and "+" not in orig_url and "joinchat/" not in orig_url:
            username = orig_url.split("t.me/")[-1].split("/")[0].replace("@", "")
            for ch_id in selected_ids:
                try:
                    chat = await call.bot.get_chat(ch_id)
                    if chat.username and chat.username.lower() == username:
                        found_channel_id = ch_id
                        break
                except Exception:
                    continue
        
        # Б) Проверка пригласительных ссылок через getChatInviteLink
        if not found_channel_id and ("t.me/+" in orig_url or "joinchat" in orig_url):
            for ch_id in selected_ids:
                try:
                    await call.bot.get_chat_invite_link(ch_id, slot.original_url)
                    found_channel_id = ch_id
                    break
                except Exception:
                    continue
                    
        if found_channel_id:
            stmt = update(AdCreativeLinkSlot).where(AdCreativeLinkSlot.id == slot.id).values(
                suggested_channel_id=found_channel_id
            )
            await db.execute(stmt)
            auto_mapped_count += 1

    await call.message.edit_text(f"✅ Авто-проверка завершена. Найдено совпадений: {auto_mapped_count}.\n\nВы можете вручную сопоставить оставшиеся ссылки или изменить текущие.")
    await _show_creative_mapping_menu(call, state)


async def _show_creative_mapping_menu(call: CallbackQuery, state: FSMContext):
    """Вспомогательная функция для показа меню маппинга креатива"""
    data = await state.get_data()
    creative_id = data.get("creative_id")
    
    slots = await db.ad_creative.get_slots(creative_id)
    channels = await db.channel.get_user_channels(call.from_user.id)
    channels_map = {ch.chat_id: ch.title for ch in channels}
    
    links_data = []
    for s in slots:
        links_data.append({
            "slot_id": s.id,
            "original_url": s.original_url[:30] + "..." if len(s.original_url) > 30 else s.original_url,
            "channel_name": channels_map.get(s.suggested_channel_id) if s.suggested_channel_id else None
        })
        
    await call.message.edit_text(
        text("ad_creative:manual_mapping_title"),
        reply_markup=InlineAdCreative.creative_mapping_menu(links_data)
    )
    await state.set_state(AdCreativeStates.mapping_links)


@router.callback_query(AdCreativeStates.mapping_links, F.data.startswith("AdCreative|map_slot|"))
@safe_handler("Креативы: выбор канала для слота")
async def manual_map_slot(call: CallbackQuery, state: FSMContext) -> None:
    """Показ меню выбора канала для конкретного слота"""
    slot_id = int(call.data.split("|")[2])
    channels = await db.channel.get_user_channels(call.from_user.id)
    
    await call.message.edit_text(
        text("ad_creative:select_channel_for_slot"),
        reply_markup=InlineAdCreative.channel_selection(channels, slot_id)
    )


@router.callback_query(AdCreativeStates.mapping_links, F.data.startswith("AdCreative|set_slot|"))
@safe_handler("Креативы: привязка канала к слоту")
async def handle_set_slot(call: CallbackQuery, state: FSMContext) -> None:
    """Привязка выбранного канала к слоту в БД"""
    parts = call.data.split("|")
    slot_id = int(parts[2])
    chat_id_str = parts[3]
    
    chat_id = int(chat_id_str) if chat_id_str != "none" else None
    
    from sqlalchemy import update
    from main_bot.database.ad_creative.model import AdCreativeLinkSlot
    
    stmt = update(AdCreativeLinkSlot).where(AdCreativeLinkSlot.id == slot_id).values(
        suggested_channel_id=chat_id
    )
    await db.execute(stmt)
    
    await _show_creative_mapping_menu(call, state)
    await call.answer()


@router.callback_query(AdCreativeStates.mapping_links, F.data == "AdCreative|back_to_mapping")
@safe_handler("Креативы: возврат к маппингу")
async def handle_back_to_mapping(call: CallbackQuery, state: FSMContext) -> None:
    """Возврат из меню выбора канала в меню маппинга"""
    await _show_creative_mapping_menu(call, state)
    await call.answer()


@router.callback_query(AdCreativeStates.mapping_links, F.data == "AdCreative|finish_mapping")
@safe_handler("Креативы: завершение создания")
async def handle_finish_mapping(call: CallbackQuery, state: FSMContext) -> None:
    """Окончательное завершение создания креатива"""
    data = await state.get_data()
    name = data.get("name")
    
    await call.message.answer(
        text("ad_creative:created_success").format(name),
        reply_markup=InlineAdCreative.menu(),
    )
    # Перезагрузка главного меню
    await reload_main_menu(call.message)
    await state.clear()
    await call.answer()
