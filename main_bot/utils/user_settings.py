from main_bot.utils.redis_client import redis_client

# Префикс ключа Redis
VIEW_MODE_KEY = "view_mode:{}"


async def get_user_view_mode(user_id: int) -> str:
    """
    Получает текущий режим просмотра каналов пользователя.
    Returns: 'folders' (по умолчанию) или 'channels'
    """
    if not redis_client:
        return "folders"

    mode = await redis_client.get(VIEW_MODE_KEY.format(user_id))
    return mode.decode() if mode else "folders"


async def set_user_view_mode(user_id: int, mode: str):
    """
    Устанавливает режим просмотра каналов пользователя.
    Args:
        mode: 'folders' or 'channels'
    """
    if redis_client:
        await redis_client.set(VIEW_MODE_KEY.format(user_id), mode)
