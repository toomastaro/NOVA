"""
Обработчики технической поддержки.

Модуль реализует:
- Прием сообщений от пользователей в поддержку
- Пересылку сообщений админу
- Ответ администратора пользователю через reply
"""
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from config import Config
from main_bot.keyboards import keyboards
from main_bot.states.user import Support
from main_bot.utils.lang.language import text
import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Support Back")
async def support_back(call: types.CallbackQuery, state: FSMContext):
    """Возврат из меню поддержки в профиль."""
    await state.clear()

    await call.message.delete()

    # Возврат в меню настроек (профиль)
    await call.message.answer(
        text("start_profile_text"),
        reply_markup=keyboards.profile_menu(),
        parse_mode="HTML",
    )


@safe_handler("Get User Message")
async def get_user_message(message: types.Message, state: FSMContext):
    """
    Принимает сообщение от пользователя и отправляет его админу поддержки.
    Поддерживает текст и фото.
    """
    if message.photo:
        await message.bot.send_photo(
            photo=message.photo[-1].file_id,
            chat_id=Config.ADMIN_SUPPORT,
            caption=text("user_support_msg").format(
                message.caption,
                message.from_user.full_name,
                message.from_user.username,
                message.from_user.id,
            ),
        )
    else:
        await message.bot.send_message(
            chat_id=Config.ADMIN_SUPPORT,
            text=text("user_support_msg").format(
                message.text,
                message.from_user.full_name,
                message.from_user.username,
                message.from_user.id,
            ),
        )

    await state.clear()
    await message.answer(
        text("success_msg_support")
    )


@safe_handler("Get Support Message")
async def get_support_message(message: types.Message):
    """
    Обработчик ответа администратора пользователю.
    Работает через reply на сообщение, пересланное от пользователя.
    """
    try:
        # ВНИМАНИЕ: Парсинг ID зависит от формата сообщения в user_support_msg ("ID: 12345")
        # Если формат текста изменится, этот код сломается.
        user_id = (
            message.reply_to_message.caption.split("ID: ")[1]
            if message.reply_to_message.caption
            else message.reply_to_message.text.split("ID: ")[1]
        )
    except Exception:
        logger.error("Ошибка парсинга ID пользователя из сообщения поддержки")
        return

    # Импортируем Reply клавиатуру для главного меню
    from main_bot.keyboards.common import Reply

    if message.photo:
        await message.bot.send_photo(
            photo=message.photo[-1].file_id,
            chat_id=user_id,
            caption=text("support_answer").format(message.caption),
            reply_markup=Reply.menu(),
        )
    else:
        await message.bot.send_message(
            chat_id=user_id,
            text=text("support_answer").format(message.text),
            reply_markup=Reply.menu(),
        )


def get_router():
    """Регистрация роутеров поддержки."""
    router = Router()
    router.message.register(get_user_message, Support.message, F.text | F.photo)
    router.message.register(
        get_support_message, (F.chat.id == Config.ADMIN_SUPPORT) & (F.text | F.photo)
    )
    router.callback_query.register(
        support_back, F.data.split("|")[0] == "CancelSupport"
    )
    return router
