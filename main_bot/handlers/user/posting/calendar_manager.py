"""
Обновленный календарь постов с поддержкой статусов
"""
import logging
from datetime import datetime
from typing import Optional

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext

from main_bot.utils.post_management_service import PostManagementService
from main_bot.utils.retention_filter import RetentionFilter
from main_bot.database.types.post_status import PostStatus
from main_bot.keyboards.keyboards import keyboards

logger = logging.getLogger(__name__)
router = Router(name="calendar_manager")


@router.callback_query(F.data.startswith("ContentPost|"))
async def show_post_details(call: types.CallbackQuery, bot: Bot):
    """Показывает детали поста из календаря"""
    try:
        temp = call.data.split("|")
        if len(temp) < 2:
            return
            
        post_id = int(temp[1])
        management_service = PostManagementService(bot)
        
        # Получаем информацию о посте
        posts = await management_service.get_posts_for_calendar(call.from_user.id)
        post_info = next((p for p in posts if p['id'] == post_id), None)
        
        if not post_info:
            await call.answer("❌ Пост не найден или недоступен", show_alert=True)
            return
            
        # Формируем информацию о посте
        message_options = post_info['message_options']
        content = message_options.get('text') or message_options.get('caption') or 'Медиа'
        if len(content) > 100:
            content = content[:100] + '...'
            
        # Форматируем время (с проверкой на None)
        if post_info.get('send_time') and post_info['send_time'] is not None:
            try:
                send_time_str = datetime.fromtimestamp(post_info['send_time']).strftime('%d.%m.%Y %H:%M')
            except (ValueError, TypeError, OSError):
                send_time_str = 'Ошибка даты'
        else:
            send_time_str = 'Сразу'
            
        if post_info.get('posted_timestamp') and post_info['posted_timestamp'] is not None:
            try:
                posted_time_str = datetime.fromtimestamp(post_info['posted_timestamp']).strftime('%d.%m.%Y %H:%M')
            except (ValueError, TypeError, OSError):
                posted_time_str = 'Ошибка даты'
        else:
            posted_time_str = '—'
            
        channels_count = len(post_info['chat_ids'])
        
        post_text = (
            f"📋 <b>Информация о посте #{post_id}</b>\n\n"
            f"📊 Статус: {post_info['status_display']}\n"
            f"📅 Запланировано: {send_time_str}\n"
            f"✅ Отправлено: {posted_time_str}\n"
            f"📺 Каналов: {channels_count}\n\n"
            f"📝 <b>Содержимое:</b>\n{content}"
        )
        
        # Создаем клавиатуру в зависимости от статуса и возможностей
        await call.message.edit_text(
            post_text,
            parse_mode="HTML",
            reply_markup=keyboards.post_details(post_info)
        )
        
    except Exception as e:
        logger.error(f"Ошибка показа деталей поста: {e}")
        await call.answer("❌ Ошибка загрузки деталей поста", show_alert=True)


