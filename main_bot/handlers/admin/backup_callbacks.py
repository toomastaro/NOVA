"""
Административные callback хэндлеры для управления бэкап системой через кнопки
"""
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from config import Config
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.backup_scheduler import BackupScheduler
from main_bot.utils.backup_manager import BackupManager
from main_bot.utils.retention_filter import RetentionFilter
from main_bot.database.post.crud import PostCrud
from main_bot.database.published_post.crud import PublishedPostCrud

logger = logging.getLogger(__name__)


async def backup_choice(call: CallbackQuery):
    """Обработчик выбора команд в бэкап меню"""
    if call.from_user.id not in Config.ADMINS:
        await call.answer("Недостаточно прав доступа")
        return

    temp = call.data.split("|")
    
    if temp[1] == "backup_status":
        await show_backup_status(call)
    elif temp[1] == "backup_info":
        await show_backup_info(call)
    elif temp[1] == "cleanup_backups":
        await cleanup_backups(call)
    elif temp[1] == "test_backup":
        await test_backup(call)
    elif temp[1] == "retention_warning":
        await show_retention_warning(call)
    elif temp[1] == "back":
        await call.message.edit_text("Админ меню", reply_markup=keyboards.admin())
    
    await call.answer()


async def show_backup_status(call: CallbackQuery):
    """Показывает статистику бэкап системы"""
    try:
        bot = call.bot
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
        
        await call.message.edit_text(status_text, parse_mode="HTML", reply_markup=keyboards.back("AdminBackup|back"))
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса бэкап системы: {e}")
        await call.message.edit_text("❌ Ошибка при получении статуса системы", reply_markup=keyboards.back("AdminBackup|back"))


async def show_backup_info(call: CallbackQuery):
    """Показывает информацию о системе бэкапов"""
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
    
    await call.message.edit_text(info_text, parse_mode="HTML", reply_markup=keyboards.back("AdminBackup|back"))


async def cleanup_backups(call: CallbackQuery):
    """Принудительная очистка старых бэкапов"""
    try:
        bot = call.bot
        backup_scheduler = BackupScheduler(bot)
        
        # Обновляем сообщение с информацией о начале очистки
        await call.message.edit_text("🧹 Начинается очистка старых бэкапов...", reply_markup=keyboards.back("AdminBackup|back"))
        
        cleaned_count = await backup_scheduler.force_cleanup()
        
        # Финальное сообщение с результатом
        result_text = (
            f"✅ Очистка завершена!\n"
            f"Удалено записей: {cleaned_count}"
        )
        
        await call.message.edit_text(result_text, parse_mode="HTML", reply_markup=keyboards.back("AdminBackup|back"))
        
    except Exception as e:
        logger.error(f"Ошибка принудительной очистки: {e}")
        await call.message.edit_text("❌ Ошибка при очистке бэкапов", reply_markup=keyboards.back("AdminBackup|back"))


async def test_backup(call: CallbackQuery):
    """Тестирует создание бэкап поста"""
    try:
        bot = call.bot
        backup_manager = BackupManager(bot)
        
        # Создаем тестовый пост
        test_message_options = {
            'text': f'🧪 Тестовое сообщение бэкап системы\n\nВремя: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'parse_mode': 'HTML'
        }
        
        await call.message.edit_text("🧪 Создается тестовый бэкап...", reply_markup=keyboards.back("AdminBackup|back"))
        
        # Отправляем в бэкап канал
        backup_message = await backup_manager._send_backup_message(test_message_options)
        
        if backup_message:
            url = f"https://t.me/c/{str(backup_manager.backup_chat_id).replace('-100', '')}/{backup_message.message_id}"
            
            result_text = (
                f"✅ Тестовый бэкап создан успешно!\n\n"
                f"📍 Message ID: {backup_message.message_id}\n"
                f"🔗 URL: {url}"
            )
        else:
            result_text = "❌ Не удалось создать тестовый бэкап"
        
        await call.message.edit_text(result_text, parse_mode="HTML", reply_markup=keyboards.back("AdminBackup|back"))
            
    except Exception as e:
        logger.error(f"Ошибка тестирования бэкапа: {e}")
        await call.message.edit_text(f"❌ Ошибка тестирования: {str(e)}", reply_markup=keyboards.back("AdminBackup|back"))


async def show_retention_warning(call: CallbackQuery):
    """Показывает предупреждение о политике хранения"""
    warning = RetentionFilter.format_retention_warning()
    await call.message.edit_text(warning, parse_mode="HTML", reply_markup=keyboards.back("AdminBackup|back"))


def hand_add():
    """Регистрирует callback хэндлеры для админских бэкап команд"""
    router = Router()
    router.callback_query.register(backup_choice, F.data.split("|")[0] == "AdminBackup")
    return router