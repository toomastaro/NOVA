"""
Middleware для сброса состояния FSM.

Этот модуль содержит middleware, который проверяет, соответствует ли входящее сообщение
кнопке главного меню. Если да, он сбрасывает текущее состояние FSM.
"""

import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update, Message

from main_bot.keyboards.common import Reply

logger = logging.getLogger(__name__)


class StateResetMiddleware(BaseMiddleware):
    """
    Middleware, который проверяет, соответствует ли входящее сообщение кнопке
    главного меню. Если да, то сбрасывает текущее состояние FSM.
    """

    def __init__(self):
        super().__init__()
        self._main_menu_texts = set()
        self._load_menu_texts()

    def _load_menu_texts(self):
        try:
            # Нам нужно собрать все возможные тексты кнопок для сброса состояния.
            # Собираем кнопки для администратора и для обычного пользователя.
            
            # 1. Кнопки администратора
            admin_id = Config.ADMINS[0] if Config.ADMINS else 0
            markup_admin = Reply.menu(admin_id)
            if markup_admin.keyboard:
                for row in markup_admin.keyboard:
                    for button in row:
                        if button.text:
                            self._main_menu_texts.add(button.text)

            # 2. Кнопки обычного пользователя
            markup_user = Reply.menu(0)
            if markup_user.keyboard:
                for row in markup_user.keyboard:
                    for button in row:
                        if button.text:
                            self._main_menu_texts.add(button.text)

            # Также добавляем "🛒 Закуп" явно, если это зависит от конфига
            # Но Reply.menu() уже проверяет Config. Так что это соответствует текущему конфигу при запуске.
            self._main_menu_texts.add("🛒 Закуп")

            logger.info(
                f"StateResetMiddleware инициализирован с {len(self._main_menu_texts)} кнопками меню: {self._main_menu_texts}"
            )
        except Exception as e:
            logger.error(
                f"Не удалось загрузить тексты главного меню для StateResetMiddleware: {e}",
                exc_info=True,
            )

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text:
            text = event.text
            # Если событие само по себе Message (в aiogram 3.x event это Update, но middleware может вешаться на message)
            # В BaseMiddleware outer event - это Update.
            # Если мы вешаем на message роутер, то event будет Message.
            # Проверим тип event.
            pass

        # В BaseMiddleware __call__ получает event типа Update, Message, CallbackQuery и т.д. в зависимости от того, куда подключен.
        # Обычно подключается к dispatcher.update, тогда event: Update.

        message: Message | None = None
        if isinstance(event, Update) and event.message:
            message = event.message
        elif isinstance(event, Message):
            message = event

        if message and message.text:
            text = message.text

            # Проверяем, совпадает ли текст с любой кнопкой главного меню
            if text in self._main_menu_texts:
                state = data.get("state")
                if state:
                    current_state = await state.get_state()
                    if current_state:
                        logger.debug(
                            f"Нажата кнопка главного меню '{text}'. Сброс состояния {current_state}"
                        )
                        await state.clear()

        return await handler(event, data)
