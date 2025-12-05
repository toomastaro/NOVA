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
    def menu(cls):
        kb = ReplyKeyboardBuilder()

        # Первый ряд: Постинг - Истории - Рассылка
        kb.button(text=text('reply_menu:posting'))
        kb.button(text=text('reply_menu:story'))
        kb.button(text=text('reply_menu:bots'))
        
        # Второй ряд: Курс USDT - NovaStat - Настройки
        kb.button(text=text('reply_menu:exchange_rate'))
        kb.button(text=text('reply_menu:novastat'))
        kb.button(text=text('reply_menu:profile'))
        
        # Третий ряд: Книга жалоб и предложений
        kb.button(text=text('reply_menu:support'))

        if Config.ENABLE_AD_BUY_MODULE:
            kb.button(text="Рекламные креативы")
            kb.button(text="Рекламные закупы")

        kb.adjust(3, 3, 1)  # 3 кнопки в первом ряду, 3 во втором, 1 в третьем
        return kb.as_markup(
            resize_keyboard=True,
        )
        

    @classmethod
    def captcha_kb(cls, buttons: str, resize: bool = True):
        kb = ReplyKeyboardBuilder()

        for row in buttons.split('\n'):
            buttons = [
                KeyboardButton(
                    text=button.strip(),
                ) for button in row.split('|')
            ]
            kb.row(*buttons)

        return kb.as_markup(
            resize_keyboard=resize
        )


class InlineCommon(InlineKeyboardBuilder):
    """Общие inline-кнопки: назад, отмена, подтверждение"""
    
    @classmethod
    def cancel(cls, data: str):
        kb = cls()

        kb.button(
            text=text('cancel'),
            callback_data=data
        )

        return kb.as_markup()

    @classmethod
    def back(cls, data: str):
        kb = cls()

        kb.button(
            text=text('back:button'),
            callback_data=data
        )

        return kb.as_markup()

    @classmethod
    def accept(cls, data: str):
        kb = cls()

        kb.button(
            text=text("delete:button"),
            callback_data=data + "|yes"
        )
        kb.button(
            text=text("back:button"),
            callback_data=data
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def wait_payment(cls, data: str, pay_url: str):
        kb = cls()

        kb.button(
            text=text('go_to_payment'),
            url=pay_url
        )
        kb.button(
            text=text('back:button'),
            callback_data=f'{data}'
        )

        kb.adjust(1)
        return kb.as_markup()
