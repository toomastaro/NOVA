"""
Утилиты для работы с сообщениями и превью постов.

Этот модуль содержит функции для:
- Отправки превью постов, сторис и бот-постов
- Отправки сообщений через ботов
- Работы с медиафайлами в сообщениях
"""
import os
import logging

from aiogram import types, Bot
from aiogram.fsm.context import FSMContext

from config import Config
from main_bot.database.bot_post.model import BotPost
from main_bot.database.post.model import Post
from main_bot.database.story.model import Story
from main_bot.keyboards import keyboards
from main_bot.utils.schemas import MessageOptions, StoryOptions, MessageOptionsHello, MessageOptionsCaptcha
from instance_bot import bot as main_bot_obj

logger = logging.getLogger(__name__)


async def answer_bot_post(message: types.Message, state: FSMContext, from_edit: bool = False):
    """
    Отправить превью бот-поста пользователю.
    
    Args:
        message: Сообщение пользователя
        state: FSM контекст с данными поста
        from_edit: Флаг редактирования (влияет на клавиатуру)
        
    Returns:
        Отправленное сообщение
    """
    data = await state.get_data()

    post: BotPost = data.get('post')
    is_edit: bool = data.get('is_edit')
    message_options = MessageOptionsHello(**post.message)

    # Определяем тип сообщения и соответствующую функцию
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

    if not from_edit:
        reply_markup = keyboards.manage_bot_post(
            post=post,
            is_edit=is_edit
        )
        message_options.reply_markup = reply_markup

    post_message = await cor(
        **message_options.model_dump(),
        parse_mode='HTML'
    )

    return post_message


async def answer_post(message: types.Message, state: FSMContext, from_edit: bool = False):
    """
    Отправить превью поста пользователю.
    
    Пытается загрузить превью из бэкапа, если доступно.
    В противном случае генерирует локально.
    
    Args:
        message: Сообщение пользователя
        state: FSM контекст с данными поста
        from_edit: Флаг редактирования (влияет на клавиатуру)
        
    Returns:
        Отправленное сообщение
    """
    data = await state.get_data()

    post: Post = data.get('post')
    is_edit: bool = data.get('is_edit')
    message_options = MessageOptions(**post.message_options)

    # Определяем тип сообщения и соответствующую функцию
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

    if from_edit:
        reply_markup = keyboards.post_kb(
            post=post
        )
    else:
        reply_markup = keyboards.manage_post(
            post=post,
            show_more=data.get('show_more'),
            is_edit=is_edit
        )

    # Логика загрузки превью из бэкапа
    if post.backup_message_id and Config.BACKUP_CHAT_ID:
        try:
            post_message = await message.bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=Config.BACKUP_CHAT_ID,
                message_id=post.backup_message_id,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            logger.info(f"Превью для поста {post.id} загружено из бэкапа (msg {post.backup_message_id})")
            return post_message
        except Exception as e:
            logger.error(f"Не удалось загрузить превью из бэкапа для поста {post.id}: {e}", exc_info=True)
            # Fallback к локальной генерации

    post_message = await cor(
        **message_options.model_dump(),
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    logger.info(f"Превью для поста {post.id} сгенерировано локально")

    return post_message


async def answer_story(message: types.Message, state: FSMContext, from_edit: bool = False):
    """
    Отправить превью сторис пользователю.
    
    Args:
        message: Сообщение пользователя
        state: FSM контекст с данными сторис
        from_edit: Флаг редактирования (влияет на клавиатуру)
        
    Returns:
        Отправленное сообщение
    """
    data = await state.get_data()

    post: Story = data.get('post')
    is_edit: bool = data.get('is_edit')
    story_options = StoryOptions(**post.story_options)

    # Сторис может быть только фото или видео
    if story_options.photo:
        cor = message.answer_photo
        story_options.photo = story_options.photo.file_id
    else:
        cor = message.answer_video
        story_options.video = story_options.video.file_id

    if from_edit:
        reply_markup = None
    else:
        reply_markup = keyboards.manage_story(
            post=post,
            is_edit=is_edit
        )

    post_message = await cor(
        **story_options.model_dump(),
        reply_markup=reply_markup
    )

    return post_message


async def answer_message_bot(bot: Bot, chat_id: int, message_options: MessageOptionsHello | MessageOptionsCaptcha):
    """
    Отправить сообщение через бота в указанный чат.
    
    Скачивает медиафайлы если необходимо, отправляет сообщение,
    затем удаляет временные файлы.
    
    Args:
        bot: Экземпляр бота для отправки
        chat_id: ID чата для отправки
        message_options: Опции сообщения (текст/фото/видео/анимация)
        
    Returns:
        Отправленное сообщение или None при ошибке
    """
    # Определяем тип сообщения
    if message_options.text:
        cor = bot.send_message
    elif message_options.photo:
        cor = bot.send_photo
    elif message_options.video:
        cor = bot.send_video
    else:
        cor = bot.send_animation

    # Ищем file_id медиафайла
    attrs = ["photo", "video", "animation"]
    file_id = next(
        (getattr(message_options, attr).file_id for attr in attrs
         if getattr(message_options, attr)),
        None
    )

    # Скачиваем медиафайл если есть
    try:
        filepath = None
        if file_id:
            get_file = await main_bot_obj.get_file(file_id)
            filepath = "main_bot/utils/temp/hello_message_media_{}".format(
                get_file.file_path.split("/")[-1]
            )
            await main_bot_obj.download(file_id, filepath)
    except Exception as e:
        logger.error(f"Ошибка при скачивании медиафайла: {e}")
        return None

    dump = message_options.model_dump()
    dump['chat_id'] = chat_id
    dump['parse_mode'] = 'HTML'

    # Удаляем специфичные поля для капчи
    if isinstance(message_options, MessageOptionsCaptcha):
        dump.pop("resize_markup", None)

    # Удаляем неиспользуемые поля в зависимости от типа сообщения
    if message_options.text:
        dump.pop("photo", None)
        dump.pop("video", None)
        dump.pop("animation", None)
        dump.pop("caption", None)

    elif message_options.photo:
        if filepath:
            dump["photo"] = types.FSInputFile(filepath)

        dump.pop("video", None)
        dump.pop("animation", None)
        dump.pop("text", None)

    elif message_options.video:
        if filepath:
            dump["video"] = types.FSInputFile(filepath)

        dump.pop("photo", None)
        dump.pop("animation", None)
        dump.pop("text", None)
    # animation
    else:
        if filepath:
            dump["animation"] = types.FSInputFile(filepath)

        dump.pop("photo", None)
        dump.pop("video", None)
        dump.pop("text", None)

    # Отправляем сообщение
    try:
        post_message = await cor(**dump)
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        return None

    # Удаляем временный файл
    if filepath:
        try:
            os.remove(filepath)
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {filepath}: {e}")

    return post_message


async def answer_message(message: types.Message, message_options: MessageOptionsHello | MessageOptionsCaptcha):
    """
    Ответить на сообщение пользователя с указанными опциями.
    
    Args:
        message: Сообщение пользователя
        message_options: Опции сообщения (текст/фото/видео/анимация)
        
    Returns:
        Отправленное сообщение
    """
    # Определяем тип сообщения
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

    post_message = await cor(
        **message_options.model_dump(),
        parse_mode='HTML'
    )

    return post_message
