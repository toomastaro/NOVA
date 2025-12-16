
from main_bot.database import db

# Redis Key Prefix
VIEW_MODE_KEY = "view_mode:{}"


async def get_user_view_mode(user_id: int) -> str:
    """
    Получает текущий режим просмотра каналов пользователя.
    Returns: 'folders' (default) or 'channels'
    """
    redis = db.redis  # Используем существующий Redis клиент из db
    if not redis:
        return "folders"
        
    mode = await redis.get(VIEW_MODE_KEY.format(user_id))
    return mode.decode() if mode else "folders"


async def set_user_view_mode(user_id: int, mode: str):
    """
    Устанавливает режим просмотра каналов пользователя.
    Args:
        mode: 'folders' or 'channels'
    """
    redis = db.redis
    if redis:
        await redis.set(VIEW_MODE_KEY.format(user_id), mode)
