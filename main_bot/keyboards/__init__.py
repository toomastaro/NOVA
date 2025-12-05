"""
Модуль клавиатур для Telegram-бота.

Реэкспорт всех клавиатур для удобного импорта.
"""

# Базовые утилиты
from .base import _parse_button

# Общие клавиатуры
from .common import Reply, InlineCommon

# Тематические клавиатуры
from .exchange_rate import InlineExchangeRate
from .posting import InlinePosting
from .stories import InlineStories
from .bots import InlineBots
from .bots_settings import InlineBotSetting
from .profile import InlineProfile
from .admin import InlineAdmin
from .novastat import InlineNovaStat
from .ad_modules import InlineAdCreative, InlineAdPurchase
from .content import InlineContent


# Объединенный класс всех inline-клавиатур
class Inline(
    InlineCommon,
    InlineContent,
    InlineStories,
    InlinePosting,
    InlineBots,
    InlineBotSetting,
    InlineProfile,
    InlineAdmin,
):
    """Объединенный класс всех inline-клавиатур"""
    pass


# Главный класс клавиатур (объединяет Reply и Inline + рекламные модули)
class Keyboards(
    Reply,
    Inline,
    InlineAdCreative,
    InlineAdPurchase
):
    """Главный класс клавиатур, объединяющий все типы клавиатур"""
    pass


# Создаем единственный экземпляр для использования в хендлерах
keyboards = Keyboards()


# Экспортируем все необходимые классы и экземпляр
__all__ = [
    # Базовые утилиты
    '_parse_button',
    
    # Общие клавиатуры
    'Reply',
    'InlineCommon',
    
    # Тематические клавиатуры
    'InlineExchangeRate',
    'InlinePosting',
    'InlineStories',
    'InlineBots',
    'InlineBotSetting',
    'InlineProfile',
    'InlineAdmin',
    'InlineNovaStat',
    'InlineAdCreative',
    'InlineAdPurchase',
    'InlineContent',
    
    # Объединенные классы
    'Inline',
    'Keyboards',
    
    # Экземпляр для использования
    'keyboards',
]
