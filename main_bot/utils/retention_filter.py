"""
Фильтр для ограничения доступа к данным старше 90 дней
"""
import time
from typing import List, Optional

from main_bot.database.post.crud import PostCrud
from main_bot.database.post.model import Post


class RetentionFilter:
    """Фильтр для работы с политикой хранения данных"""
    
    RETENTION_DAYS = 90
    
    @classmethod
    def get_cutoff_timestamp(cls) -> float:
        """Получает временную метку, старше которой данные не должны быть доступны"""
        return time.time() - (cls.RETENTION_DAYS * 24 * 60 * 60)
    
    @classmethod
    def is_within_retention(cls, timestamp: float) -> bool:
        """Проверяет, находится ли временная метка в пределах периода хранения"""
        return timestamp > cls.get_cutoff_timestamp()
    
    @classmethod
    async def filter_posts_by_retention(cls, posts: List[Post]) -> List[Post]:
        """Фильтрует посты по периоду хранения"""
        cutoff_time = cls.get_cutoff_timestamp()
        return [post for post in posts if post.created_timestamp > cutoff_time]
    
    @classmethod
    async def get_recent_posts_for_admin(cls, admin_id: int) -> List[Post]:
        """Получает посты администратора за последние 90 дней"""
        cutoff_time = cls.get_cutoff_timestamp()
        
        async with PostCrud() as post_crud:
            # Получаем все посты админа
            posts = await post_crud.fetch(
                post_crud.select(Post).where(
                    Post.admin_id == admin_id,
                    Post.created_timestamp > cutoff_time
                ).order_by(Post.created_timestamp.desc())
            )
            return posts
    
    @classmethod
    async def get_post_if_accessible(cls, post_id: int) -> Optional[Post]:
        """
        Получает пост только если он доступен (в пределах 90 дней)
        
        Args:
            post_id: ID поста
            
        Returns:
            Post если доступен, None если старше 90 дней или не существует
        """
        async with PostCrud() as post_crud:
            post = await post_crud.get_by_id(post_id)
            
            if not post:
                return None
            
            if not cls.is_within_retention(post.created_timestamp):
                return None
                
            return post
    
    @classmethod
    def format_retention_warning(cls) -> str:
        """Возвращает предупреждение о политике хранения"""
        return (
            f"⚠️ <b>Внимание:</b> История и календарь постов доступны "
            f"только за последние {cls.RETENTION_DAYS} дней.\n"
            f"Посты старше этого периода автоматически удаляются из системы."
        )