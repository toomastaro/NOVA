"""
Модуль обработчиков для управления рекламными креативами.
Позволяет создавать, просматривать и удалять креативы.
"""
import json
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from main_bot.database.db import db
from main_bot.database.ad_creative.model import AdCreative
from main_bot.keyboards import InlineAdCreative
from main_bot.states.user import AdCreativeStates
from main_bot.utils.lang.language import text
from main_bot.utils.error_handler import safe_handler

router = Router(name="AdCreative")


@router.callback_query(F.data == "AdCreative|create")
@safe_handler("Create Creative Start")
async def create_creative_start(call: CallbackQuery, state: FSMContext):
    """Начало создания креатива."""
    await call.message.edit_text(
        text('ad_creative:create_start_text'),
        reply_markup=InlineAdCreative.create_creative_cancel()
    )
    await state.set_state(AdCreativeStates.waiting_for_content)
    await call.answer()


@router.message(AdCreativeStates.waiting_for_content)
@safe_handler("Process Creative Content")
async def process_creative_content(message: Message, state: FSMContext):
    """Обработка пересланного контента для создания креатива."""

    raw_message = json.loads(message.model_dump_json(exclude_defaults=True))
    

    if message.entities:
        raw_message['entities'] = [e.model_dump(mode='json') for e in message.entities]
    if message.caption_entities:
        raw_message['caption_entities'] = [e.model_dump(mode='json') for e in message.caption_entities]
    slots = []
    slot_index = 1
    
    def add_slot(url, loc_type, meta):
        nonlocal slot_index
        slots.append({
            "slot_index": slot_index,
            "original_url": url,
            "location_type": loc_type,
            "location_meta": meta
        })
        slot_index += 1

    # 1. Entities
    if message.caption_entities:
        for i, entity in enumerate(message.caption_entities):
            if entity.type == "text_link":
                add_slot(entity.url, "text", {"entity_index": i, "field": "caption"})
            elif entity.type == "url":
                # Extract URL from text
                url = message.caption[entity.offset:entity.offset + entity.length]
                add_slot(url, "text", {"entity_index": i, "field": "caption"})

    if message.entities:
        for i, entity in enumerate(message.entities):
            if entity.type == "text_link":
                add_slot(entity.url, "text", {"entity_index": i, "field": "text"})
            elif entity.type == "url":
                url = message.text[entity.offset:entity.offset + entity.length]
                add_slot(url, "text", {"entity_index": i, "field": "text"})

    # 2. Inline Keyboard
    if message.reply_markup and message.reply_markup.inline_keyboard:
        for r, row in enumerate(message.reply_markup.inline_keyboard):
            for c, btn in enumerate(row):
                if btn.url:
                    add_slot(btn.url, "button", {"button_row": r, "button_col": c})

    if not slots:
        await message.answer(
            text('ad_creative:no_links_found'),
            reply_markup=InlineAdCreative.create_creative_cancel()
        )
        return

    # Create Creative
    creative_id = await db.ad_creative.create_creative(
        owner_id=message.from_user.id,
        name=text('ad_creative:default_name'), # Temporary name
        raw_message=raw_message
    )
    
    await db.ad_creative.create_slots_for_creative(creative_id, slots)
    
    # Show found links
    links_text = "\n".join([f"{s['slot_index']}. {s['original_url'][:50]}" for s in slots])
    await message.answer(
        text('ad_creative:slots_found').format(len(slots), links_text),
        disable_web_page_preview=True
    )
    
    await message.answer(text('ad_creative:enter_name'))
    await state.update_data(creative_id=creative_id)
    await state.set_state(AdCreativeStates.waiting_for_name)


@router.message(AdCreativeStates.waiting_for_name)
@safe_handler("Process Creative Name")
async def process_creative_name(message: Message, state: FSMContext):
    """Обработка ввода имени креатива."""
    name = message.text.strip()
    if not name:
        await message.answer(text('ad_creative:empty_name'))
        return

    data = await state.get_data()
    creative_id = data.get("creative_id")
    

    
    from sqlalchemy import update
    query = update(AdCreative).where(AdCreative.id == creative_id).values(name=name)
    await db.execute(query)
    
    await message.answer(
        text('ad_creative:created_success').format(name),
        reply_markup=InlineAdCreative.menu()
    )
    await state.clear()


