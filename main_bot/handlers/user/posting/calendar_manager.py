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
from main_bot.database.types.post_status import PostStatus, PostStatusRu
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
            
        # Форматируем время
        if post_info['send_time']:
            send_time_str = datetime.fromtimestamp(post_info['send_time']).strftime('%d.%m.%Y %H:%M')
        else:
            send_time_str = 'Сразу'
            
        if post_info['posted_timestamp']:
            posted_time_str = datetime.fromtimestamp(post_info['posted_timestamp']).strftime('%d.%m.%Y %H:%M')
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
        new_message_options = {}\n        \n        if message.text:\n            new_message_options['text'] = message.html_text\n        elif message.caption:\n            new_message_options['caption'] = message.html_text\n            \n        # Добавляем медиа если есть\n        if message.photo:\n            new_message_options['photo'] = message.photo[-1].file_id\n        elif message.video:\n            new_message_options['video'] = message.video.file_id\n        elif message.animation:\n            new_message_options['animation'] = message.animation.file_id\n            \n        new_message_options['parse_mode'] = 'HTML'\n        \n        # Применяем изменения\n        management_service = PostManagementService(bot)\n        result = await management_service.edit_post(\n            post_id, new_message_options, message.from_user.id\n        )\n        \n        # Формируем отчет\n        if result['success']:\n            report_text = f\"✅ <b>Пост #{post_id} обновлен!</b>\\n\\n{result['message']}\"\n            \n            if result['updated_channels'] > 0:\n                report_text += f\"\\n📺 Обновлено каналов: {result['updated_channels']}\"\n                \n            if result['errors']:\n                report_text += \"\\n\\n⚠️ <b>Предупреждения:</b>\\n\"\n                for error in result['errors'][:3]:\n                    report_text += f\"• {error}\\n\"\n        else:\n            report_text = f\"❌ <b>Ошибка обновления поста #{post_id}</b>\\n\\n{result['message']}\"\n            \n        await message.answer(\n            report_text,\n            parse_mode=\"HTML\",\n            reply_markup=keyboards.post_edit_complete()\n        )\n        \n        await state.clear()\n        \n    except Exception as e:\n        logger.error(f\"Ошибка обработки редактирования поста: {e}\")\n        await message.answer(\n            \"❌ Произошла ошибка при обновлении поста\",\n            reply_markup=keyboards.post_edit_complete()\n        )\n        await state.clear()\n\n\n@router.callback_query(F.data.startswith(\"delete_post|\"))\nasync def confirm_delete_post(call: types.CallbackQuery, bot: Bot):\n    \"\"\"Подтверждение удаления поста\"\"\"\n    try:\n        temp = call.data.split(\"|\")\n        post_id = int(temp[1])\n        \n        management_service = PostManagementService(bot)\n        posts = await management_service.get_posts_for_calendar(call.from_user.id)\n        post_info = next((p for p in posts if p['id'] == post_id), None)\n        \n        if not post_info:\n            await call.answer(\"❌ Пост не найден\", show_alert=True)\n            return\n            \n        if not post_info['can_delete']:\n            await call.answer(\"❌ Пост недоступен для удаления\", show_alert=True)\n            return\n            \n        delete_text = (\n            f\"❓ <b>Удалить пост #{post_id}?</b>\\n\\n\"\n            f\"Статус: {post_info['status_display']}\\n\"\n        )\n        \n        if post_info['status'] == PostStatus.POSTED:\n            delete_text += \"\\n⚠️ Пост уже отправлен. Он будет помечен как удаленный.\"\n        else:\n            delete_text += \"\\n🗑 Пост будет полностью удален.\"\n            \n        await call.message.edit_text(\n            delete_text,\n            parse_mode=\"HTML\",\n            reply_markup=keyboards.confirm_delete_post(post_id)\n        )\n        \n    except Exception as e:\n        logger.error(f\"Ошибка подтверждения удаления поста: {e}\")\n        await call.answer(\"❌ Ошибка удаления поста\", show_alert=True)\n\n\n@router.callback_query(F.data.startswith(\"confirm_delete|\"))\nasync def execute_delete_post(call: types.CallbackQuery, bot: Bot):\n    \"\"\"Выполняет удаление поста\"\"\"\n    try:\n        temp = call.data.split(\"|\")\n        post_id = int(temp[1])\n        \n        management_service = PostManagementService(bot)\n        result = await management_service.delete_post(post_id, call.from_user.id)\n        \n        if result['success']:\n            await call.message.edit_text(\n                f\"✅ {result['message']}\",\n                reply_markup=keyboards.back_to_calendar()\n            )\n        else:\n            await call.message.edit_text(\n                f\"❌ {result['message']}\",\n                reply_markup=keyboards.back_to_calendar()\n            )\n            \n    except Exception as e:\n        logger.error(f\"Ошибка выполнения удаления поста: {e}\")\n        await call.answer(\"❌ Ошибка при удалении поста\", show_alert=True)\n\n\n@router.callback_query(F.data.startswith(\"preview_post|\"))\nasync def show_post_preview(call: types.CallbackQuery, bot: Bot):\n    \"\"\"Показывает предпросмотр поста\"\"\"\n    try:\n        temp = call.data.split(\"|\")\n        post_id = int(temp[1])\n        \n        management_service = PostManagementService(bot)\n        preview_url = await management_service.get_post_preview_url(post_id)\n        \n        if preview_url:\n            await call.answer(\n                f\"🔗 Ссылка на предпросмотр:\\n{preview_url}\",\n                show_alert=True\n            )\n        else:\n            await call.answer(\n                \"❌ Предпросмотр недоступен (нет бэкапа или пост старше 90 дней)\",\n                show_alert=True\n            )\n            \n    except Exception as e:\n        logger.error(f\"Ошибка показа предпросмотра поста: {e}\")\n        await call.answer(\"❌ Ошибка получения предпросмотра\", show_alert=True)\n\n\n@router.callback_query(F.data.in_([\"cancel_post_edit\", \"edit_complete\", \"back_to_calendar\"]))\nasync def handle_navigation(call: types.CallbackQuery, state: FSMContext):\n    \"\"\"Обрабатывает навигационные кнопки\"\"\"\n    await state.clear()\n    \n    if call.data == \"cancel_post_edit\":\n        await call.message.edit_text(\n            \"❌ Редактирование отменено\",\n            reply_markup=keyboards.back_to_calendar()\n        )\n    elif call.data in [\"edit_complete\", \"back_to_calendar\"]:\n        await call.message.edit_text(\n            \"📅 Возврат к календарю...\",\n            reply_markup=keyboards.back_to_main_menu()\n        )\n\n\ndef register_calendar_manager() -> Router:\n    \"\"\"Регистрация обработчиков календаря\"\"\"\n    return router