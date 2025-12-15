"""
DEPRECATED: Этот файл сохранен для обратной совместимости.

Логика создания stories теперь находится в модуле flow_create_post.
Используйте: from main_bot.handlers.user.stories.flow_create_post import get_router
"""

# Импортируем из нового модуля для обратной совместимости
from main_bot.handlers.user.stories.flow_create_post import get_router

__all__ = ["get_router"]
