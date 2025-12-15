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
    await call.message.edit_text(
        "Перешлите пост или подборку постов, из которых нужно сделать креатив.",
        reply_markup=InlineAdCreative.create_creative_cancel()
    )
    await state.set_state(AdCreativeStates.waiting_for_content)
    # Don't answer callback if we edited text, but wait, usually we answer callbacks to stop loading animation.
    # call.answer() is fine.
    # But wait, original code used call.message.answer, creating a NEW message. 
    # If we want "Back" behavior, editing is often better, but if it was a new message, user might expect new message.
    # However, for "Cancel" flow, staying in same message (edit) is usually cleaner.
    # I will change .answer to .edit_text to keep context, or .answer if "Back" button in menu expects new message stack.
    # Inline menu usually edits.
    # Original code: await call.message.answer(...)
    # I will change to edit_text for smoother experience as requested ("cancel... button leads back").
    await call.answer()


@router.message(AdCreativeStates.waiting_for_content)
async def process_creative_content(message: Message, state: FSMContext):
    # Serialize message safely
    # 1. Use exclude_defaults=True to avoid 'Default' type serialization error (aiogram 3.x)
    raw_message = json.loads(message.model_dump_json(exclude_defaults=True))
    
    # 2. Manually restore entities if they were stripped or if we want to ensure they are present
    # (Previously exclude_defaults seemed to strip them or cause issues)
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
            "В сообщении не найдено ссылок. Креатив не может быть создан без ссылок. Попробуйте другое сообщение.\n\n"
            "Перешлите пост или подборку постов, из которых нужно сделать креатив.",
            reply_markup=InlineAdCreative.create_creative_cancel()
        )
        return

    # Create Creative
    creative_id = await db.ad_creative.create_creative(
        owner_id=message.from_user.id,
        name="Без названия", # Temporary name
        raw_message=raw_message
    )
    
    await db.ad_creative.create_slots_for_creative(creative_id, slots)
    
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
    creatives = await db.ad_creative.get_user_creatives(call.from_user.id)
    # We need slots count for each.
    # This is N+1 but okay for small lists.
    # Or we could join. For now, simple loop.
    
    creatives_with_slots = []
    for c in creatives:
        slots = await db.ad_creative.get_slots(c.id)
        c.slots = slots # Monkey patch for display
        creatives_with_slots.append(c)
        
    if not creatives_with_slots:
        await call.message.edit_text(
            "У вас пока нет созданных креативов.\nНажмите 'Создать креатив', чтобы добавить первый.",
            reply_markup=InlineAdCreative.menu()
        )
        return

    await call.message.edit_text(
        "Ваши креативы:",
        reply_markup=InlineAdCreative.creative_list(creatives_with_slots)
    )


@router.callback_query(F.data == "AdCreative|cancel_creation")
async def cancel_creation(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Создание креатива отменено.", reply_markup=InlineAdCreative.menu())


@router.callback_query(F.data.startswith("AdCreative|delete|"))
async def delete_creative(call: CallbackQuery):
    creative_id = int(call.data.split("|")[2])
    await db.ad_creative.update_creative_status(creative_id, "deleted")
    await call.answer("Креатив удален")
    
    # Check remaining
    creatives = await db.ad_creative.get_user_creatives(call.from_user.id)
    if not creatives:
        # No creatives left, go to main menu
        # Assuming we can go back to Ad Buy Menu or specific Creative Menu
        # User said: "перенапрявлять на раздел 🎨 Рекламные креативы" (AdCreative|menu)
        # But AdCreative|menu has "List", "Create".
        # If list is empty, list_creatives handles it.
        # But user wants specific behavior: if LAST deleted -> AdCreative|menu
        await call.message.edit_text("Рекламные креативы", reply_markup=InlineAdCreative.menu())
    else:
        await list_creatives(call)


@router.callback_query(F.data.startswith("AdCreative|view|"))
async def view_creative(call: CallbackQuery):
    creative_id = int(call.data.split("|")[2])
    creative = await db.ad_creative.get_creative(creative_id)
    if not creative:
        await call.answer("Креатив не найден")
        return
        
    slots = await db.ad_creative.get_slots(creative_id)
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
    # Navigate back to Ad Buy Menu
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎨 Рекламные креативы", callback_data="AdBuyMenu|creatives")],
        [types.InlineKeyboardButton(text="💰 Рекламные закупы", callback_data="AdBuyMenu|purchases")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="AdBuyMenu|back")]
    ])
    await call.message.edit_text("🛒 <b>Закуп</b>\n\nВыберите раздел:", reply_markup=kb)

@router.callback_query(F.data == "AdCreative|menu")
async def back_to_ad_menu(call: CallbackQuery):
    await call.message.edit_text("Рекламные креативы", reply_markup=InlineAdCreative.menu())
