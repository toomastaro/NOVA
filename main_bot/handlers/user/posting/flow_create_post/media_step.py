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
from main_bot.handlers.user.posting.menu import show_create_post
from main_bot.utils.message_utils import answer_post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import MessageOptions, Media
from main_bot.utils.backup_utils import edit_backup_message, update_live_messages
from main_bot.keyboards import keyboards
from main_bot.keyboards.posting import ensure_obj
from main_bot.states.user import Posting
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler(
    "Постинг: управление постом"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post = ensure_obj(data.get("post"))
    is_edit: bool = data.get("is_edit")

    # Отмена создания/редактирования
    if temp[1] == "cancel":
        if is_edit:
            post_message = await answer_post(call.message, state, from_edit=True)
            await state.update_data(
                post_message={"message_id": post_message.message_id}, show_more=False
            )
            await call.message.delete()
            # Логика возврата
            await state.update_data(show_more=False)

            if data.get("is_published"):
                # Возврат к просмотру опубликованного поста
                from main_bot.handlers.user.posting.content import (
                    generate_post_info_text,
                )

                info_text = await generate_post_info_text(post, is_published=True)

                return await call.message.answer(
                    info_text, reply_markup=keyboards.manage_published_post(post=post)
                )
            else:
                # Возврат к черновикам/отложенным
                from main_bot.handlers.user.posting.content import (
                    generate_post_info_text,
                )

                info_text = await generate_post_info_text(post, is_published=False)

                return await call.message.answer(
                    info_text,
                    reply_markup=keyboards.manage_remain_post(
                        post=post, is_published=False
                    ),
                )

        if post:
            await db.post.delete_post(post.id)
        await call.message.delete()
        return await show_create_post(call.message, state)

    # Переход к настройкам или выбору каналов
    if temp[1] == "next":
        if is_edit:
            post_message = await answer_post(call.message, state, from_edit=True)
            await state.update_data(
                post_message={"message_id": post_message.message_id}, show_more=False
            )
            await call.message.delete()
            return await call.message.answer(
                text("post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title,
                ),
                reply_markup=keyboards.manage_remain_post(
                    post=post, is_published=data.get("is_published")
                ),
            )

        # Для нового поста - переход к настройкам
        chosen = data.get("chosen", [])
        display_objects = await db.channel.get_user_channels(
            user_id=call.from_user.id, from_array=chosen
        )

        # Форматируем список выбранных каналов
        if chosen:
            channels_list = (
                "<blockquote expandable>"
                + "\n".join(
                    text("resource_title").format(obj.title) for obj in display_objects
                )
                + "</blockquote>"
            )
        else:
            channels_list = ""

        await call.message.delete()

        # Force refresh main menu
        from main_bot.keyboards.common import Reply

        await call.message.answer(
            text("manage_post_settings"), reply_markup=Reply.menu()
        )

        return await call.message.answer(
            text("manage:post:finish_params").format(len(chosen), channels_list),
            reply_markup=keyboards.finish_params(obj=post),
            parse_mode="HTML",
        )

    # Показать/скрыть дополнительные параметры
    if temp[1] == "show_more":
        await state.update_data(show_more=not data.get("show_more"))
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.manage_post(
                post=data.get("post"),
                show_more=not data.get("show_more"),
                is_edit=is_edit,
            )
        )

    # Переключение параметров (notification, media_above, has_spoiler, pin_time)
    if temp[1] in ["notification", "media_above", "has_spoiler", "pin_time"]:
        post_obj = ensure_obj(data.get("post"))
        message_options = MessageOptions(**post_obj.message_options)

        if temp[1] == "notification":
            message_options.disable_notification = (
                not message_options.disable_notification
            )

        if temp[1] in ["media_above", "has_spoiler"]:
            if (
                not message_options.photo
                and not message_options.video
                and not message_options.animation
            ):
                return await call.answer(text("require_media"), show_alert=True)

            if temp[1] == "has_spoiler":
                message_options.has_spoiler = not message_options.has_spoiler
            if temp[1] == "media_above":
                message_options.show_caption_above_media = (
                    not message_options.show_caption_above_media
                )

        if temp[1] == "pin_time":
            # Переключаем закреп
            # Обработка PublishedPost (unpin_time) vs Post (pin_time)
            current_val = getattr(post, "pin_time", getattr(post, "unpin_time", None))
            new_pin_value = not current_val if current_val else True

        # Обновление в БД
        if data.get("is_published"):
            # Обновление всех опубликованных постов с одинаковым post_id
            update_kwargs = {}
            if temp[1] == "pin_time":
                update_kwargs["unpin_time"] = new_pin_value
            else:
                update_kwargs["message_options"] = message_options.model_dump()

            post_id_val = post_obj.post_id or post_obj.id
            await db.published_post.update_published_posts_by_post_id(
                post_id=post_id_val, **update_kwargs
            )
            # Получаем обновленный объект (только один, чтобы сохранить в state)
            post = await db.published_post.get_published_post_by_id(post_obj.id)
        else:
            update_kwargs = {}
            if temp[1] == "pin_time":
                update_kwargs["pin_time"] = new_pin_value
            else:
                update_kwargs["message_options"] = message_options.model_dump()

            post = await db.post.update_post(
                post_id=data.get("post")["id"], return_obj=True, **update_kwargs
            )

        # Обновляем бекап сообщения
        await edit_backup_message(post)

        # Обновляем live-сообщения, если опубликовано
        if data.get("is_published"):
            await update_live_messages(post.post_id, message_options)

        post_dict = {
            col.name: getattr(post, col.name) for col in post.__table__.columns
        }
        await state.update_data(post=post_dict)

        await call.message.delete()
        return await answer_post(call.message, state)

    # Начало редактирования параметра
    await state.update_data(param=temp[1])

    await call.message.delete()
    message_text = text("manage:post:new:{}".format(temp[1]))

    if temp[1] in ["text", "media", "buttons", "reaction"]:
        input_msg = await call.message.answer(
            message_text, reply_markup=keyboards.param_cancel(param=temp[1])
        )
        await state.set_state(Posting.input_value)
        await state.update_data(input_msg_id=input_msg.message_id)

    if temp[1] == "hide":
        await call.message.answer(
            message_text, reply_markup=keyboards.param_hide(post=data.get("post"))
        )


