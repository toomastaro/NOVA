"""
Административные команды для управления бэкап системой
"""
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command

from main_bot.utils.backup_scheduler import BackupScheduler
from main_bot.utils.backup_manager import BackupManager
from main_bot.utils.retention_filter import RetentionFilter
from main_bot.database.post.crud import PostCrud
from main_bot.database.published_post.crud import PublishedPostCrud

logger = logging.getLogger(__name__)
router = Router(name="backup_management")


@router.message(Command("backup_status"))
async def backup_status_command(message: Message, bot: Bot):
    """Показывает статус бэкап системы"""
    try:
        backup_manager = BackupManager(bot)
        
        # Получаем статистику
        cutoff_time = RetentionFilter.get_cutoff_timestamp()
        
        post_crud = PostCrud()
        # Общее количество постов
        total_posts_result = await post_crud.execute(
            "SELECT COUNT(*) FROM posts WHERE created_timestamp > %s",
            (cutoff_time,)
        )
        total_posts = total_posts_result.scalar() if total_posts_result else 0
        
        # Посты с бэкапами
        backup_posts_result = await post_crud.execute(
            "SELECT COUNT(*) FROM posts WHERE backup_message_id IS NOT NULL AND created_timestamp > %s",
            (cutoff_time,)
        )
        backup_posts = backup_posts_result.scalar() if backup_posts_result else 0
    
        pub_crud = PublishedPostCrud()
        # Общее количество публикаций
        total_publications_result = await pub_crud.execute(
            "SELECT COUNT(*) FROM published_posts WHERE created_timestamp > %s",
            (cutoff_time,)
        )
        total_publications = total_publications_result.scalar() if total_publications_result else 0
        
        status_text = (
            f"📊 <b>Статус бэкап системы</b>\n\n"
            f"📅 Период хранения: {RetentionFilter.RETENTION_DAYS} дней\n"
            f"📝 Всего постов за период: {total_posts}\n"
            f"💾 Постов с бэкапом: {backup_posts}\n"
            f"📤 Всего публикаций: {total_publications}\n\n"
            f"🕒 Последняя проверка: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await message.reply(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса бэкап системы: {e}")
        await message.reply("❌ Ошибка при получении статуса системы")


@router.message(Command("cleanup_backups"))
async def force_cleanup_command(message: Message, bot: Bot):
    """Принудительная очистка старых бэкапов"""
    try:
        backup_scheduler = BackupScheduler(bot)
        
        await message.reply("🧹 Начинается очистка старых бэкапов...")
        
        cleaned_count = await backup_scheduler.force_cleanup()
        
        await message.reply(
            f"✅ Очистка завершена!\n"
            f"Удалено записей: {cleaned_count}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка принудительной очистки: {e}")
        await message.reply("❌ Ошибка при очистке бэкапов")


@router.message(Command("backup_info"))
async def backup_info_command(message: Message):
    """Информация о системе бэкапов"""
    info_text = (
        f"ℹ️ <b>Информация о системе бэкапов</b>\n\n"
        f"📋 <b>Как это работает:</b>\n"
        f"• При отправке поста создается копия в служебном канале\n"
        f"• Посты в каналы копируются из бэкапа (быстрее и экономнее)\n"
        f"• Бэкап используется как источник для предпросмотра\n"
        f"• При редактировании сначала меняется бэкап, затем все копии\n\n"
        f"🗓 <b>Ограничения:</b>\n"
        f"• Данные хранятся только {RetentionFilter.RETENTION_DAYS} дней\n"
        f"• Старые посты автоматически удаляются\n"
        f"• Очистка происходит ежедневно в 3:00\n\n"
        f"⚡️ <b>Преимущества:</b>\n"
        f"• Быстрая отправка через copyMessage\n"
        f"• Меньше нагрузки на Telegram API\n"
        f"• Единый источник правды для предпросмотра\n"
        f"• Централизованное редактирование"
    )
    
    await message.reply(info_text, parse_mode="HTML")


@router.message(Command("test_backup"))
async def test_backup_command(message: Message, bot: Bot):
    """Тестирует создание бэкап поста"""
    try:
        backup_manager = BackupManager(bot)
        
        # Создаем тестовый пост
        test_message_options = {
            'text': f'🧪 Тестовое сообщение бэкап системы\n\nВремя: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'parse_mode': 'HTML'
        }
        
        await message.reply("🧪 Создается тестовый бэкап...")
        
        # Отправляем в бэкап канал
        backup_message = await backup_manager._send_backup_message(test_message_options)
        
        if backup_message:
            url = f"https://t.me/c/{str(backup_manager.backup_chat_id).replace('-100', '')}/{backup_message.message_id}"
            
            await message.reply(
                f"✅ Тестовый бэкап создан успешно!\n\n"
                f"📍 Message ID: {backup_message.message_id}\n"
                f"🔗 URL: {url}",
                parse_mode="HTML"
            )
        else:
            await message.reply("❌ Не удалось создать тестовый бэкап")
            
    except Exception as e:
        logger.error(f"Ошибка тестирования бэкапа: {e}")
        await message.reply(f"❌ Ошибка тестирования: {str(e)}")


@router.message(Command("retention_warning"))
async def retention_warning_command(message: Message):
    """Показывает предупреждение о политике хранения"""
    warning = RetentionFilter.format_retention_warning()
    await message.reply(warning, parse_mode="HTML")