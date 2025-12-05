"""
Модуль управления постом и редактирования параметров.

Содержит логику:
- Управление постом (отмена, переход к выбору каналов, показать больше)
- Редактирование параметров (текст, медиа, кнопки, реакции)
- Отмена редактирования и удаление параметров
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.handlers.user.posting.menu import show_create_post
from main_bot.utils.message_utils import answer_post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import MessageOptions, Media
from main_bot.utils.backup_utils import edit_backup_message, update_live_messages
from main_bot.keyboards import keyboards
from main_bot.states.user import Posting

logger = logging.getLogger(__name__)


async def manage_post(call: types.CallbackQuery, state: FSMContext):
    """
    Управление постом - обработка различных действий с постом.
    
    Действия:
    - cancel: отмена создания/редактирования поста
    - next: переход к выбору каналов
    - show_more: показать/скрыть дополнительные параметры
    - notification, media_above, has_spoiler, pin_time: переключение параметров
    - text, media, buttons, reaction, hide: начало редактирования параметра
    
    Args:
        call: Callback query с данными действия
        state: FSM контекст
    """
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Post = data.get('post')
    is_edit: bool = data.get('is_edit')

    # Отмена создания/редактирования
    if temp[1] == 'cancel':
        if is_edit:
            post_message = await answer_post(call.message, state, from_edit=True)
            await state.update_data(
                post_message=post_message,
                show_more=False
            )
            await call.message.delete()
            return await call.message.answer(
                text("post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_post(
                    post=post,
                    is_published=data.get("is_published")
                )
            )

        await db.delete_post(data.get('post').id)
        await call.message.delete()
        return await show_create_post(call.message, state)

    # Переход к выбору каналов
    if temp[1] == "next":
        if is_edit:
            post_message = await answer_post(call.message, state, from_edit=True)
            await state.update_data(
                post_message=post_message,
                show_more=False
            )
            await call.message.delete()
            return await call.message.answer(
                text("post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_post(
                    post=post,
                    is_published=data.get("is_published")
                )
            )

        objects = await db.get_user_channels_without_folders(
            user_id=call.from_user.id
        )
        folders = await db.get_folders(
            user_id=call.from_user.id
        )
        await state.update_data(
            chosen=[],
            current_folder_id=None
        )

        await call.message.delete()
        return await call.message.answer(
            text("choice_channels:post").format(
                0, ""
            ),
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=[],
                folders=folders
            )
        )

    # Показать/скрыть дополнительные параметры
    if temp[1] == 'show_more':
        await state.update_data(
            show_more=not data.get('show_more')
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.manage_post(
                post=data.get('post'),
                show_more=not data.get('show_more'),
                is_edit=is_edit
            )
        )

    # Переключение параметров (notification, media_above, has_spoiler, pin_time)
    if temp[1] in ['notification', 'media_above', 'has_spoiler', 'pin_time']:
        message_options = MessageOptions(**data.get('post').message_options)
        
        if temp[1] == 'notification':
            message_options.disable_notification = not message_options.disable_notification

        if temp[1] in ['media_above', 'has_spoiler']:
            if not message_options.photo and not message_options.video and not message_options.animation:
                return await call.answer(text("require_media"), show_alert=True)

            if temp[1] == 'has_spoiler':
                message_options.has_spoiler = not message_options.has_spoiler
            if temp[1] == 'media_above':
                message_options.show_caption_above_media = not message_options.show_caption_above_media
        
        if temp[1] == 'pin_time':
            # Переключаем закреп: если был включен - выключаем, если выключен - включаем (True)
            new_pin_value = not post.pin_time if post.pin_time else True

        # Обновление в БД
        if data.get("is_published"):
            # Update all published posts with same post_id
            update_kwargs = {}
            if temp[1] == 'pin_time':
                update_kwargs['pin_time'] = new_pin_value
            else:
                update_kwargs['message_options'] = message_options.model_dump()
            
            await db.update_published_posts_by_post_id(
                post_id=post.post_id,
                **update_kwargs
            )
            # Fetch updated object (just one of them to keep in state)
            post = await db.get_published_post_by_id(post.id)
        else:
            update_kwargs = {}
            if temp[1] == 'pin_time':
                update_kwargs['pin_time'] = new_pin_value
            else:
                update_kwargs['message_options'] = message_options.model_dump()
            
            post = await db.update_post(
                post_id=data.get('post').id,
                return_obj=True,
                **update_kwargs
            )
        
        # Update backup message
        await edit_backup_message(post)
        
        # Update live messages if published
        if data.get("is_published"):
            await update_live_messages(post.post_id, message_options)

        await state.update_data(
            post=post
        )

        await call.message.delete()
        return await answer_post(call.message, state)

    # Начало редактирования параметра
    await state.update_data(
        param=temp[1]
    )

    await call.message.delete()
    message_text = text("manage:post:new:{}".format(temp[1]))

    if temp[1] in ["text", "media", "buttons", "reaction"]:
        input_msg = await call.message.answer(
            message_text,
            reply_markup=keyboards.param_cancel(
                param=temp[1]
            )
        )
        await state.set_state(Posting.input_value)
        await state.update_data(
            input_msg_id=input_msg.message_id
        )

    if temp[1] == "hide":
        await call.message.answer(
            message_text,
            reply_markup=keyboards.param_hide(
                post=data.get('post')
            )
        )


async def cancel_value(call: types.CallbackQuery, state: FSMContext):
    """
    Отмена редактирования параметра или удаление значения параметра.
    
    Args:
        call: Callback query с данными действия
        state: FSM контекст
    """
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    # Удаление значения параметра
    if temp[1] == 'delete':
        param = data.get('param')

        if param in ["text", "media"]:
            message_options = MessageOptions(**data.get('post').message_options)

            if param == "text":
                message_options.text = message_options.caption = None
            if param == "media":
                message_options.photo = message_options.video = message_options.animation = None

                if message_options.caption:
                    message_options.text = message_options.caption
                    message_options.caption = None

            # Проверка: если все поля пусты - удаляем пост
            none_list = [
                message_options.text is None,
                message_options.caption is None,
                message_options.photo is None,
                message_options.video is None,
                message_options.animation is None,
            ]
            if False not in none_list:
                await state.clear()
                await call.message.delete()
                await db.delete_post(data.get('post').id)
                return await show_create_post(call.message, state)

            kwargs = {"message_options": message_options.model_dump()}
        else:
            kwargs = {param: None}

        post = await db.update_post(
            post_id=data.get('post').id,
            return_obj=True,
            **kwargs
        )
        await state.update_data(
            post=post
        )
        data = await state.get_data()

    await state.clear()
    await state.update_data(data)

    await call.message.delete()

    # Для cpm_price возвращаемся к выбору каналов
    if data.get('param') == "cpm_price":
        post: Post = data.get("post")
        chosen = data.get("chosen", post.chat_ids)
        display_objects = await db.get_user_channels(
            user_id=call.from_user.id,
            from_array=chosen[:10]
        )
        return await call.message.answer(
            text("choice_channels:post").format(
                len(chosen),
                "\\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in display_objects
                )
            ),
            reply_markup=keyboards.finish_params(
                obj=post
            )
        )

    await answer_post(call.message, state)


async def get_value(message: types.Message, state: FSMContext):
    """
    Получение нового значения параметра от пользователя.
    
    Обрабатывает:
    - text: текст поста
    - media: медиа (фото, видео, анимация)
    - buttons: кнопки
    - reaction: реакции
    - cpm_price: цена CPM
    
    Args:
        message: Сообщение от пользователя с новым значением
        state: FSM контекст
    """
    data = await state.get_data()
    param = data.get('param')

    # Валидация типа сообщения
    if param == "media" and message.text:
        return await message.answer(
            text("error_value")
        )
    if param != "media" and not message.text:
        return await message.answer(
            text("error_value")
        )

    post: Post = data.get("post")
    
    # Обработка текста и медиа
    if param in ["text", "media"]:
        message_options = MessageOptions(**post.message_options)

        if param == "text":
            if message_options.photo or message_options.video or message_options.animation:
                message_options.caption = message.html_text
            else:
                message_options.text = message.html_text

        if param == "media":
            if message.photo:
                message_options.photo = Media(file_id=message.photo[-1].file_id)
            if message.video:
                message_options.video = Media(file_id=message.video.file_id)
            if message.animation:
                message_options.animation = Media(file_id=message.animation.file_id)

            if message_options.text:
                message_options.caption = message_options.text
                message_options.text = None

        kwargs = {"message_options": message_options.model_dump()}

    else:
        value = message.text

        # Обработка cpm_price
        if param in ["cpm_price"]:
            try:
                value = int(value)
            except ValueError:
                return await message.answer(
                    text("error_value")
                )
        else:
            # Обработка кнопок и реакций
            if param == "buttons":
                post.buttons = value
            else:
                # Парсинг реакций
                c = 0
                dict_react = {'rows': []}
                for a, row in enumerate(message.text.split('\\n')):
                    reactions = []
                    for react in row.split('|'):
                        reactions.append({'id': c, 'react': react, 'users': []})
                        c += 1
                    dict_react['rows'].append({'id': a, 'reactions': reactions})

                post.reaction = dict_react
                value = dict_react

            # Проверка валидности кнопок/реакций
            try:
                post: Post = data.get("post")
                check = await message.answer("...", reply_markup=keyboards.manage_post(post))
                await check.delete()
            except (IndexError, TypeError):
                return await message.answer(
                    text("error_value")
                )

        kwargs = {param: value}

    # Обновление в БД
    if data.get("is_published"):
        await db.update_published_posts_by_post_id(
            post_id=post.post_id,
            **kwargs
        )
        post = await db.get_published_post_by_id(post.id)
    else:
        post = await db.update_post(
            post_id=post.id,
            return_obj=True,
            **kwargs
        )

    # Update backup message if content changed
    if param in ["text", "media", "buttons", "reaction"]:
        await edit_backup_message(post)
        
        # Refresh post object to get updated backup_message_id if fallback occurred
        if data.get("is_published"):
            post = await db.get_published_post_by_id(post.id)
        else:
            post = await db.get_post(post.id)

        # Update live messages if published
        if data.get("is_published"):
            message_options = MessageOptions(**post.message_options)
            reply_markup = keyboards.post_kb(post=post)
            await update_live_messages(post.post_id, message_options, reply_markup=reply_markup)

    await state.clear()
    data['post'] = post
    await state.update_data(data)

    await message.bot.delete_message(
        message.chat.id,
        data.get("input_msg_id")
    )

    # Для cpm_price возвращаемся к выбору каналов
    if param == "cpm_price":
        chosen = data.get("chosen", post.chat_ids)
        display_objects = await db.get_user_channels(
            user_id=message.from_user.id,
            from_array=chosen[:10]
        )
        return await message.answer(
            text("choice_channels:post").format(
                len(chosen),
                "\\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in display_objects
                )
            ),
            reply_markup=keyboards.finish_params(
                obj=post
            )
        )

    await answer_post(message, state)
