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
from main_bot.utils.schemas import MessageOptions
from main_bot.utils.media_manager import MediaManager
from main_bot.utils.post_assembler import PostAssembler
from main_bot.keyboards import keyboards
from main_bot.keyboards.posting import ensure_obj
from main_bot.utils.backup_utils import edit_backup_message, update_live_messages
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
                import re
                raw_text = text("require_media")
                # Очистка от HTML тегов для safe alert
                clean_text = re.sub(r'<[^>]+>', '', raw_text)
                return await call.answer(clean_text, show_alert=True)

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
            message_text, reply_markup=keyboards.param_hide(post=post)
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
            post = await db.published_post.get_published_post_by_id(post.id)
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


@safe_handler("Постинг: получение значения")
async def get_value(message: types.Message, state: FSMContext):
    """
    Получение нового значения параметра от пользователя (Унифицированный поток).
    """
    data = await state.get_data()
    param = data.get("param")
    post_data = data.get("post")

    if not post_data:
        await message.answer(text("keys_data_error"))
        return

    # 1. Загружаем текущее состояние (Сущность)
    try:
        current_options = MessageOptions(**post_data.get("message_options", {}))
    except Exception:
        current_options = MessageOptions()

    # 2. Обработка изменений в зависимости от параметра
    new_html = current_options.html_text or ""
    new_buttons = post_data.get("buttons")
    new_reaction = post_data.get("reaction")
    
    # CPM цена вынесена из message_options, но мы ее тоже можем менять здесь
    new_cpm = post_data.get("cpm_price")

    if param in ["text", "media"]:
        # Валидация
        if param == "media" and message.text:
            return await message.answer(text("error_value"))
        if param == "text" and not message.text:
            return await message.answer(text("error_value"))

        # Лимиты текста
        is_media = bool(message.photo or message.video or message.animation or current_options.media_value)
        limit = 2048 if is_media else 4096
        input_text = message.html_text or message.caption or ""
        
        if len(input_text) > limit:
            return await message.answer(text("error_length_text").format(limit))

        if param == "text":
            new_html = input_text
        
    elif param == "buttons":
        new_buttons = message.text
        
    elif param == "reaction":
        # Парсинг реакций
        c = 0
        dict_react = {"rows": []}
        for a, row in enumerate(message.text.split("\\n")):
            reactions = []
            for react in row.split("|"):
                reactions.append({"id": c, "react": react, "users": []})
                c += 1
            dict_react["rows"].append({"id": a, "reactions": reactions})
        new_reaction = dict_react
        
    elif param == "cpm_price":
        try:
            new_cpm = int(message.text)
        except ValueError:
            return await message.answer(text("error_value"))

    # 3. Адаптивная трансформация медиа
    # Передаем существующие медиа-данные для сохранения при правке только текста
    media_value, is_invisible, media_type = await MediaManager.process_media_for_post(
        message=message,
        caption=new_html,
        existing_media=current_options.media_value,
        existing_type=current_options.media_type
    )

    # 4. Сборка финального объекта через PostAssembler
    # Это гарантирует, что HTML всегда актуален и содержит невидимую ссылку если надо
    final_message_options = PostAssembler.assemble_message_options(
        html_text=new_html,
        media_type=media_type,
        media_value=media_value,
        is_invisible=is_invisible,
        buttons=new_buttons,
        reaction=new_reaction
    )
    
    # Сохраняем остальные настройки (уведомления и т.д.)
    final_message_options["disable_notification"] = current_options.disable_notification
    final_message_options["has_spoiler"] = current_options.has_spoiler
    final_message_options["show_caption_above_media"] = current_options.show_caption_above_media
    
    # 5. Сохранение в БД
    kwargs = {
        "message_options": final_message_options,
        "buttons": new_buttons,
        "reaction": new_reaction,
        "cpm_price": new_cpm
    }

    if data.get("is_published"):
        post_id_val = post_data.get("post_id") or post_data.get("id")
        await db.published_post.update_published_posts_by_post_id(post_id=post_id_val, **kwargs)
        post = await db.published_post.get_published_post_by_id(post_data.get("id"))
    else:
        post = await db.post.update_post(post_id=post_data.get("id"), return_obj=True, **kwargs)

    # 6. Синхронизация live-сообщений
    if data.get("is_published") and post:
        from main_bot.utils.backup_utils import update_live_messages
        msg_opts = MessageOptions(**post.message_options)
        reply_markup = keyboards.post_kb(post=post)
        await update_live_messages(post.post_id or post.id, msg_opts, reply_markup=reply_markup)

    # 7. Обновление состояния и ответ
    await state.clear()
    data["post"] = {col.name: getattr(post, col.name) for col in post.__table__.columns}
    await state.update_data(data)
    
    # Удаляем сервисное сообщение ввода
    if data.get("input_msg_id"):
        try:
            await message.bot.delete_message(message.chat.id, data.get("input_msg_id"))
        except Exception:
            pass

    # Для cpm_price возвращаем меню выбора каналов
    if param == "cpm_price":
        # ... (логика возврата к каналам оставлена без изменений)
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
