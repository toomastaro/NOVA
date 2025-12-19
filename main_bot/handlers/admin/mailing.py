"""
Модуль массовой рассылки для администраторов.

Содержит:
- Прием контента для рассылки.
- Подтверждение и запуск процесса рассылки.
- Фоновое выполнение рассылки с контролем частоты запросов (flood control).
"""

import asyncio
import logging
import time

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.database.db import db
from main_bot.states.admin import AdminMailing
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

# Константы для контроля флуда
MAX_CONCURRENT_REQUESTS = 30  # Сообщений в секунду


async def broadcast_task(bot: Bot, admin_id: int, message_to_copy: types.Message, user_ids: list) -> None:
    """
    Фоновая задача для массовой рассылки сообщений пользователям.

    Аргументы:
        bot (Bot): Экземпляр бота.
        admin_id (int): Telegram ID администратора для отправки отчета.
        message_to_copy (types.Message): Объект сообщения, которое нужно скопировать.
        user_ids (list): Список ID пользователей-получателей.
    """
    logger.info(f"Запуск массовой рассылки от админа {admin_id} на {len(user_ids)} пользователей")
    
    success = 0
    errors = 0
    start_time = time.time()
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def send_to_user(user_id: int) -> None:
        """
        Отправка сообщения конкретному пользователю.
        """
        nonlocal success, errors
        async with semaphore:
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message_to_copy.chat.id,
                    message_id=message_to_copy.message_id
                )
                success += 1
            except Exception as e:
                errors += 1
                logger.debug(f"Ошибка отправки пользователю {user_id}: {e}")
            
            # Небольшая задержка для соблюдения лимитов
            await asyncio.sleep(0.05)

    # Запускаем задачи параллельно с ограничением семафором
    tasks = [send_to_user(uid) for uid in user_ids]
    await asyncio.gather(*tasks)

    duration = round(time.time() - start_time, 2)
    logger.info(f"Рассылка завершена за {duration}с. Успешно: {success}, Ошибок: {errors}")

    # Отправка отчета администратору
    try:
        report = text("admin:mailing:finished").format(success, errors)
        await bot.send_message(admin_id, report, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось отправить отчет о рассылке администратору {admin_id}: {e}")


@safe_handler("Админ-панель: прием сообщения для рассылки")
async def get_mailing_post(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик получения контента для рассылки.
    Запрашивает подтверждение перед запуском.
    """
    logger.info(f"Админ {message.from_user.id} прислал контент для рассылки")
    
    all_users = await db.user.get_users()
    count = len(all_users)
    
    # Сохраняем данные сообщения для последующего копирования
    await state.update_data(
        mail_chat_id=message.chat.id,
        mail_msg_id=message.message_id
    )
    
    # Генерация клавиатуры подтверждения
    kb = InlineKeyboardBuilder()
    kb.button(text=text("admin:mailing:btn:send"), callback_data="AdminMail|confirm")
    kb.button(text=text("admin:mailing:btn:cancel"), callback_data="Admin|back")
    kb.adjust(1)
    
    await message.answer(
        text("admin:mailing:confirm").format(count),
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(AdminMailing.confirm)


@safe_handler("Админ-панель: подтверждение и запуск рассылки")
async def confirm_mailing(call: types.CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """
    Обработчик подтверждения рассылки.
    Запускает асинхронную задачу рассылки и очищает состояние.
    """
    logger.info(f"Админ {call.from_user.id} подтвердил запуск рассылки")
    
    data = await state.get_data()
    msg_id = data.get("mail_msg_id")
    chat_id = data.get("mail_chat_id")
    
    if not msg_id or not chat_id:
        logger.warning(f"Данные для рассылки утеряны в состоянии админа {call.from_user.id}")
        await call.answer("❌ Ошибка: данные сообщения утеряны", show_alert=True)
        return await state.clear()

    # Получаем список всех ID пользователей
    users = await db.user.get_users()
    user_ids = [u.id for u in users]
    
    # Подготовка объекта сообщения для передачи в таску
    message_to_copy = types.Message(
        message_id=msg_id,
        chat=types.Chat(id=chat_id, type="private"),
        date=int(time.time())
    )

    # Запуск фонового процесса
    asyncio.create_task(broadcast_task(bot, call.from_user.id, message_to_copy, user_ids))
    
    await call.message.edit_text(
        text("admin:mailing:started"),
        parse_mode="HTML"
    )
    await state.clear()
    await call.answer()


def get_router() -> Router:
    """
    Создает и настраивает роутер для модуля рассылки.

    Возвращает:
        Router: Настроенный роутер.
    """
    router = Router(name="AdminMailing")
    router.message.register(get_mailing_post, AdminMailing.post)
    router.callback_query.register(confirm_mailing, F.data == "AdminMail|confirm", AdminMailing.confirm)
    return router
