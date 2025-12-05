"""
Модуль планировщика задач для Telegram-бота.

Реэкспорт всех функций планировщика для удобного импорта.

Структура модулей:
- posts.py: отправка, удаление, открепление постов, CPM отчеты
- stories.py: отправка сторис
- bots.py: рассылки через ботов, удаление сообщений
- cleanup.py: проверка подписок, самопроверка MT клиентов
- extra.py: обновление курсов валют и прочие вспомогательные задачи
"""

# Импорты из модулей
from .posts import (
    send_posts,
    unpin_posts,
    delete_posts,
    check_cpm_reports,
)

from .stories import (
    send_stories,
)

from .bots import (
    send_bot_posts,
    start_delete_bot_posts,
)

from .cleanup import (
    check_subscriptions,
    mt_clients_self_check,
)

from .extra import (
    update_exchange_rates_in_db,
)


# Экспорт всех функций
__all__ = [
    # Посты
    "send_posts",
    "unpin_posts",
    "delete_posts",
    "check_cpm_reports",
    
    # Сторис
    "send_stories",
    
    # Боты
    "send_bot_posts",
    "start_delete_bot_posts",
    
    # Очистка и обслуживание
    "check_subscriptions",
    "mt_clients_self_check",
    
    # Вспомогательные
    "update_exchange_rates_in_db",
]
