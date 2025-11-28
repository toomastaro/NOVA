"""
Backup Manager - Управление бэкап каналом для постов
"""
import time
import logging
from typing import Optional, Dict, Any

from aiogram import Bot
from aiogram.types import Message

from config import settings
from main_bot.database.post.crud import PostCrud
from main_bot.database.published_post.crud import PublishedPostCrud

logger = logging.getLogger(__name__)


class BackupManager:
    """Менеджер для работы с бэкап каналом"""

    BACKUP_RETENTION_DAYS = 90

    def __init__(self, bot: Bot):
        self.bot = bot
        self.backup_chat_id = settings.NOVA_BKP

    async def create_backup_post(self, post_id: int, message_options: Dict[str, Any]) -> Optional[tuple[int, int]]:
        """
        Создает бэкап пост в служебном канале
        
        Args:
            post_id: ID поста
            message_options: Опции сообщения (текст, медиа и т.д.)
            
        Returns:
                    caption=message_options.get('caption'),
                    parse_mode=message_options.get('parse_mode')
                )
            elif 'document' in message_options:
                return await self.bot.send_document(
                    chat_id=self.backup_chat_id,
                    document=message_options['document'],
                    caption=message_options.get('caption'),
                    parse_mode=message_options.get('parse_mode')
                )
            elif 'animation' in message_options:
                return await self.bot.send_animation(
                    chat_id=self.backup_chat_id,
                    animation=message_options['animation'],
                    caption=message_options.get('caption'),
                    parse_mode=message_options.get('parse_mode')
                )
            else:
                # Текстовое сообщение
                return await self.bot.send_message(
                    chat_id=self.backup_chat_id,
                    text=message_options.get('text', ''),
                    parse_mode=message_options.get('parse_mode')
                )
                
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в бэкап канал: {e}")
            return None

    async def copy_from_backup(self, post_id: int, target_chat_id: int) -> Optional[Message]:
        """
        Копирует пост из бэкап канала в целевой канал
        
        Args:
            post_id: ID поста
            target_chat_id: ID целевого канала
            
        Returns:
            Скопированное сообщение или None при ошибке
        """
        try:
            async with PostCrud() as post_crud:
                post = await post_crud.get_by_id(post_id)
                
                if not post or not post.backup_message_id:
                    logger.error(f"Пост {post_id} не имеет бэкапа")
                    return None
                
                # Копируем сообщение из бэкап канала
                copied_message = await self.bot.copy_message(
                    chat_id=target_chat_id,
                    from_chat_id=self.backup_chat_id,
                    message_id=post.backup_message_id
                )
                
                logger.info(f"Скопирован пост из бэкапа: post_id={post_id}, target_chat={target_chat_id}")
                return copied_message
                
        except Exception as e:
            logger.error(f"Ошибка копирования поста из бэкапа: {e}")
            return None

    async def update_backup_post(self, post_id: int, new_message_options: Dict[str, Any]) -> bool:
        """
        Обновляет пост в бэкап канале
        
        Args:
            post_id: ID поста
            new_message_options: Новые опции сообщения
            
        Returns:
            True при успехе, False при ошибке
        """
        try:
            async with PostCrud() as post_crud:
                post = await post_crud.get_by_id(post_id)
                
                if not post or not post.backup_message_id:
                    logger.error(f"Пост {post_id} не имеет бэкапа для обновления")
                    return False
                
                # Обновляем сообщение в бэкап канале
                if 'text' in new_message_options:
                    await self.bot.edit_message_text(
                        chat_id=self.backup_chat_id,
                        message_id=post.backup_message_id,
                        text=new_message_options['text'],
                        parse_mode=new_message_options.get('parse_mode')
                    )
                elif 'caption' in new_message_options:
                    await self.bot.edit_message_caption(
                        chat_id=self.backup_chat_id,
                        message_id=post.backup_message_id,
                        caption=new_message_options['caption'],
                        parse_mode=new_message_options.get('parse_mode')
                    )
                
                logger.info(f"Обновлен бэкап пост для post_id={post_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка обновления бэкап поста: {e}")
            return False

    async def get_backup_message_url(self, post_id: int) -> Optional[str]:
        """
        Получает URL бэкап сообщения для предпросмотра
        
        Args:
            post_id: ID поста
            
        Returns:
            URL сообщения или None
        """
        try:
            async with PostCrud() as post_crud:
                post = await post_crud.get_by_id(post_id)
                
                if not post or not post.backup_message_id:
                    return None
                
                # Формируем URL (для приватных каналов нужен особый подход)
                # Для приватных каналов URL будет работать только для участников канала
                chat_id_str = str(self.backup_chat_id).replace('-100', '')
                return f"https://t.me/c/{chat_id_str}/{post.backup_message_id}"
                
        except Exception as e:
            logger.error(f"Ошибка получения URL бэкап сообщения: {e}")
            return None

    async def cleanup_old_backups(self) -> int:
        """
        Очищает старые бэкапы (старше 90 дней)
        
        Returns:
            Количество очищенных записей
        """
        try:
            cutoff_time = time.time() - (self.BACKUP_RETENTION_DAYS * 24 * 60 * 60)
            cleaned_count = 0
            
            async with PostCrud() as post_crud:
                # Получаем старые посты с бэкапами
                old_posts = await post_crud.get_posts_older_than(cutoff_time)
                
                for post in old_posts:
                    if post.backup_message_id:
                        try:
                            # Удаляем сообщение из бэкап канала
                            await self.bot.delete_message(
                                chat_id=self.backup_chat_id,
                                message_id=post.backup_message_id
                            )
                            
                            # Очищаем ссылки на бэкап
                            await post_crud.update(
                                post.id,
                                backup_chat_id=None,
                                backup_message_id=None
                            )
                            
                            cleaned_count += 1
                            
                        except Exception as e:
                            logger.error(f"Ошибка удаления бэкап сообщения {post.backup_message_id}: {e}")
                            continue
                
                # Также удаляем записи о публикациях старше 90 дней
                async with PublishedPostCrud() as published_crud:
                    await published_crud.delete_older_than(cutoff_time)

                # Удаляем сами посты старше 90 дней
                deleted_posts = await post_crud.delete_old_posts(cutoff_time)

            logger.info(f"Очищено {cleaned_count} старых бэкапов")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")
            return 0

    async def is_post_within_retention(self, post_id: int) -> bool:
        """
        Проверяет, находится ли пост в пределах периода хранения
        
        Args:
            post_id: ID поста
            
        Returns:
            True если пост в пределах 90 дней
        """
        try:
            cutoff_time = time.time() - (self.BACKUP_RETENTION_DAYS * 24 * 60 * 60)
            
            async with PostCrud() as post_crud:
                post = await post_crud.get_by_id(post_id)
                
                if not post:
                    return False
                
                return post.created_timestamp > cutoff_time
                
        except Exception as e:
            logger.error(f"Ошибка проверки периода хранения поста {post_id}: {e}")
            return False