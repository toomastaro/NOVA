"""
Клавиатуры для рекламных креативов и закупов.
"""
from aiogram.utils.keyboard import InlineKeyboardBuilder


class InlineAdCreative(InlineKeyboardBuilder):
    """Клавиатуры для рекламных креативов"""
    
    @classmethod
    def create_creative_cancel(cls):
        kb = cls()
        kb.button(text="Отмена", callback_data="AdCreative|cancel_creation")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def menu(cls):
        kb = cls()
        kb.button(text="Создать креатив", callback_data="AdCreative|create")
        kb.button(text="Список креативов", callback_data="AdCreative|list")
        kb.button(text="Назад", callback_data="AdCreative|back")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def creative_list(cls, creatives: list, page: int = 0):
        kb = cls()
        from datetime import datetime
        
        for creative in creatives:
            # Format: 🎨 DD.MM.YYYY Name (N ссылок)
            # Assuming creative has created_timestamp, defaulting to now if missing (shouldn't be)
            ts = getattr(creative, 'created_timestamp', 0)
            date_str = datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
            
            slots_count = len(creative.slots) if hasattr(creative, 'slots') else 0
            
            kb.button(
                text=f"🎨 {date_str} {creative.name} ({slots_count} ссылок)",
                callback_data=f"AdCreative|view|{creative.id}"
            )
        kb.button(text="Назад", callback_data="AdBuyMenu|menu")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def creative_view(cls, creative_id: int):
        kb = cls()
        kb.button(text="Создать закуп", callback_data=f"AdPurchase|create|{creative_id}")
        kb.button(text="🗑 Удалить", callback_data=f"AdCreative|delete|{creative_id}")
        kb.button(text="Назад", callback_data="AdCreative|list")
        kb.adjust(1)
        return kb.as_markup()


