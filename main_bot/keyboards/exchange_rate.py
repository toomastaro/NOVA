"""
Клавиатуры для работы с курсами валют.
"""
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.utils.lang.language import text


class InlineExchangeRate(InlineKeyboardBuilder):
    """Клавиатуры для настройки курсов валют"""
    
    @classmethod
    def set_exchange_rate(cls):
        kb = cls()

        kb.button(
            text=text('exchange_rate:start_exchange_rate:settings:button'),
            callback_data='MenuExchangeRate|settings'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choose_exchange_rate(cls, source_list, chosen_exchange_rate_id):
        kb = cls()
        for s in source_list:
            kb.button(
                text=f"{s.name}: {s.rate:.2f}₽{' ✅' if int(chosen_exchange_rate_id) == int(s.id) else ''}",
                callback_data=f'MenuExchangeRate|settings|choose_exchange_rate|{s.id}'
            )

        kb.button(
            text=text("exchange_rate:start_exchange_rate:settings:back:button"),
            callback_data=f'MenuExchangeRate|settings|back'
        )

        kb.adjust(*([1]*(len(source_list) + 1)))
        return kb.as_markup()
