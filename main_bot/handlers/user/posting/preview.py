"""
Предпросмотр постов через бэкап систему
"""
import logging
from typing import Optional

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext

from main_bot.utils.posting_service import PostingService
from main_bot.utils.retention_filter import RetentionFilter
from main_bot.database.post.crud import PostCrud
from main_bot.keyboards.keyboards import keyboards

logger = logging.getLogger(__name__)
router = Router(name="post_preview")


@router.callback_query(F.data.startswith("preview_post|"))
async def show_post_preview(call: types.CallbackQuery, bot: Bot):
    """Показать предпросмотр поста из бэкап канала"""
    try:
        temp = call.data.split("|")
        post_id = int(temp[1])
        
        # Проверяем доступность поста (в пределах 90 дней)
        post = await RetentionFilter.get_post_if_accessible(post_id)
        if not post:
            await call.answer(
                "❌ Пост недоступен (старше 90 дней или не существует)",
                show_alert=True
            )
            return
        
        # Получаем URL предпросмотра
        posting_service = PostingService(bot)
        preview_url = await posting_service.get_post_preview_url(post_id)
        
        if preview_url:
            await call.answer(
                f"🔗 Ссылка на предпросмотр:\n{preview_url}",
                show_alert=True
            )
        else:
            await call.answer(
                "❌ Предпросмотр недоступен (бэкап не найден)",
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Ошибка показа предпросмотра поста: {e}")
        await call.answer("❌ Ошибка получения предпросмотра", show_alert=True)


@router.callback_query(F.data.startswith("edit_via_backup|"))
async def edit_post_via_backup(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Редактирование поста через бэкап систему"""
    try:
        temp = call.data.split("|")
        post_id = int(temp[1])
        
        # Проверяем доступность поста (в пределах 90 дней)
        post = await RetentionFilter.get_post_if_accessible(post_id)
        if not post:
            await call.answer(
                "❌ Пост недоступен для редактирования (старше 90 дней или не существует)",
                show_alert=True
            )
            return
        
        # Сохраняем ID поста в состоянии для дальнейшего редактирования
        await state.update_data(editing_post_id=post_id)
        
        await call.message.edit_text(
            "✏️ <b>Редактирование поста через бэкап</b>\n\n"
            "Отправьте новое содержимое поста (текст, медиа с подписью).\n\n"
            "ℹ️ Изменения будут применены сначала в бэкап канале, "
            "затем во всех опубликованных каналах.",
            parse_mode="HTML",\n            reply_markup=keyboards.cancel_edit_backup()\n        )\n        \n        await state.set_state(\"editing_backup_post\")\n        \n    except Exception as e:\n        logger.error(f\"Ошибка начала редактирования поста: {e}\")\n        await call.answer(\"❌ Ошибка инициализации редактирования\", show_alert=True)\n\n\n@router.message(F.text | F.photo | F.video | F.animation)\nasync def process_post_edit(message: types.Message, state: FSMContext, bot: Bot):\n    \"\"\"Обработка нового содержимого поста\"\"\"\n    current_state = await state.get_state()\n    \n    if current_state != \"editing_backup_post\":\n        return\n    \n    try:\n        data = await state.get_data()\n        post_id = data.get(\"editing_post_id\")\n        \n        if not post_id:\n            await message.answer(\"❌ Ошибка: ID поста не найден\")\n            return\n        \n        # Подготавливаем новые опции сообщения\n        new_message_options = {}\n        \n        if message.text:\n            new_message_options['text'] = message.html_text\n        elif message.caption:\n            new_message_options['caption'] = message.html_text\n        \n        # Добавляем медиа если есть\n        if message.photo:\n            new_message_options['photo'] = message.photo[-1].file_id\n        elif message.video:\n            new_message_options['video'] = message.video.file_id\n        elif message.animation:\n            new_message_options['animation'] = message.animation.file_id\n        \n        new_message_options['parse_mode'] = 'HTML'\n        \n        # Применяем изменения через PostingService\n        posting_service = PostingService(bot)\n        results = await posting_service.edit_post_batch(post_id, new_message_options)\n        \n        # Формируем отчет\n        if results['backup_updated']:\n            report_text = \"✅ <b>Пост успешно обновлен!</b>\\n\\n\"\n            report_text += f\"📝 Обновлено каналов: {results['channels_updated']}\\n\"\n            \n            if results['errors']:\n                report_text += \"\\n⚠️ <b>Ошибки при обновлении:</b>\\n\"\n                for error in results['errors'][:5]:  # Показываем первые 5 ошибок\n                    report_text += f\"• {error}\\n\"\n        else:\n            report_text = \"❌ <b>Ошибка обновления поста</b>\\n\\n\"\n            if results['errors']:\n                report_text += \"<b>Детали ошибок:</b>\\n\"\n                for error in results['errors'][:3]:\n                    report_text += f\"• {error}\\n\"\n        \n        await message.answer(\n            report_text,\n            parse_mode=\"HTML\",\n            reply_markup=keyboards.post_edit_complete()\n        )\n        \n        # Очищаем состояние\n        await state.clear()\n        \n    except Exception as e:\n        logger.error(f\"Ошибка обработки редактирования поста: {e}\")\n        await message.answer(\n            \"❌ Произошла ошибка при обновлении поста\",\n            reply_markup=keyboards.post_edit_complete()\n        )\n        await state.clear()\n\n\n@router.callback_query(F.data == \"cancel_backup_edit\")\nasync def cancel_backup_edit(call: types.CallbackQuery, state: FSMContext):\n    \"\"\"Отмена редактирования через бэкап\"\"\"\n    await state.clear()\n    await call.message.edit_text(\n        \"❌ Редактирование отменено\",\n        reply_markup=keyboards.back_to_menu()\n    )\n\n\n@router.callback_query(F.data == \"edit_complete\")\nasync def edit_complete(call: types.CallbackQuery):\n    \"\"\"Завершение редактирования\"\"\"\n    await call.message.edit_text(\n        \"✅ Редактирование завершено\",\n        reply_markup=keyboards.back_to_menu()\n    )\n\n\ndef register_preview_handlers() -> Router:\n    \"\"\"Регистрация обработчиков предпросмотра\"\"\"\n    return router