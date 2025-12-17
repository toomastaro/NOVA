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
            s_id = s.get('id') if isinstance(s, dict) else s.id
            s_name = s.get('name') if isinstance(s, dict) else s.name
            s_rate = s.get('rate') if isinstance(s, dict) else s.rate
            
            kb.button(
                text=f"{s_name}: {s_rate:.2f}₽{' ✅' if int(chosen_exchange_rate_id) == int(s_id) else ''}",
                callback_data=f'MenuExchangeRate|settings|choose_exchange_rate|{s_id}'
            )

        kb.button(
            text=text("exchange_rate:start_exchange_rate:settings:back:button"),
            callback_data='MenuExchangeRate|settings|back'
        )

        kb.adjust(*([1]*(len(source_list) + 1)))
        return kb.as_markup()