@router.callback_query(F.data == "AdCreative|list")
@safe_handler("List Creatives")
async def list_creatives(call: CallbackQuery):
    """Список креативов пользователя."""
    creatives = await db.ad_creative.get_user_creatives(call.from_user.id)

    
    creatives_with_slots = []
    for c in creatives:
        slots = await db.ad_creative.get_slots(c.id)
        c.slots = slots # Monkey patch for display
        creatives_with_slots.append(c)
        
    if not creatives_with_slots:
        await call.message.edit_text(
            text('ad_creative:list_empty'),
            reply_markup=InlineAdCreative.menu()
        )
        return

    await call.message.edit_text(
        text('ad_creative:list_title'),
        reply_markup=InlineAdCreative.creative_list(creatives_with_slots)
    )


@router.callback_query(F.data == "AdCreative|cancel_creation")
@safe_handler("Cancel Creative Creation")
async def cancel_creation(call: CallbackQuery, state: FSMContext):
    """Отмена создания креатива."""
    await state.clear()
    await call.message.edit_text(
        text('ad_creative:cancelled'),
        reply_markup=InlineAdCreative.menu()
    )


@router.callback_query(F.data.startswith("AdCreative|delete|"))
@safe_handler("Delete Creative")
async def delete_creative(call: CallbackQuery):
    """Удаление креатива (Soft Delete)."""
    creative_id = int(call.data.split("|")[2])
    await db.ad_creative.update_creative_status(creative_id, "deleted")
    await call.answer(text('ad_creative:deleted'))
    
    # Check remaining
    creatives = await db.ad_creative.get_user_creatives(call.from_user.id)
    if not creatives:
  
        await call.message.edit_text(
            text('ad_creative:menu_title'),
            reply_markup=InlineAdCreative.menu()
        )
    else:
        await list_creatives(call)


@router.callback_query(F.data.startswith("AdCreative|view|"))
@safe_handler("View Creative")
async def view_creative(call: CallbackQuery):
    """Просмотр деталей креатива."""
    creative_id = int(call.data.split("|")[2])
    creative = await db.ad_creative.get_creative(creative_id)
    if not creative:
        await call.answer(text('ad_creative:not_found'))
        return
        
    slots = await db.ad_creative.get_slots(creative_id)
    links_text = "\n".join([f"{s.slot_index}. {s.original_url[:50]}" for s in slots])
    
    text_content = text('ad_creative:view_template').format(
        name=creative.name,
        created=creative.created_timestamp,
        count=len(slots),
        links=links_text
    )
    
    await call.message.edit_text(
        text_content,
        reply_markup=InlineAdCreative.creative_view(creative_id),
        disable_web_page_preview=True
    )


@router.callback_query(F.data == "AdCreative|back")
@safe_handler("Back To Ad Menu")
async def back_to_menu(call: CallbackQuery):
    """Возврат в меню закупки рекламы."""
    # Navigate back to Ad Buy Menu
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=text("btn_ad_creatives"), callback_data="AdBuyMenu|creatives")],
        [types.InlineKeyboardButton(text=text("btn_ad_purchases"), callback_data="AdBuyMenu|purchases")],
        [types.InlineKeyboardButton(text=text("btn_back"), callback_data="AdBuyMenu|back")]
    ])
    await call.message.edit_text(
        text('ad_buy_menu:title'), 
        reply_markup=kb
    )

@router.callback_query(F.data == "AdCreative|menu")
@safe_handler("Ad Creative Menu")
async def back_to_ad_menu(call: CallbackQuery):
    """Возврат в главное меню креативов."""
    await call.message.edit_text(
        text('ad_creative:menu_title'),
        reply_markup=InlineAdCreative.menu()
    )
