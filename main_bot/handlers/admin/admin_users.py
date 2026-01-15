"""
Модуль для управления разделом "Админы" (пользователи) в админ-панели.
"""

import io
import logging
import time

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.admin import AdminStates
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

router = Router()

USERS_PER_PAGE = 10


@safe_handler("Админ: Пользователи — список")
async def show_users_list(call: types.CallbackQuery, offset: int = 0) -> None:
    """Отображает список всех пользователей системы."""
    # TODO: Добавить пагинацию в БД для оптимизации на больших объемах
    all_users = await db.user.get_users()
    total = len(all_users)
    users = all_users[offset : offset + USERS_PER_PAGE]

    text_msg = f"👥 <b>Пользователи системы</b>\n\nВсего: {total}\n"
    if not users:
        text_msg += "Пользователи не найдены."

    await call.message.edit_text(
        text_msg,
        reply_markup=keyboards.admin_users_list(users, offset, total),
        parse_mode="HTML",
    )
    await call.answer()
    
    
@safe_handler("Админ: Экспорт пользователей")
async def export_users(call: types.CallbackQuery) -> None:
    """
    Генерирует .txt файл со всеми user_id и отправляет его администратору.
    """
    await call.answer("⏳ Генерация файла экспорта...")
    
    users = await db.user.get_users()
    content = '\n'.join(str(user.id) for user in users)
    
    # Создаем виртуальный файл в памяти
    file_bytes = content.encode('utf-8')
    timestamp = int(time.time())
    file_name = f"nova_users_export_{timestamp}.txt"
    
    # Используем BufferedInputFile вместо FSInputFile для байтов из памяти
    document = types.BufferedInputFile(file_bytes, filename=file_name)
    
    await call.message.answer_document(
        document,
        caption=f"📤 Экспорт пользователей\nВсего записей: {len(users)}"
    )
    
    # Возвращаемся в меню
    await call.message.answer(
        "👥 Меню управления пользователями",
        reply_markup=keyboards.admin_users_management()
    )


