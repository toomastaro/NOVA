import json
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from main_bot.database.db import db
from main_bot.database.ad_creative.model import AdCreative
from main_bot.keyboards import keyboards, InlineAdCreative
from main_bot.states.user import AdCreativeStates
from main_bot.utils.lang.language import text


router = Router(name="AdCreative")


@router.callback_query(F.data == "AdCreative|create")
async def create_creative_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Перешлите пост или подборку постов, из которых нужно сделать креатив.")
    await state.set_state(AdCreativeStates.waiting_for_content)
    await call.answer()


@router.message(AdCreativeStates.waiting_for_content)
async def process_creative_content(message: Message, state: FSMContext):
    # Serialize message
    # Use model_dump_json() then json.loads() to handle Pydantic types correctly and avoid Default type issues
    raw_message = json.loads(message.model_dump_json())
    
    # Extract links
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
        await message.answer("В сообщении не найдено ссылок. Креатив не может быть создан без ссылок. Попробуйте другое сообщение.")
        return

    # Create Creative
    creative_id = await db.create_creative(
        owner_id=message.from_user.id,
        name="Без названия", # Temporary name
        raw_message=raw_message
    )
    
    await db.create_slots_for_creative(creative_id, slots)
    
    # Show found links
    links_text = "\n".join([f"{s['slot_index']}. {s['original_url'][:50]}" for s in slots])
    await message.answer(f"В креативе найдено {len(slots)} ссылок:\n{links_text}", disable_web_page_preview=True)
    
    await message.answer("Введите имя для креатива:")
    await state.update_data(creative_id=creative_id)
    await state.set_state(AdCreativeStates.waiting_for_name)


@router.message(AdCreativeStates.waiting_for_name)
async def process_creative_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым. Введите имя:")
        return

    data = await state.get_data()
    creative_id = data.get("creative_id")
    
    # We don't have update_creative method in CRUD yet, but we can use execute or add it.
    # Wait, the user didn't ask to add update method in CRUD, but I can add it or use raw SQL.
    # Actually, I should probably add it to CRUD or use a generic update if available.
    # DatabaseMixin has execute.
    
    # Let's check if there is a generic update.
    # I'll just use a direct update query here for now or add a method to CRUD if I can.
    # But I can't easily modify CRUD file now without context switch.
    # I'll use db.execute with text query or sqlalchemy update.
    
    from sqlalchemy import update
    query = update(AdCreative).where(AdCreative.id == creative_id).values(name=name)
    await db.execute(query)
    
    await message.answer(f"Креатив '{name}' успешно создан!", reply_markup=InlineAdCreative.menu())
    await state.clear()


@router.callback_query(F.data == "AdCreative|list")
async def list_creatives(call: CallbackQuery):
    creatives = await db.get_user_creatives(call.from_user.id)
    # We need slots count for each.
    # This is N+1 but okay for small lists.
    # Or we could join. For now, simple loop.
    
    creatives_with_slots = []
    for c in creatives:
        slots = await db.get_slots(c.id)
        c.slots = slots # Monkey patch for display
        creatives_with_slots.append(c)
        
    await call.message.edit_text(
        "Ваши креативы:",
        reply_markup=InlineAdCreative.creative_list(creatives_with_slots)
    )


@router.callback_query(F.data.startswith("AdCreative|delete|"))
async def delete_creative(call: CallbackQuery):
    creative_id = int(call.data.split("|")[2])
    await db.update_creative_status(creative_id, "deleted")
    await call.answer("Креатив удален")
    await list_creatives(call)


@router.callback_query(F.data.startswith("AdCreative|view|"))
async def view_creative(call: CallbackQuery):
    creative_id = int(call.data.split("|")[2])
    creative = await db.get_creative(creative_id)
    if not creative:
        await call.answer("Креатив не найден")
        return
        
    slots = await db.get_slots(creative_id)
    links_text = "\n".join([f"{s.slot_index}. {s.original_url[:50]}" for s in slots])
    
    text = (
        f"Креатив: {creative.name}\n"
        f"Создан: {creative.created_timestamp}\n"
        f"Ссылок: {len(slots)}\n\n"
        f"{links_text}"
    )
    
    await call.message.edit_text(
        text,
        reply_markup=InlineAdCreative.creative_view(creative_id),
        disable_web_page_preview=True
    )


@router.callback_query(F.data == "AdCreative|back")
async def back_to_menu(call: CallbackQuery):
    await call.message.delete()
    # Assuming main menu is reply keyboard, so we just delete the inline message?
    # Or if this was a sub-menu.
    # The user said "При выборе этого пункта показывать клавиатуру".
    # If it was an inline message sent on reply button click, then back should probably delete it or go to main inline menu if exists.
    # But "Рекламные креативы" is a Reply button.
    # Usually reply buttons trigger a new message.
    # So "Back" should probably just delete the message.
    pass

@router.callback_query(F.data == "AdCreative|menu")
async def back_to_ad_menu(call: CallbackQuery):
    await call.message.edit_text("Рекламные креативы", reply_markup=InlineAdCreative.menu())
