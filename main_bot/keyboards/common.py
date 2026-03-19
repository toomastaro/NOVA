"""
Общие клавиатуры: Reply-клавиатуры, базовые inline-кнопки (назад, отмена и т.п.).
"""

from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from main_bot.utils.lang.language import text
from config import Config


class Reply:
    """Reply-клавиатуры (главное меню, капча)"""

    @classmethod
    def menu(cls, user_id: int = 0):
        """
        Создает главное меню бота.
        Для администраторов отображается полный список функций.
        Для обычных пользователей - сокращенный список согласно ТЗ.

        Аргументы:
            user_id (int): ID пользователя в Telegram.

        Возвращает:
            ReplyKeyboardMarkup: Объект клавиатуры.
        """
        kb = ReplyKeyboardBuilder()
        is_admin = user_id in Config.ADMINS

        if is_admin:
            # Полное меню для администраторов (сетка 3x3)
            # Первый ряд: Постинг - Истории - Рассылка
            kb.button(text=text("reply_menu:posting"))
            kb.button(text=text("reply_menu:story"))
            kb.button(text=text("reply_menu:bots"))

            # Второй ряд: Приветка - NovaStat - Закуп/Настройки (в зависимости от флага)
            kb.button(text=text("reply_menu:privetka"))
            kb.button(text=text("reply_menu:novastat"))

            if Config.ENABLE_AD_BUY_MODULE:
                kb.button(text="🛒 Закуп")
            else:
                kb.button(text=text("reply_menu:profile"))

            # Третий ряд: Курс USDT - Подписка - Настройки/Ничего
            kb.button(text=text("reply_menu:exchange_rate"))
            kb.button(text=text("reply_menu:subscription"))
            kb.button(text=text("reply_menu:profile"))

            kb.adjust(3, 3, 3)
        else:
            # Сокращенное меню для обычных пользователей (сетка 2x3)
            # Постинг | Курс USDT
            kb.button(text=text("reply_menu:posting"))
            kb.button(text=text("reply_menu:exchange_rate"))

            # Рассылка | Приветка
            kb.button(text=text("reply_menu:bots"))
            kb.button(text=text("reply_menu:privetka"))

            # Подписка | Настройки
            kb.button(text=text("reply_menu:subscription"))
            kb.button(text=text("reply_menu:profile"))

            kb.adjust(2, 2, 2)

        return kb.as_markup(resize_keyboard=True, is_persistent=True)

    @classmethod
    def captcha_kb(cls, buttons: str, resize: bool = True):
        kb = ReplyKeyboardBuilder()

        for row in buttons.split("\n"):
            buttons = [
                KeyboardButton(
                    text=button.strip(),
                )
                for button in row.split("|")
            ]
            kb.row(*buttons)

        return kb.as_markup(resize_keyboard=resize)


class InlineCommon(InlineKeyboardBuilder):
    """Общие inline-кнопки: назад, отмена, подтверждение"""

    @classmethod
    def cancel(cls, data: str):
        kb = cls()

        kb.button(text=text("back:button"), callback_data=data)

        return kb.as_markup()

    @classmethod
    def back(cls, data: str):
        kb = cls()

        kb.button(text=text("back:button"), callback_data=data)

        return kb.as_markup()

    @classmethod
    def accept(cls, data: str):
        kb = cls()

        kb.button(text=text("delete:button"), callback_data=data + "|yes")
        kb.button(text=text("back:button"), callback_data=data)

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def wait_payment(cls, data: str, pay_url: str):
        kb = cls()

        kb.button(text=text("go_to_payment"), url=pay_url)
        kb.button(text=text("cancel"), callback_data=f"{data}")

        kb.adjust(1)
        return kb.as_markup()
