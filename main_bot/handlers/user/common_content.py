from typing import Dict, Any, Optional


def serialize_channel(channel: Any) -> Optional[Dict[str, Any]]:
    """
    Сериализует объект канала в словарь.

    Аргументы:
        channel: Объект канала.

    Возвращает:
        dict: Данные канала или None.
    """
    if not channel:
        return None
    return {
        "id": channel.id,
        "chat_id": channel.chat_id,
        "title": channel.title,
        "username": getattr(channel, "username", None),
        "emoji_id": getattr(channel, "emoji_id", "📺"),
        "subscribers_count": getattr(channel, "subscribers_count", 0),
        "posting": getattr(channel, "posting", False),
    }
