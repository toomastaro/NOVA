"""
Сервис для отправки постов с поддержкой бэкап канала
"""
import logging
from typing import List, Dict, Any, Optional

from aiogram import Bot
from aiogram.types import Message

from main_bot.utils.backup_manager import BackupManager
from main_bot.database.published_post.crud import PublishedPostCrud

logger = logging.getLogger(__name__)


class PostingService:
    """Сервис для управления отправкой постов"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.backup_manager = BackupManager(bot)

    async def send_post_batch(
        self, 
        post_id: int,
        chat_ids: List[int],
        message_options: Dict[str, Any],
        admin_id: int,
        use_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Отправляет пост в несколько каналов с созданием бэкапа
        
        Args:
            post_id: ID поста
            chat_ids: Список ID каналов для отправки
            message_options: Опции сообщения
            admin_id: ID администратора
            use_backup: Использовать ли бэкап канал
            
        Returns:
            Результат отправки с информацией о статусе
        """
        results = {
            'success_count': 0,
            'failed_count': 0,
            'backup_created': False,
            'published_posts': [],
            'errors': []
        }
        
        backup_info = None
        
        try:
            # Сначала создаем бэкап (если нужно)
            if use_backup:
                backup_info = await self.backup_manager.create_backup_post(
                    post_id, message_options
                )
                if backup_info:
                    results['backup_created'] = True
                    logger.info(f"Создан бэкап для поста {post_id}")
                else:
                    logger.warning(f"Не удалось создать бэкап для поста {post_id}")

            # Отправляем в каналы
            published_posts_data = []
            
            for chat_id in chat_ids:
                try:
                    sent_message = None
                    
                    # Выбираем способ отправки
                    if backup_info and use_backup:
                        # Копируем из бэкап канала (быстрее и меньше нагрузка)
                        sent_message = await self.backup_manager.copy_from_backup(
                            post_id, chat_id
                        )
                    else:
                        # Отправляем напрямую
                        sent_message = await self._send_direct_message(
                            chat_id, message_options
                        )
                    
                    if sent_message:
                        # Записываем информацию о публикации
                        published_posts_data.append({
                            'post_id': post_id,
                            'message_id': sent_message.message_id,
                            'chat_id': chat_id,
                            'admin_id': admin_id
                        })
                        
                        results['success_count'] += 1
                        results['published_posts'].append({
                            'chat_id': chat_id,
                            'message_id': sent_message.message_id
                        })
                        
                        logger.info(f"Пост {post_id} отправлен в канал {chat_id}")
                    else:
                        results['failed_count'] += 1
                        results['errors'].append(f"Не удалось отправить в канал {chat_id}")
                        
                except Exception as e:
                    results['failed_count'] += 1
                    error_msg = f"Ошибка отправки в канал {chat_id}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # Сохраняем информацию о публикациях в БД
            if published_posts_data:
                published_crud = PublishedPostCrud()
                await published_crud.add_many_published_post(published_posts_data)
                    
        except Exception as e:
            error_msg = f"Критическая ошибка при отправке поста {post_id}: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
        
        return results

    async def _send_direct_message(
        self, 
        chat_id: int, 
        message_options: Dict[str, Any]
    ) -> Optional[Message]:
        """Отправляет сообщение напрямую"""
        try:
            if 'photo' in message_options:
                return await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=message_options['photo'],
                    caption=message_options.get('caption'),
                    parse_mode=message_options.get('parse_mode')
                )
            elif 'video' in message_options:
                return await self.bot.send_video(
                    chat_id=chat_id,
                    video=message_options['video'],
                    caption=message_options.get('caption'),
                    parse_mode=message_options.get('parse_mode')
                )
            elif 'document' in message_options:
                return await self.bot.send_document(
                    chat_id=chat_id,
                    document=message_options['document'],
                    caption=message_options.get('caption'),
                    parse_mode=message_options.get('parse_mode')
                )
            elif 'animation' in message_options:
                return await self.bot.send_animation(
                    chat_id=chat_id,
                    animation=message_options['animation'],
                    caption=message_options.get('caption'),
                    parse_mode=message_options.get('parse_mode')
                )
            else:
                # Текстовое сообщение
                return await self.bot.send_message(
                    chat_id=chat_id,
                    text=message_options.get('text', ''),
                    parse_mode=message_options.get('parse_mode')
                )
                
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в канал {chat_id}: {e}")
            return None

    async def edit_post_batch(
        self,
        post_id: int,
        new_message_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Редактирует пост во всех каналах через бэкап
        
        Args:
            post_id: ID поста
            new_message_options: Новые опции сообщения
            
        Returns:
            Результат редактирования
        """
        results = {
            'backup_updated': False,
            'channels_updated': 0,
            'errors': []
        }
        
        try:
            # Сначала обновляем бэкап
            backup_updated = await self.backup_manager.update_backup_post(
                post_id, new_message_options
            )
            results['backup_updated'] = backup_updated
            
            if not backup_updated:
                results['errors'].append("Не удалось обновить бэкап поста")
                return results
            
            # Затем обновляем во всех каналах
            published_crud = PublishedPostCrud()
            published_posts = await published_crud.get_by_post_id(post_id)

            for pub_post in published_posts:
                try:
                    # Обновляем сообщение в канале
                    if 'text' in new_message_options:
                        await self.bot.edit_message_text(
                            chat_id=pub_post.chat_id,
                            message_id=pub_post.message_id,
                            text=new_message_options['text'],
                            parse_mode=new_message_options.get('parse_mode')
                        )
                    elif 'caption' in new_message_options:
                        await self.bot.edit_message_caption(
                            chat_id=pub_post.chat_id,
                            message_id=pub_post.message_id,
                            caption=new_message_options['caption'],
                            parse_mode=new_message_options.get('parse_mode')
                        )

                    results['channels_updated'] += 1

                except Exception as e:
                    error_msg = f"Ошибка обновления в канале {pub_post.chat_id}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)

        except Exception as e:
            error_msg = f"Ошибка редактирования поста {post_id}: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
        
        return results

    async def get_post_preview_url(self, post_id: int) -> Optional[str]:
        """
        Получает URL для предпросмотра поста из бэкап канала
        
        Args:
            post_id: ID поста
            
        Returns:
            URL для предпросмотра или None
        """
        # Проверяем, что пост в пределах 90 дней
        if not await self.backup_manager.is_post_within_retention(post_id):
            return None
            
        return await self.backup_manager.get_backup_message_url(post_id)