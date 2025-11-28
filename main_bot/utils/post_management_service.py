"""
Сервис для управления постами с учетом статусов
"""
import logging
import time
from typing import List, Dict, Any, Optional

from aiogram import Bot

from main_bot.utils.posting_service import PostingService
from main_bot.utils.retention_filter import RetentionFilter
from main_bot.database.post.crud import PostCrud
from main_bot.database.post.model import Post
from main_bot.database.types.post_status import PostStatus, PostStatusRu

logger = logging.getLogger(__name__)


class PostManagementService:
    """Сервис для управления постами с учетом статусов и ограничений"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.posting_service = PostingService(bot)

    async def get_posts_for_calendar(self, admin_id: int, target_date=None) -> List[Dict]:
        """
        Получает посты для календаря с информацией о статусах
        
        Args:
            admin_id: ID администратора
            target_date: Дата для фильтрации (datetime объект)
            
        Returns:
            Список постов с дополнительной информацией о статусе
        """
        post_crud = PostCrud()
        posts = await post_crud.get_posts_for_calendar(admin_id, target_date)
            
        result = []
        for post in posts:
            # Проверяем доступность поста
            is_accessible = RetentionFilter.is_within_retention(post.created_timestamp)
            
            post_info = {
                'id': post.id,
                'status': post.status,
                'status_display': PostStatusRu.get_full_name(post.status),
                'message_options': post.message_options,
                'send_time': post.send_time,
                'posted_timestamp': post.posted_timestamp,
                'created_timestamp': post.created_timestamp,
                'chat_ids': post.chat_ids,
                'admin_id': post.admin_id,
                'backup_available': bool(post.backup_message_id),
                'is_accessible': is_accessible,
                'can_edit': self._can_edit_post(post),
                'can_delete': self._can_delete_post(post)
            }
            result.append(post_info)
            
        return result

    def _can_edit_post(self, post: Post) -> bool:
        """Проверяет, можно ли редактировать пост"""
        # Недоступные посты нельзя редактировать
        if not RetentionFilter.is_within_retention(post.created_timestamp):
            return False
            
        # Можно редактировать ожидающие отправки и отправленные (если есть бэкап)
        return post.status in [PostStatus.PENDING, PostStatus.POSTPONED] or \
               (post.status == PostStatus.POSTED and post.backup_message_id)

    def _can_delete_post(self, post: Post) -> bool:
        """Проверяет, можно ли удалить пост"""
        # Недоступные посты нельзя удалять
        if not RetentionFilter.is_within_retention(post.created_timestamp):
            return False
            
        # Можно удалять неотправленные и отправленные (отметка как удаленный)
        return post.status != PostStatus.DELETED

    async def edit_post(self, post_id: int, new_message_options: Dict[str, Any], admin_id: int) -> Dict[str, Any]:
        """
        Редактирует пост с учетом его статуса
        
        Args:
            post_id: ID поста
            new_message_options: Новые опции сообщения
            admin_id: ID администратора
            
        Returns:
            Результат операции
        """
        result = {
            'success': False,
            'message': '',
            'updated_channels': 0,
            'errors': []
        }
        
        try:
            post_crud = PostCrud()
            post = await post_crud.get_by_id(post_id)
            
            if not post:
                result['message'] = 'Пост не найден'
                return result
            
            if post.admin_id != admin_id:
                result['message'] = 'Нет прав на редактирование этого поста'
                return result
            
            if not self._can_edit_post(post):
                result['message'] = 'Пост недоступен для редактирования'
                return result
            
            # Обновляем сам пост в БД
            await post_crud.update(post_id, message_options=new_message_options)
            
            if post.status == PostStatus.POSTED:
                # Если пост уже отправлен, редактируем через бэкап систему
                edit_result = await self.posting_service.edit_post_batch(
                    post_id, new_message_options
                )
                
                result['success'] = edit_result['backup_updated']
                result['updated_channels'] = edit_result['channels_updated']
                result['errors'] = edit_result['errors']
                
                if edit_result['backup_updated']:
                    result['message'] = f'Пост обновлен в {edit_result["channels_updated"]} каналах'
                else:
                    result['message'] = 'Ошибка обновления поста'
                    
            else:
                # Если пост еще не отправлен, просто обновляем в БД
                result['success'] = True
                result['message'] = 'Пост обновлен (будет применено при отправке)'
                
        except Exception as e:
            logger.error(f"Ошибка редактирования поста {post_id}: {e}")
            result['message'] = f'Ошибка: {str(e)}'
            
        return result

    async def delete_post(self, post_id: int, admin_id: int, delete_from_backup: bool = True) -> Dict[str, Any]:
        """
        Удаляет пост или помечает как удаленный
        
        Args:
            post_id: ID поста
            admin_id: ID администратора
            delete_from_backup: Удалять ли из бэкап канала (True для ручного удаления, False для автоматического)

        Returns:
            Результат операции
        """
        result = {
            'success': False,
            'message': '',
            'deleted_from_channels': 0,
            'deleted_from_backup': False
        }
        
        try:
            post_crud = PostCrud()
            post = await post_crud.get_by_id(post_id)
            
            if not post:
                result['message'] = 'Пост не найден'
                return result
            
            if post.admin_id != admin_id:
                result['message'] = 'Нет прав на удаление этого поста'
                return result
            
            if not self._can_delete_post(post):
                result['message'] = 'Пост недоступен для удаления'
                return result
            
            if post.status == PostStatus.PENDING or post.status == PostStatus.POSTPONED:
                # Неотправленные посты можно удалить полностью
                await post_crud.delete_post(post_id)
                result['success'] = True
                result['message'] = 'Пост удален'

            elif post.status == PostStatus.POSTED:
                # Отправленные посты удаляем из каналов и опционально из бэкапа
                deleted_count = await self._delete_from_channels(post_id)
                result['deleted_from_channels'] = deleted_count

                # ВАЖНО: По требованию, пост НИКОГДА не удаляется из бэкап канала
                # даже при ручном удалении. Он должен оставаться в календаре.
                
                # Помечаем пост как удаленный
                await post_crud.update_post_status(post_id, PostStatus.DELETED)
                result['success'] = True

                result['message'] = f'Пост удален из каналов, но сохранен в календаре (каналов: {deleted_count})'

        except Exception as e:
            logger.error(f"Ошибка удаления поста {post_id}: {e}")
            result['message'] = f'Ошибка: {str(e)}'
            
        return result

    async def postpone_post(self, post_id: int, new_send_time: int, admin_id: int) -> Dict[str, Any]:
        """
        Откладывает отправку поста
        
        Args:
            post_id: ID поста
            new_send_time: Новое время отправки
            admin_id: ID администратора
            
        Returns:
            Результат операции
        """
        result = {
            'success': False,
            'message': ''
        }
        
        try:
            post_crud = PostCrud()
            post = await post_crud.get_by_id(post_id)
            
            if not post:
                result['message'] = 'Пост не найден'
                return result
            
            if post.admin_id != admin_id:
                result['message'] = 'Нет прав на изменение этого поста'
                return result
            
            if post.status != PostStatus.PENDING:
                result['message'] = 'Можно откладывать только ожидающие отправки посты'
                return result
            
            # Обновляем время отправки и статус
            await post_crud.update(post_id, send_time=new_send_time)
            await post_crud.update_post_status(post_id, PostStatus.POSTPONED)
            
            result['success'] = True
            result['message'] = 'Пост отложен'
            
        except Exception as e:
            logger.error(f"Ошибка откладывания поста {post_id}: {e}")
            result['message'] = f'Ошибка: {str(e)}'
            
        return result

    async def get_post_preview_url(self, post_id: int) -> Optional[str]:
        """
        Получает URL для предпросмотра поста
        
        Args:
            post_id: ID поста
            
        Returns:
            URL предпросмотра или None
        """
        # Проверяем доступность поста
        post = await RetentionFilter.get_post_if_accessible(post_id)
        if not post:
            return None
            
        return await self.posting_service.get_post_preview_url(post_id)

    async def _delete_from_channels(self, post_id: int) -> int:
        """
        Удаляет пост из всех каналов через published_posts

        Args:
            post_id: ID поста

        Returns:
            Количество каналов, из которых удален пост
        """
        try:
            from main_bot.database.published_post.crud import PublishedPostCrud
            published_crud = PublishedPostCrud()

            # Получаем все публикации этого поста
            published_posts = await published_crud.get_by_post_id(post_id)
            deleted_count = 0

            for pub_post in published_posts:
                try:
                    await self.bot.delete_message(
                        chat_id=pub_post.chat_id,
                        message_id=pub_post.message_id
                    )
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Ошибка удаления сообщения {pub_post.message_id} из канала {pub_post.chat_id}: {e}")

            # Удаляем записи о публикациях
            await published_crud.delete_by_post_id(post_id)

            return deleted_count

        except Exception as e:
            logger.error(f"Ошибка удаления поста {post_id} из каналов: {e}")
            return 0

    async def cleanup_old_posts(self) -> Dict[str, int]:
        """
        Очищает старые посты (старше 90 дней)
        
        Returns:
            Статистика очистки
        """
        cutoff_time = time.time() - (90 * 24 * 60 * 60)
        
        post_crud = PostCrud()
        deleted_count = await post_crud.delete_old_posts(cutoff_time)
            
        return {
            'deleted_posts': deleted_count,
            'cutoff_days': 90
        }