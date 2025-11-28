"""
Статусы постов
"""
import enum


class PostStatus(enum.Enum):
    """Статусы постов"""
    PENDING = "pending"  # Ожидает отправки
    POSTED = "posted"    # Отправлен
    DELETED = "deleted"  # Удален
    POSTPONED = "postponed"  # Отложен
    
    
class PostStatusRu:
    """Русские названия статусов"""
    STATUS_NAMES = {
        PostStatus.PENDING: "Ожидает отправки",
        PostStatus.POSTED: "Отправлен", 
        PostStatus.DELETED: "Удален",
        PostStatus.POSTPONED: "Отложен"
    }
    
    STATUS_EMOJIS = {
        PostStatus.PENDING: "⏳",
        PostStatus.POSTED: "✅", 
        PostStatus.DELETED: "🗑",
        PostStatus.POSTPONED: "⏸"
    }
    
    @classmethod
    def get_name(cls, status: PostStatus) -> str:
        """Получить русское название статуса"""
        return cls.STATUS_NAMES.get(status, "Неизвестно")
    
    @classmethod
    def get_emoji(cls, status: PostStatus) -> str:
        """Получить эмодзи статуса"""
        return cls.STATUS_EMOJIS.get(status, "❓")
    
    @classmethod
    def get_full_name(cls, status: PostStatus) -> str:
        """Получить полное название со смайликом"""
        emoji = cls.get_emoji(status)
        name = cls.get_name(status)
        return f"{emoji} {name}"