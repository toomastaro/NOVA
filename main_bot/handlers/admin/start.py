"""
Модуль стартового меню администратора.

Содержит:
- Обработку команды /admin
- Главное меню панели администратора
- Навигацию по разделам (сессии, промокоды)
"""

import logging
import os

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import Config
from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.admin import Promo, AdminMailing, AdminTest
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler
import uuid

logger = logging.getLogger(__name__)


@safe_handler("Админ: меню — команда /admin или /админ")
async def admin_menu(message: types.Message) -> None:
    """
    Показать главное меню администратора.
    Доступно только пользователям из списка Config.ADMINS.
    Команды: /admin, /админ
    """
    if message.from_user.id not in Config.ADMINS:
        return

    await message.answer(text("admin:menu:title"), reply_markup=keyboards.admin())


@safe_handler("Админ: меню — навигация")
async def choice(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработка нажатий в админ-меню.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    action = temp[1]

    if action == "session":
        # Проверяем наличие директории сессий
        session_dir = "main_bot/utils/sessions/"
        session_count = 0
        if os.path.exists(session_dir):
            session_count = len(os.listdir(session_dir))

        try:
            await call.message.edit_text(
                text("admin:session:available").format(session_count),
                reply_markup=keyboards.admin_sessions(),
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Error editing session message: {e}")
                raise

    elif action == "promo":
        await call.message.edit_text(
            text("admin:promo:input"),
            reply_markup=keyboards.back(data="AdminPromoBack"),
        )
        await state.set_state(Promo.input)

    elif action == "mail":
        await call.message.edit_text(
            text("admin:mailing:input"),
            reply_markup=keyboards.back(data="Admin|back"),
            parse_mode="HTML"
        )
        await state.set_state(AdminMailing.post)

    elif action == "back":
        try:
            await call.message.edit_text(
                text("admin:menu:title"), reply_markup=keyboards.admin()
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Error editing back message: {e}")
                raise

    elif action == "stats":
        """
        Отображение статистики сервиса.
        Показывает данные по пользователям, пополнениям и покупкам.
        """
        try:
            stats = await db.stats.get_admin_stats()
            
            stats_text = (
                "📊 <b>СТАТИСТИКА СЕРВИСА</b>\n\n"
                "👤 <b>Пользователи:</b>\n"
                f"├ Всего: <code>{stats['users_total']}</code>\n"
                f"├ За 30 дней: <code>+{stats['users_30d']}</code>\n"
                f"├ За 7 дней: <code>+{stats['users_7d']}</code>\n"
                f"└ За 24 часа: <code>+{stats['users_24h']}</code>\n\n"
                
                "💰 <b>Финансы (Пополнения):</b>\n"
                f"├ Всего: <code>{stats['payments_total_sum']:,}₽</code> ({stats['payments_total_count']} транз.)\n"
                f"├ За 7 дней: <code>{stats['payments_7d_sum']:,}₽</code>\n"
                f"└ За 24 часа: <code>{stats['payments_24h_sum']:,}₽</code>\n\n"
                
                "🛍 <b>Финансы (Покупки услуг):</b>\n"
                f"├ Всего: <code>{stats['purchases_total_sum']:,}₽</code> ({stats['purchases_total_count']} оплат)\n"
                f"├ За 7 дней: <code>{stats['purchases_7d_sum']:,}₽</code>\n"
                f"└ За 24 часа: <code>{stats['purchases_24h_sum']:,}₽</code>\n\n"
                
                "<i>* Статистика обновляется в реальном времени</i>"
            )
            
            await call.message.edit_text(
                stats_text,
                reply_markup=keyboards.back(data="Admin|back"),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in stats: {e}", exc_info=True)
            await call.answer("❌ Ошибка при получении статистики", show_alert=True)

    elif action in ["test_invisible", "test_bottom"]:
        """
        Тестирование метода «Скрытая ссылка» (Invisible Link).
        test_invisible - картинка сверху.
        test_bottom - картинка снизу.
        """
        is_above = action == "test_invisible"
        target_chat_id = -1003252039305
        image_url = "https://bot.stafflink.biz/images/ab1d3e16abe20ea3f5570ae787ffc81e.jpg"
        invisible_link = f'<a href="{image_url}">\u200b</a>'
        
        premium_emojis = "⚡️💎👑🚀🔥🌟✨"
        title = "СВЕРХУ" if is_above else "СНИЗУ"
        base_text = (
            f"{invisible_link}<b>🧪 ТЕСТ: КАРТИНКА {title}</b>\n\n"
            f"Этот пост тестирует отображение скрытой картинки в позиции: <b>{title}</b>.\n"
            f"Премиум эмодзи: {premium_emojis}\n\n"
        )
        
        filler = "Это тестовая строка для заполнения объема сообщения. " 
        long_text = base_text + (filler * 60)
        long_text += f"\n\n🔚 Конец сообщения. Итоговая длина: {len(long_text)} символов."
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb_builder = InlineKeyboardBuilder()
        for i in range(4):
            kb_builder.button(text=f"Кнопка {i+1} ➡️ Нова", url="https://t.me/novatg")
        kb_builder.adjust(2)
        
        logger.info(f"Запуск теста Invisible Link ({title}). Цель: {target_chat_id}, Длина: {len(long_text)}")
        
        try:
            from instance_bot import bot
            from aiogram.types import LinkPreviewOptions
            
            # Настройки превью: управляем позицией через is_above
            preview_options = LinkPreviewOptions(
                is_disabled=False,
                prefer_large_media=True,
                show_above_text=is_above
            )
            
            # 1. Отправка в канал
            await bot.send_message(
                chat_id=target_chat_id,
                text=long_text,
                parse_mode="HTML",
                reply_markup=kb_builder.as_markup(),
                link_preview_options=preview_options
            )
            
            # 2. Показываем превью самому админу
            await bot.send_message(
                chat_id=call.from_user.id,
                text=f"📢 <b>Превью ({title}):</b>\n\n{long_text}",
                parse_mode="HTML",
                reply_markup=kb_builder.as_markup(),
                link_preview_options=preview_options
            )
            
            await call.answer(f"✅ Тест ({title}) отправлен!", show_alert=True)
        except Exception as e:
            logger.error(f"Ошибка при отправке теста {title}: {e}", exc_info=True)
            await call.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)

    elif action == "test_parse":
        """Начало теста с парсингом: запрашиваем пост"""
        await call.message.edit_text(
            "📝 <b>Режим теста: Парсинг и Пост</b>\n\n"
            "Пришлите мне сообщение с картинкой и текстом (капшеном). "
            "Я сохраню картинку в локальное хранилище и переотправлю пост методом 'Скрытая ссылка'.",
            reply_markup=keyboards.back(data="Admin|back"),
            parse_mode="HTML"
        )
        await state.set_state(AdminTest.waiting_for_post)

    await call.answer()


@safe_handler("Админ: тест — обработка присланного поста")
async def process_test_post(message: types.Message, state: FSMContext) -> None:
    """
    Обработка присланного админом поста для теста Invisible Link.
    """
    if message.from_user.id not in Config.ADMINS:
        return

    if not message.photo:
        await message.answer("❌ Пожалуйста, пришлите сообщение именно с <b>ФОТО</b>.")
        return

    # 1. Подготовка папки
    os.makedirs(Config.PUBLIC_IMAGES_PATH, exist_ok=True)

    # 2. Сохранение фото
    photo = message.photo[-1]
    file_ext = ".jpg" # Telegram фото обычно jpg
    unique_name = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(Config.PUBLIC_IMAGES_PATH, unique_name)
    
    from instance_bot import bot
    await bot.download(photo, destination=file_path)
    logger.info(f"Тест: Фото сохранено в {file_path}")

    # 3. Формирование ссылки и текста
    image_url = f"{Config.PUBLIC_IMAGES_URL}{unique_name}"
    invisible_link = f'<a href="{image_url}">\u200b</a>'
    
    # Получаем исходный текст с сохранением HTML
    caption = message.html_text if message.caption else "Без текста"
    
    # Добавляем инфо-блок
    final_text = (
        f"{invisible_link}🚀 <b>АВТО-ТЕСТ INVISIBLE LINK</b>\n"
        f"🖼 <i>Картинка сохранена локально:</i>\n<code>{unique_name}</code>\n\n"
        f"{caption}"
    )

    # 4. Кнопки (берем из исходного сообщения)
    reply_markup = message.reply_markup
    if reply_markup:
        logger.info(f"Тест: Обнаружены кнопки в исходном сообщении ({len(reply_markup.inline_keyboard)} рядов)")
    else:
        logger.info("Тест: Кнопки в исходном сообщении отсутствуют.")

    # 5. Отправка
    target_chat_id = -1003252039305
    try:
        from aiogram.types import LinkPreviewOptions
        preview_options = LinkPreviewOptions(
            is_disabled=False,
            prefer_large_media=True,
            show_above_text=True
        )

        # В канал
        await bot.send_message(
            chat_id=target_chat_id,
            text=final_text,
            parse_mode="HTML",
            reply_markup=reply_markup, # Используем оригинальные кнопки
            link_preview_options=preview_options
        )
        
        # Админу
        await message.answer(
            f"✅ <b>Готово!</b>\n\n"
            f"Публичная ссылка: <code>{image_url}</code>\n\n"
            f"Пост отправлен в канал. Ниже — превью для вас (кнопки сохранены):",
            parse_mode="HTML"
        )
        await message.answer(
            final_text,
            parse_mode="HTML",
            reply_markup=reply_markup, # Используем оригинальные кнопки
            link_preview_options=preview_options
        )
        
        await state.clear()
        logger.info("Авто-тест Invisible Link успешно завершен.")
    except Exception as e:
        logger.error(f"Ошибка в авто-тесте: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")


def get_router() -> Router:
    """
    Регистрация роутера для админ-меню.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.message.register(admin_menu, Command("admin"))
    router.message.register(admin_menu, Command("админ"))  # Русская команда
    router.callback_query.register(choice, F.data.split("|")[0] == "Admin")
    router.message.register(process_test_post, AdminTest.waiting_for_post)
    return router