@safe_handler("Админ: Импорт пользователей - старт")
async def import_users_start(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Запускает сценарий импорта пользователей.
    Запрашивает файл .txt.
    """
    await call.message.answer(
        "📥 <b>Импорт пользователей</b>\n\n"
        "Отправьте <code>.txt</code> файл, где каждый ID пользователя находится на новой строке.\n"
        "Пример:\n"
        "<code>123456789\n987654321</code>",
        parse_mode="HTML",
        reply_markup=keyboards.back(data="AdminUsers|cancel_import")
    )
    await state.set_state(AdminStates.waiting_for_user_import_file)
    await call.answer()


@safe_handler("Админ: Импорт пользователей - обработка файла")
async def process_import_file(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает полученный файл с ID пользователей.
    """
    if not message.document or not message.document.file_name.endswith('.txt'):
        return await message.answer("❌ Пожалуйста, отправьте файл с расширением .txt")

    processing_msg = await message.answer("⏳ Обработка файла...")

    # Скачиваем файл
    file = await message.bot.download(message.document.file_id)
    content = file.read().decode('utf-8')

    added = 0
    skipped = 0
    errors = 0

    # Парсим и добавляем
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        
        try:
            user_id = int(line)
            if user_id <= 0:
                errors += 1
                continue
            
            # Проверяем существование
            existing = await db.user.get_user(user_id)
            if existing:
                skipped += 1
            else:
                await db.user.add_user(id=user_id)
                added += 1
                
        except ValueError:
            errors += 1
            logger.debug(f"Импорт: невалидная строка '{line}'")

    await state.clear()
    await processing_msg.delete()
    
    result_text = (
        f"✅ <b>Импорт завершён</b>\n\n"
        f"➕ Добавлено: <code>{added}</code>\n"
        f"⏭ Пропущено (уже есть): <code>{skipped}</code>\n"
        f"⚠️ Ошибки (невалидные данные): <code>{errors}</code>"
    )

    await message.answer(
        result_text,
        reply_markup=keyboards.admin_users_management(),
        parse_mode="HTML"
    )


@safe_handler("Админ: Пользователи — детали")
async def view_user_details(call: types.CallbackQuery) -> None:
    """Отображает детальный отчет по администратору."""
    user_id = int(call.data.split("|")[2])
    user = await db.user.get_user(user_id)

    if not user:
        return await call.answer("❌ Пользователь не найден", show_alert=True)

    # Собираем статистику
    channels = await db.channel.get_user_channels(user_id)
    bots = await db.user_bot.get_user_bots(user_id)

    posts_count = await db.post.count_user_posts(user_id)
    stories_count = await db.story.count_user_stories(user_id)
    published_count = await db.published_post.count_user_published(user_id)
    bot_posts_count = await db.bot_post.count_user_bot_posts(user_id)

    msg = "👤 <b>Отчет по администратору</b>\n\n"
    msg += f"<b>Telegram ID:</b> <code>{user_id}</code>\n"
    msg += (
        f"<b>Регистрация:</b> {time.strftime('%d.%m.%Y %H:%M', time.localtime(user.created_timestamp))}\n"
    )
    msg += f"<b>Баланс:</b> {user.balance}₽\n"
    msg += (
        f"<b>Статус:</b> {'✅ Активен' if user.is_active else '❌ Заблокирован'}\n\n"
    )

    msg += "📊 <b>Статистика действий:</b>\n"
    msg += f"├ Постов (план/архив): {posts_count}\n"
    msg += f"├ Опубликовано: {published_count}\n"
    msg += f"├ Историй: {stories_count}\n"
    msg += f"└ Рассылок через ботов: {bot_posts_count}\n\n"

    if channels:
        msg += f"📺 <b>Каналы ({len(channels)}):</b>\n"
        for ch in channels[:5]:
            status = "✅" if ch.subscribe and ch.subscribe > time.time() else "❌"
            msg += f"• {status} {ch.title[:20]}\n"
        if len(channels) > 5:
            msg += f"<i>... и еще {len(channels)-5}</i>\n"
        msg += "\n"

    if bots:
        msg += f"🤖 <b>Боты ({len(bots)}):</b>\n"
        for b in bots:
            msg += f"• {b.title} (@{b.username})\n"
    else:
        msg += "🤖 <b>Боты отсутствуют</b>"

    await call.message.edit_text(
        msg, reply_markup=keyboards.admin_user_details(user_id), parse_mode="HTML"
    )
    await call.answer()


@safe_handler("Админ: Пользователи — колбэки")
async def users_callback_handler(call: types.CallbackQuery, state: FSMContext) -> None:
    """Маршрутизатор колбэков для раздела пользователей."""
    data = call.data.split("|")
    action = data[1]

    if action == "list":
        # Если передан page, используем его, иначе offset
        offset = int(data[2])
        await show_users_list(call, offset)
    elif action == "view":
        await view_user_details(call)
    elif action == "menu":
        await call.message.edit_text(
            "👥 <b>Управление пользователями</b>\n\nВыберите действие:",
            reply_markup=keyboards.admin_users_management(),
            parse_mode="HTML"
        )
        await call.answer()
    elif action == "export":
        await export_users(call)
    elif action == "import":
        await import_users_start(call, state)
    elif action == "cancel_import":
        await state.clear()
        # Возвращаем меню, но нужно отправить новое сообщение, так как мы удалили прошлое
        await call.message.delete() 
        await call.message.answer("👥 Меню управления пользователями", reply_markup=keyboards.admin_users_management())


def get_router() -> Router:
    router.callback_query.register(
        users_callback_handler, F.data.split("|")[0] == "AdminUsers"
    )
    # Регистрируем обработчик файла
    router.message.register(
        process_import_file, 
        AdminStates.waiting_for_user_import_file, 
        F.document
    )
    return router
