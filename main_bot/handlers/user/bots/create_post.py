"""
DEPRECATED: Этот файл сохранен для обратной совместимости.

Логика создания постов для ботов теперь находится в модуле flow_create_post.
Используйте: from main_bot.handlers.user.bots.flow_create_post import hand_add
"""

# Импортируем из нового модуля для обратной совместимости
from main_bot.handlers.user.bots.flow_create_post import hand_add

__all__ = ['hand_add']
