"""
Клавиатуры для NOVASTAT - статистики каналов.
"""
from typing import List

from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.database.novastat.model import Collection, CollectionChannel


class InlineNovaStat(InlineKeyboardBuilder):
    """Клавиатуры для NOVASTAT"""
    
    @classmethod
    def main_menu(cls):
        kb = cls()
        kb.button(text="Настройки", callback_data="NovaStat|settings")
        kb.button(text="Сохранённые каналы", callback_data="NovaStat|collections")
        kb.button(text="Мои каналы (в разработке)", callback_data="NovaStat|my_channels")
        kb.button(text="Назад", callback_data="NovaStat|exit")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def settings(cls, current_depth: int):
        kb = cls()
        for i in range(3, 8):
            text_btn = f"{i} дня" if i < 5 else f"{i} дней"
            if i == current_depth:
                text_btn += " ✅"
            kb.button(text=text_btn, callback_data=f"NovaStat|set_depth|{i}")
        kb.button(text="Назад", callback_data="NovaStat|main")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def collections_list(cls, collections: List[Collection]):
        kb = cls()
        for col in collections:
            kb.button(text=f"{col.name}", callback_data=f"NovaStat|col_open|{col.id}")
        
        kb.button(text="Создать коллекцию", callback_data="NovaStat|col_create")
        kb.button(text="Назад", callback_data="NovaStat|main")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def collection_view(cls, collection: Collection, channels: List[CollectionChannel]):
        kb = cls()
        kb.button(text="Получить аналитику", callback_data=f"NovaStat|col_analyze|{collection.id}")
        kb.button(text="Добавить канал", callback_data=f"NovaStat|col_add_channel|{collection.id}")
        kb.button(text="Удалить канал", callback_data=f"NovaStat|col_del_channel_list|{collection.id}")
        kb.button(text="Переименовать", callback_data=f"NovaStat|col_rename|{collection.id}")
        kb.button(text="Удалить коллекцию", callback_data=f"NovaStat|col_delete|{collection.id}")
        kb.button(text="Назад", callback_data="NovaStat|collections")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def collection_channels_delete(cls, collection_id: int, channels: List[CollectionChannel]):
        kb = cls()
        for ch in channels:
            kb.button(text=f"❌ {ch.channel_identifier}", callback_data=f"NovaStat|col_del_channel|{collection_id}|{ch.id}")
        kb.button(text="Назад", callback_data=f"NovaStat|col_open|{collection_id}")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def analysis_result(cls):
        kb = cls()
        kb.button(text="Рассчитать цену рекламы", callback_data="NovaStat|calc_cpm_start")
        kb.button(text="Назад", callback_data="NovaStat|main")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def cpm_choice(cls):
        kb = cls()
        for cpm in range(100, 2100, 100):
            kb.button(text=str(cpm), callback_data=f"NovaStat|calc_cpm|{cpm}")
        kb.button(text="Назад", callback_data="NovaStat|main")
        kb.adjust(4)
        return kb.as_markup()

    @classmethod
    def cpm_result(cls):
        kb = cls()
        kb.button(text="Назад", callback_data="NovaStat|calc_cpm_start")
        return kb.as_markup()