@router.callback_query(F.data.startswith("edit_post|"))
async def start_edit_post(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Начинает редактирование поста"""
    try:
        temp = call.data.split("|")
        post_id = int(temp[1])
        
        management_service = PostManagementService(bot)
        posts = await management_service.get_posts_for_calendar(call.from_user.id)
        post_info = next((p for p in posts if p['id'] == post_id), None)
        
        if not post_info:
            await call.answer("❌ Пост не найден", show_alert=True)
            return
            
        if not post_info['can_edit']:
            await call.answer("❌ Пост недоступен для редактирования", show_alert=True)
            return
            
        # Сохраняем ID поста для редактирования
        await state.update_data(editing_post_id=post_id)
        
        edit_message = (
            f"✏️ <b>Редактирование поста #{post_id}</b>\n\n"
            f"Статус: {post_info['status_display']}\n\n"
        )
        
        if post_info['status'] == PostStatus.POSTED:
            edit_message += (
                "⚠️ <b>Внимание!</b> Пост уже отправлен.\n"
                "Изменения будут применены во всех каналах через бэкап систему.\n\n"
            )
            
        edit_message += "Отправьте новое содержимое поста:"
        
        await call.message.edit_text(
            edit_message,
            parse_mode="HTML",
            reply_markup=keyboards.cancel_post_edit()
        )
        
        await state.set_state("editing_calendar_post")
        
    except Exception as e:
        logger.error(f"Ошибка начала редактирования поста: {e}")
        await call.answer("❌ Ошибка инициализации редактирования", show_alert=True)


@router.message(F.text | F.photo | F.video | F.animation)
async def process_post_edit_content(message: types.Message, state: FSMContext, bot: Bot):
    """Обрабатывает новое содержимое поста при редактировании"""
    current_state = await state.get_state()
    
    if current_state != "editing_calendar_post":
        return
        
    try:
        data = await state.get_data()
        post_id = data.get('editing_post_id')
        
        if not post_id:
            await message.answer("❌ Ошибка: ID поста не найден")
            await state.clear()
            return
            
        # Подготавливаем новые опции сообщения
        new_message_options = {}
        
        if message.text:
            new_message_options['text'] = message.html_text
        elif message.caption:
            new_message_options['caption'] = message.html_text
            
        # Добавляем медиа если есть
        if message.photo:
            new_message_options['photo'] = message.photo[-1].file_id
        elif message.video:
            new_message_options['video'] = message.video.file_id
        elif message.animation:
            new_message_options['animation'] = message.animation.file_id
            
        new_message_options['parse_mode'] = 'HTML'
        
        # Применяем изменения
        management_service = PostManagementService(bot)
        result = await management_service.edit_post(
            post_id, new_message_options, message.from_user.id
        )
        
        # Формируем отчет
        if result['success']:
            report_text = f"✅ <b>Пост #{post_id} обновлен!</b>\n\n{result['message']}"
            
            if result['updated_channels'] > 0:
                report_text += f"\n📺 Обновлено каналов: {result['updated_channels']}"
                
            if result['errors']:
                report_text += "\n\n⚠️ <b>Предупреждения:</b>\n"
                for error in result['errors'][:3]:
                    report_text += f"• {error}\n"
        else:
            report_text = f"❌ <b>Ошибка обновления поста #{post_id}</b>\n\n{result['message']}"
            
        await message.answer(
            report_text,
            parse_mode="HTML",
            reply_markup=keyboards.post_edit_complete()
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка обработки редактирования поста: {e}")
        await message.answer(
            "❌ Произошла ошибка при обновлении поста",
            reply_markup=keyboards.post_edit_complete()
        )
        await state.clear()


@router.callback_query(F.data.startswith("delete_post|"))
async def confirm_delete_post(call: types.CallbackQuery, bot: Bot):
    """Подтверждение удаления поста"""
    try:
        temp = call.data.split("|")
        post_id = int(temp[1])
        
        management_service = PostManagementService(bot)
        posts = await management_service.get_posts_for_calendar(call.from_user.id)
        post_info = next((p for p in posts if p['id'] == post_id), None)
        
        if not post_info:
            await call.answer("❌ Пост не найден", show_alert=True)
            return
            
        if not post_info['can_delete']:
            await call.answer("❌ Пост недоступен для удаления", show_alert=True)
            return
            
        delete_text = (
            f"❓ <b>Удалить пост #{post_id}?</b>\n\n"
            f"Статус: {post_info['status_display']}\n"
        )
        
        if post_info['status'] == PostStatus.POSTED:
            delete_text += "\n⚠️ Пост уже отправлен. Он будет помечен как удаленный."
        else:
            delete_text += "\n🗑 Пост будет полностью удален."
            
        await call.message.edit_text(
            delete_text,
            parse_mode="HTML",
            reply_markup=keyboards.confirm_delete_post(post_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения удаления поста: {e}")
        await call.answer("❌ Ошибка удаления поста", show_alert=True)


@router.callback_query(F.data.startswith("confirm_delete|"))
async def execute_delete_post(call: types.CallbackQuery, bot: Bot):
    """Выполняет удаление поста"""
    try:
        temp = call.data.split("|")
        post_id = int(temp[1])
        
        management_service = PostManagementService(bot)
        # Удаляем с delete_from_backup=True, так как это ручное удаление
        result = await management_service.delete_post(post_id, call.from_user.id, delete_from_backup=True)

        if result['success']:
            # Формируем детальное сообщение
            message_text = f"✅ {result['message']}"
            if result.get('deleted_from_backup'):
                message_text += "\n🗑️ Пост полностью удален из всех мест"
            elif result.get('deleted_from_channels', 0) > 0:
                message_text += "\n📅 Пост оставлен в календаре для истории"

            await call.message.edit_text(
                message_text,
                reply_markup=keyboards.back_to_calendar()
            )
        else:
            await call.message.edit_text(
                f"❌ {result['message']}",
                reply_markup=keyboards.back_to_calendar()
            )
            
    except Exception as e:
        logger.error(f"Ошибка выполнения удаления поста: {e}")
        await call.answer("❌ Ошибка при удалении поста", show_alert=True)


@router.callback_query(F.data.startswith("preview_post|"))
async def show_post_preview(call: types.CallbackQuery, bot: Bot):
    """Показывает предпросмотр поста"""
    try:
        temp = call.data.split("|")
        post_id = int(temp[1])
        
        management_service = PostManagementService(bot)
        preview_url = await management_service.get_post_preview_url(post_id)
        
        if preview_url:
            await call.answer(
                f"🔗 Ссылка на предпросмотр:\n{preview_url}",
                show_alert=True
            )
        else:
            await call.answer(
                "❌ Предпросмотр недоступен (нет бэкапа или пост старше 90 дней)",
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Ошибка показа предпросмотра поста: {e}")
        await call.answer("❌ Ошибка получения предпросмотра", show_alert=True)


@router.callback_query(F.data.in_(["cancel_post_edit", "edit_complete", "back_to_calendar"]))
async def handle_navigation(call: types.CallbackQuery, state: FSMContext):
    """Обрабатывает навигационные кнопки"""
    await state.clear()
    
    if call.data == "cancel_post_edit":
        await call.message.edit_text(
            "❌ Редактирование отменено",
            reply_markup=keyboards.back_to_calendar()
        )
    elif call.data in ["edit_complete", "back_to_calendar"]:
        await call.message.edit_text(
            "📅 Возврат к календарю...",
            reply_markup=keyboards.back_to_main_menu()
        )


def register_calendar_manager() -> Router:
    """Регистрация обработчиков календаря"""
    return router