class InlineAdPurchase(InlineKeyboardBuilder):
    """Клавиатуры для рекламных закупов"""
    
    @classmethod
    def menu(cls):
        return cls.main_menu()

    @classmethod
    def main_menu(cls):
        from config import Config
        kb = cls()
        kb.button(text="Создать закуп", callback_data="AdPurchase|create_menu")
        kb.button(text="Мои закупы", callback_data="AdPurchase|list")
        kb.button(text="🌍 Моя статистика", callback_data="AdPurchase|global_stats")
        kb.button(text="Назад", callback_data="AdBuyMenu|menu")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def creative_selection_menu(cls, creatives: list):
        kb = cls()
        for c in creatives:
            kb.button(text=f"Выбрать {c.name}", callback_data=f"AdPurchase|create|{c.id}")
        kb.button(text="Назад", callback_data="AdPurchase|menu")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def pricing_type_menu(cls):
        kb = cls()
        kb.button(text="По заявке (CPL)", callback_data="AdPurchase|pricing|CPL")
        kb.button(text="По подписке (CPS)", callback_data="AdPurchase|pricing|CPS")
        kb.button(text="Фикс (FIXED)", callback_data="AdPurchase|pricing|FIXED")
        kb.button(text="Назад", callback_data="AdPurchase|cancel")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def mapping_menu(cls, purchase_id: int, links_data: list):
        kb = cls()
        # links_data is list of dict: {slot_id, original_url, status_text, is_channel}
        for link in links_data:
            # Left button: URL (inactive/noop)
            kb.button(
                text=f"{link['original_url']}", 
                callback_data="noop"
            )
            # Right button: Status/Channel (clickable)
            kb.button(
                text=f"{link['status_text']}",
                callback_data=f"AdPurchase|map_link|{purchase_id}|{link['slot_id']}"
            )
        
        kb.button(text="⬅️ Назад", callback_data=f"AdPurchase|view|{purchase_id}")
        kb.button(text="✅ Сохранить мапинг", callback_data=f"AdPurchase|save_mapping|{purchase_id}")
        
        # Adjust: 2 columns for links, 2 columns for bottom buttons
        sizes = [2] * len(links_data) + [2]
        kb.adjust(*sizes)
        return kb.as_markup()

    @classmethod
    def link_actions_menu(cls, purchase_id: int, slot_id: int):
        kb = cls()
        kb.button(
            text="Выбрать канал",
            callback_data=f"AdPurchase|select_channel_list|{purchase_id}|{slot_id}"
        )
        kb.button(
            text="❌ Не трекать",
            callback_data=f"AdPurchase|set_external|{purchase_id}|{slot_id}"
        )
        kb.button(
            text="Назад",
            callback_data=f"AdPurchase|mapping|{purchase_id}"
        )
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def channel_list_menu(cls, purchase_id: int, slot_id: int, channels: list):
        kb = cls()
        for ch in channels:
            kb.button(
                text=ch.title,
                callback_data=f"AdPurchase|set_channel|{purchase_id}|{slot_id}|{ch.chat_id}"
            )
        
        kb.button(
            text="Назад",
            callback_data=f"AdPurchase|map_link|{purchase_id}|{slot_id}"
        )
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def purchase_list_menu(cls, purchases: list):
        kb = cls()
        from datetime import datetime
        
        # Mapping for pricing types
        type_ru = {
            "CPL": "Заявка",
            "CPS": "Подписка",
            "FIXED": "Фикс"
        }
        
        for p in purchases:
            # p is AdPurchase object, needs creative_name attached or fetched
            name = getattr(p, 'creative_name', f"Creative #{p.creative_id}")
            # Format: 🛒 DD.MM.YYYY Name (Type)
            date_str = datetime.fromtimestamp(p.created_timestamp).strftime("%d.%m.%Y")
            
            p_type = p.pricing_type.value if hasattr(p.pricing_type, 'value') else str(p.pricing_type)
            ru_type = type_ru.get(p_type, p_type)
            
            text_str = f"🛒 {date_str} {name} ({ru_type})"
            
            kb.button(text=text_str, callback_data=f"AdPurchase|view|{p.id}")
        
        kb.button(text="Назад", callback_data="AdBuyMenu|menu")
        # 1 column per row
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def purchase_view_menu(cls, purchase_id: int):
        kb = cls()
        kb.button(text="Мапинг ссылок", callback_data=f"AdPurchase|mapping|{purchase_id}")
        kb.button(text="📤 Сгенерировать пост", callback_data=f"AdPurchase|gen_post|{purchase_id}")
        kb.button(text="📊 Статистика", callback_data=f"AdPurchase|stats|{purchase_id}")
        kb.button(text="Архивировать", callback_data=f"AdPurchase|archive|{purchase_id}")
        kb.button(text="Удалить", callback_data=f"AdPurchase|delete|{purchase_id}")
        kb.button(text="Назад", callback_data="AdPurchase|list")
        kb.adjust(1)
        return kb.as_markup()
    
    @classmethod
    def stats_period_menu(cls, purchase_id: int):
        kb = cls()
        kb.button(text="📅 24 часа", callback_data=f"AdPurchase|stats_period|{purchase_id}|24h")
        kb.button(text="📅 7 дней", callback_data=f"AdPurchase|stats_period|{purchase_id}|7d")
        kb.button(text="📅 30 дней", callback_data=f"AdPurchase|stats_period|{purchase_id}|30d")
        kb.button(text="📅 Всё время", callback_data=f"AdPurchase|stats_period|{purchase_id}|all")
        kb.button(text="Назад", callback_data=f"AdPurchase|view|{purchase_id}")
        kb.adjust(1)
        return kb.as_markup()
    
    @classmethod
    def global_stats_period_menu(cls):
        kb = cls()
        kb.button(text="📅 24 часа", callback_data="AdPurchase|global_stats_period|24h")
        kb.button(text="📅 7 дней", callback_data="AdPurchase|global_stats_period|7d")
        kb.button(text="📅 30 дней", callback_data="AdPurchase|global_stats_period|30d")
        kb.button(text="📅 Всё время", callback_data="AdPurchase|global_stats_period|all")
        kb.button(text="Назад", callback_data="AdPurchase|menu")
        kb.adjust(1)
        return kb.as_markup()
