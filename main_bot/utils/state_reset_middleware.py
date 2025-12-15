from aiogram import BaseMiddleware
from aiogram.types import Update
import logging

from main_bot.keyboards.common import Reply

logger = logging.getLogger(__name__)

class StateResetMiddleware(BaseMiddleware):
    """
    Middleware that checks if the incoming message corresponds to a button
    on the Main Menu. If so, it clears the current FSM state.
    """
    
    def __init__(self):
        super().__init__()
        self._main_menu_texts = set()
        self._load_menu_texts()
        
    def _load_menu_texts(self):
        try:
            # Generate the menu markup
            markup = Reply.menu()
            if markup.keyboard:
                for row in markup.keyboard:
                    for button in row:
                        if button.text:
                            self._main_menu_texts.add(button.text)
            
            # Also add "🛒 Закуп" explicitly if it depends on config
            # But Reply.menu() already checks Config. So it matches the current runtime config.
            self._main_menu_texts.add("🛒 Закуп")
            
            logger.info(f"StateResetMiddleware initialized with {len(self._main_menu_texts)} menu buttons: {self._main_menu_texts}")
        except Exception as e:
            logger.error(f"Failed to load main menu texts for StateResetMiddleware: {e}", exc_info=True)

    async def __call__(self, handler, event: Update, data):
        if event.message and event.message.text:
            text = event.message.text
            
            # Check if text matches any main menu button
            if text in self._main_menu_texts:
                state = data.get("state")
                if state:
                    current_state = await state.get_state()
                    if current_state:
                         logger.debug(f"Main menu button '{text}' pressed. Clearing state {current_state}")
                         await state.clear()
        
        return await handler(event, data)