@safe_handler(
    "Постинг: отмена значения"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def cancel_value(call: types.CallbackQuery, state: FSMContext):
    """
    Отмена редактирования параметра или удаление значения параметра.

    Args:
        call: Callback query с данными действия
        state: FSM контекст
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    # Удаление значения параметра
    if temp[1] == "delete":
        param = data.get("param")

        if param in ["text", "media"]:
            post_obj = ensure_obj(data.get("post"))
            message_options = MessageOptions(**post_obj.message_options)

            if param == "text":
                message_options.text = message_options.caption = None
            if param == "media":
                message_options.photo = message_options.video = (
                    message_options.animation
                ) = None

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
                await db.post.delete_post(data.get("post")["id"])
                return await show_create_post(call.message, state)

            kwargs = {"message_options": message_options.model_dump()}
        else:
            kwargs = {param: None}

        post = await db.post.update_post(
            post_id=data.get("post")["id"], return_obj=True, **kwargs
        )
        post_dict = {
            col.name: getattr(post, col.name) for col in post.__table__.columns
        }
        await state.update_data(post=post_dict)
        data = await state.get_data()

    # Установка значения из кнопки
    if temp[1] == "set":
        param = data.get("param")
        value = temp[2]

        # Обработка cpm_price
        if param in ["cpm_price"]:
            try:
                value = int(value)
            except ValueError:
                return await call.answer(text("error_value"))
        else:
            # Для других параметров пока просто передаем значение (расширяемо)
            pass

        kwargs = {param: value}

        # Получаем объект поста из состояния
        post_obj = ensure_obj(data.get("post"))

        # Обновление в БД
        if data.get("is_published"):
            post = ensure_obj(data.get("post"))
            await db.published_post.update_published_posts_by_post_id(
                post_id=post.post_id or post.id, **kwargs
            )
            post = await db.published_post.get_published_post_by_id(
                post.id
            )
        else:
            post = await db.post.update_post(
                post_id=ensure_obj(data.get("post")).id, return_obj=True, **kwargs
            )

        post_dict = {
            col.name: getattr(post, col.name) for col in post.__table__.columns
        }
        await state.update_data(post=post_dict)
        data = await state.get_data()

    if temp[1] not in ["delete", "set"]:
        await state.clear()
        await state.update_data(data)
        await call.message.delete()

    if temp[1] in ["delete", "set"]:
        await state.clear()
        await state.update_data(data)
        await call.message.delete()

    # Для cpm_price возвращаемся к выбору каналов (или к посту, если опубликован)
    if data.get("param") == "cpm_price":
        post = ensure_obj(data.get("post"))

        if data.get("is_published"):
            from main_bot.handlers.user.posting.content import generate_post_info_text

            info_text = await generate_post_info_text(post, is_published=True)
            return await call.message.answer(
                info_text, reply_markup=keyboards.manage_published_post(post=post)
            )

        # Handle difference between Post (chat_ids) and PublishedPost (chat_id)
        if hasattr(post, "chat_ids"):
            default_chosen = post.chat_ids
        elif hasattr(post, "chat_id"):
            default_chosen = [post.chat_id]
        else:
            default_chosen = []

        chosen = data.get("chosen", default_chosen) or []

        display_objects = await db.channel.get_user_channels(
            user_id=call.from_user.id, from_array=chosen
        )
        return await call.message.answer(
            text("choice_channels:post").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.title) for obj in display_objects
                ),
            ),
            reply_markup=keyboards.finish_params(obj=post),
        )

    await answer_post(call.message, state)


@safe_handler(
    "Постинг: получение значения"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
    param = data.get("param")

    # Валидация типа сообщения
    if param == "media" and message.text:
        return await message.answer(text("error_value"))
    if param != "media" and not message.text:
        return await message.answer(text("error_value"))

    post = ensure_obj(data.get("post"))

    # Проверка наличия поста
    if not post:
        await message.answer(text("keys_data_error"))
        return

    # Обработка текста и медиа
    if param in ["text", "media"]:
        # Проверка длины текста
        is_media = (
            bool(
                message.photo or message.video or message.animation or message.document
            )
            or param == "media"
        )
        # Если меняем медиа, то это точно будет пост с медиа.
        # Если меняем текст, проверяем есть ли уже медиа в посту.
        if param == "text":
            is_media = bool(
                post.message_options.get("photo")
                or post.message_options.get("video")
                or post.message_options.get("animation")
            )

        limit = 2048 if is_media else 4096
        message_text_length = len(message.caption or message.text or "")

        if message_text_length > limit:
            logger.warning(
                "Пользователь %s: превышена длина текста при редактировании (%d > %d)",
                message.from_user.id,
                message_text_length,
                limit,
            )
            return await message.answer(text("error_length_text").format(limit))

        message_options = MessageOptions(**post.message_options)

        # Принудительно захватываем HTML-разметку
        # Детальное логирование для отладки форматирования (спойлеров)
        # Если html_text почему-то пуст или без тегов, пробуем проверить сущности напрямую
        final_html = message.html_text
        entities = message.entities or message.caption_entities or []
        has_spoiler_entity = any(e.type == "spoiler" for e in entities)
        
        logger.info(
            "Пользователь %s: захвачен HTML (длина %d). Медиа: %s. Тип сущностей: %s. Текст содержит спойлер (entity): %s, спойлер (tag): %s",
            message.from_user.id,
            len(final_html or ""),
            is_media,
            "caption" if message.caption_entities else "text" if message.entities else "none",
            has_spoiler_entity,
            "tg-spoiler" in (final_html or "")
        )
        
        # Если это медиа и есть сущность спойлера, но нет тега в html_text - это баг aiogram/пересылки
        if has_spoiler_entity and "tg-spoiler" not in (final_html or ""):
            logger.warning("ОБНАРУЖЕН БАГ: Сущность спойлера есть, а тега в HTML нет! Принудительно восстанавливаем.")
            from aiogram.utils.text_decorations import html_decoration
            text_to_format = message.text or message.caption or ""
            final_html = html_decoration.unparse(text_to_format, entities)
            
            if is_media:
                message_options.caption = final_html
            else:
                message_options.text = final_html
            
            logger.info("Восстановленный HTML: %s", final_html)
        if final_html and "<" in final_html:
            logger.debug("Захваченный HTML: %s", final_html[:500])

        if param == "text":
            if (
                message_options.photo
                or message_options.video
                or message_options.animation
            ):
                message_options.caption = captured_html
                message_options.text = None
            else:
                message_options.text = captured_html
                message_options.caption = None

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
                return await message.answer(text("error_value"))
        else:
            # Обработка кнопок и реакций
            if param == "buttons":
                post.buttons = value
            else:
                # Парсинг реакций
                c = 0
                dict_react = {"rows": []}
                for a, row in enumerate(message.text.split("\\n")):
                    reactions = []
                    for react in row.split("|"):
                        reactions.append({"id": c, "react": react, "users": []})
                        c += 1
                    dict_react["rows"].append({"id": a, "reactions": reactions})

                post.reaction = dict_react
                value = dict_react

            # Проверка валидности кнопок/реакций
            try:
                check = await message.answer(
                    "...", reply_markup=keyboards.manage_post(post)
                )
                await check.delete()
            except (IndexError, TypeError):
                return await message.answer(text("error_value"))

        kwargs = {param: value}

    # Обновление в БД
    if data.get("is_published"):
        post_obj = ensure_obj(post)
        post_id_val = post_obj.post_id or post_obj.id
        await db.published_post.update_published_posts_by_post_id(
            post_id=post_id_val, **kwargs
        )
        post = await db.published_post.get_published_post_by_id(post_obj.id)
    else:
        post = await db.post.update_post(
            post_id=ensure_obj(data.get("post")).id, return_obj=True, **kwargs
        )

    # Update backup message if content changed
    if param in ["text", "media", "buttons", "reaction"]:
        # Обновление бекапа сообщения если контент изменился
        await edit_backup_message(post)

        # Обновление объекта поста, чтобы получить новый backup_message_id если произошел фоллбек
        if data.get("is_published"):
            wrapped_post = ensure_obj(post)
            post = (
                await db.published_post.get_published_post_by_id(wrapped_post.id)
                if post
                else None
            )
        else:
            wrapped_post = ensure_obj(post)
            post = await db.post.get_post(wrapped_post.id) if post else None

        # Обновление live-сообщений если опубликовано
        if data.get("is_published"):
            message_options = MessageOptions(**post.message_options)
            reply_markup = keyboards.post_kb(post=post)
            post_id_val = post.post_id or post.id
            await update_live_messages(
                post_id_val, message_options, reply_markup=reply_markup
            )

    await state.clear()
    data["post"] = {col.name: getattr(post, col.name) for col in post.__table__.columns}
    await state.update_data(data)

    await message.bot.delete_message(message.chat.id, data.get("input_msg_id"))

    if param == "cpm_price":
        # Handle difference between Post (chat_ids) and PublishedPost (chat_id)
        if hasattr(post, "chat_ids"):
            default_chosen = post.chat_ids
        elif hasattr(post, "chat_id"):
            default_chosen = [post.chat_id]
        else:
            default_chosen = []

        chosen = data.get("chosen", default_chosen)
        display_objects = await db.channel.get_user_channels(
            user_id=message.from_user.id, from_array=chosen
        )
        return await message.answer(
            text("choice_channels:post").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.title) for obj in display_objects
                ),
            ),
            reply_markup=keyboards.finish_params(obj=post),
        )

    await answer_post(message, state)
