from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from config import Config
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.utils.middlewares import StartMiddle
import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Start Command")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Check for ref-parameter for lead tracking
    if message.text and len(message.text.split()) > 1:
        start_param = message.text.split()[1]
        
        if start_param.startswith("ref_"):
            # Extract purchase_id and slot_id from ref parameter
            try:
                # Format: ref_{purchase_id}_{slot_id}
                params = start_param[4:]  # Remove "ref_" prefix
                parts = params.split("_")
                
                if len(parts) >= 2:
                    purchase_id = int(parts[0])
                    slot_id = int(parts[1])
                    
                    # Add lead (silently, no user feedback)
                    from main_bot.database.db import db
                    await db.add_lead(
                        user_id=message.from_user.id,
                        ad_purchase_id=purchase_id,
                        slot_id=slot_id,
                        ref_param=start_param
                    )
            except (ValueError, IndexError):
                # Invalid ref parameter format, ignore
                pass
    
    await message.answer(
        text("start_text") + f"\n\nVersion: {Config.VERSION}\n\n"
        f"📄 <a href='{text('info:terms:url')}'>Пользовательское соглашение</a>\n"
        f"🔒 <a href='{text('info:privacy:url')}'>Политика конфиденциальности</a>",
        reply_markup=keyboards.menu(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


def hand_add():
    router = Router()
    router.message.middleware(StartMiddle())
    router.message.register(start, CommandStart())
    return router
