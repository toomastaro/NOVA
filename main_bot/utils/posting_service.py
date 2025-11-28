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
    def __init__(self, bot: Bot, backup_manager: BackupManager = None):
        self.bot = bot
        self.backup_manager = backup_manager or BackupManager(bot)

    async def send_post_batch(
        self,
        post_id: int,
        chat_ids: List[int],
        message_options: Dict[str, Any],
        admin_id: int,
        use_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Отправляет пост в несколько каналов с поддержкой бэкапа

        Args:
            post_id: ID поста
            chat_ids: Список ID каналов
            message_options: Опции сообщения
            admin_id: ID администратора
            use_backup: Использовать бэкап

        Returns:
            Результат отправки
        """
        results = {
            'success_count': 0,
            'failed_count': 0,
            'errors': [],
            'published_posts': [],
            'backup_created': False
        }

        try:
            # Отправляем в бэкап канал сначала (если нужно)
            backup_message = None
            if use_backup:
                try:
                    backup_message = await self.backup_manager.send_to_backup(
                        post_id, message_options
                    )
                    if backup_message:
                        results['backup_created'] = True
                        logger.info(f"Пост {post_id} сохранён в бэкап")
                except Exception as e:
                    logger.warning(f"Не удалось создать бэкап: {e}")

            # Отправляем в каналы
            published_posts_data = []

            for chat_id in chat_ids:
                try:
                    sent_message = await self._send_direct_message(chat_id, message_options)

                    if sent_message:
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
            # Создаем клавиатуру с кнопками, если они есть
            reply_markup = None
            if 'buttons' in message_options and message_options['buttons']:
                from main_bot.keyboards.keyboards import keyboards
                # Создаем временный объект для использования с post_kb
                class TempPost:
                    def __init__(self, buttons):
                        self.buttons = buttons
                        self.hide = None
                        self.reaction = None

                temp_post = TempPost(message_options['buttons'])
                reply_markup = keyboards.post_kb(temp_post, is_bot=True)

            # Базовые параметры для всех типов сообщений
            send_params = {
                'chat_id': chat_id,
                'parse_mode': message_options.get('parse_mode'),
                'reply_markup': reply_markup
            }

            # Добавляем специфичные параметры в зависимости от типа медиа
            if 'photo' in message_options:
                send_params.update({
                    'photo': message_options['photo'],
                    'caption': message_options.get('caption')
                })
                return await self.bot.send_photo(**send_params)

            elif 'video' in message_options:
                send_params.update({
                    'video': message_options['video'],
                    'caption': message_options.get('caption')
                })
                return await self.bot.send_video(**send_params)

            elif 'document' in message_options:
                send_params.update({
                    'document': message_options['document'],
                    'caption': message_options.get('caption')
                })
                return await self.bot.send_document(**send_params)

            elif 'animation' in message_options:
                send_params.update({
                    'animation': message_options['animation'],
                    'caption': message_options.get('caption')
                })
                return await self.bot.send_animation(**send_params)

            else:
                # Текстовое сообщение
                send_params['text'] = message_options.get('text', '')
                return await self.bot.send_message(**send_params)

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