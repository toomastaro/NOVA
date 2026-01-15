"""
Вспомогательные функции для отправки сообщений ботом.
"""

from aiogram import types, Bot
from loguru import logger

from hello_bot.utils.schemas import MessageOptions, Protect


def get_protect_tag(protect: Protect):
    """
    Определяет тег защиты на основе настроек.

    Args:
        protect: Объект настроек защиты.

    Returns:
        str: Тег защиты ('all', 'arab', 'china' или '').
    """
    if protect.arab and protect.china:
        protect_tag = "all"
    elif protect.arab:
        protect_tag = "arab"
    elif protect.china:
        protect_tag = "china"
    else:
        protect_tag = ""

    return protect_tag


async def answer_message_bot(
    bot: Bot, chat_id: int, message_options: MessageOptions, reply=None
):
    """
    Отправляет сообщение от имени бота.

    Args:
        bot: Экземпляр бота.
        chat_id: ID чата.
        message_options: Опции сообщения (текст, медиа).
        reply: Клавиатура.

    Returns:
        Message: Отправленное сообщение или None при ошибке.
    """
    if message_options.text:
        cor = bot.send_message
    elif message_options.photo:
        cor = bot.send_photo
        message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = bot.send_video
        message_options.video = message_options.video.file_id
    else:
        cor = bot.send_animation
        message_options.animation = message_options.animation.file_id

    dump = message_options.model_dump()
    dump["chat_id"] = chat_id

    if message_options.text:
        dump.pop("photo")
        dump.pop("video")
        dump.pop("animation")
        dump.pop("caption")
    elif message_options.photo:
        dump.pop("video")
        dump.pop("animation")
        dump.pop("text")
        dump.pop("disable_web_page_preview")
    elif message_options.video:
        dump.pop("photo")
        dump.pop("animation")
        dump.pop("text")
        dump.pop("disable_web_page_preview")
    # animation
    else:
        dump.pop("photo")
        dump.pop("video")
        dump.pop("text")
        dump.pop("disable_web_page_preview")

    try:
        post_message = await cor(**dump, reply_markup=reply or message_options.reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения ботом: {e}")
        return None

    return post_message


async def answer_message(message: types.Message, message_options: MessageOptions):
    """
    Отвечает на сообщение пользователя.

    Args:
        message: Исходное сообщение пользователя.
        message_options: Опции ответа.

    Returns:
        Message: Отправленное сообщение.
    """
    if message_options.text:
        cor = message.answer
    elif message_options.photo:
        cor = message.answer_photo
        message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = message.answer_video
        message_options.video = message_options.video.file_id
    else:
        cor = message.answer_animation
        message_options.animation = message_options.animation.file_id

    dump = message_options.model_dump()

    # Удаляем лишние поля, чтобы не вызвать ошибку
    dump.pop("reply_markup", None)

    if message_options.text:
        dump.pop("photo", None)
        dump.pop("video", None)
        dump.pop("animation", None)
        dump.pop("caption", None)
    elif message_options.photo:
        dump.pop("video", None)
        dump.pop("animation", None)
        dump.pop("text", None)
        dump.pop("disable_web_page_preview", None)
    elif message_options.video:
        dump.pop("photo", None)
        dump.pop("animation", None)
        dump.pop("text", None)
        dump.pop("disable_web_page_preview", None)
    else:
        dump.pop("photo", None)
        dump.pop("video", None)
        dump.pop("text", None)
        dump.pop("disable_web_page_preview", None)

    post_message = await cor(
        **dump,
        reply_markup=message_options.reply_markup,
    )

    return post_message
