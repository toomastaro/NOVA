"""
Модуль выбора каналов и настройки расписания для stories.

Содержит логику:
- Выбор каналов для публикации stories
- Настройка финальных параметров
- Выбор времени отправки
- Вспомогательные функции для отображения лимитов stories
"""

import time
import logging
from datetime import datetime

from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.utils.message_utils import answer_story
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import StoryOptions
from main_bot.keyboards import keyboards
from main_bot.states.user import Stories
from utils.error_handler import safe_handler
from main_bot.utils.user_settings import get_user_view_mode, set_user_view_mode

logger = logging.getLogger(__name__)


async def get_story_report_text(chosen, objects):
    """
    Формирование текста отчета для выбранных каналов.

    Args:
        chosen: Список выбранных chat_id
        objects: Список объектов каналов

    Returns:
        str: Форматированный текст
    """
    lines = []
    target_ids = chosen[:10]
    target_objects = [obj for obj in objects if obj.chat_id in target_ids]

    for obj in target_objects:
        lines.append(text("resource_title").format(obj.title))

    return "\n".join(lines)


async def set_folder_content(
    resource_id, chosen, chosen_folders, user_channels: list = None
):
    """
    Добавление/удаление всех каналов из папки в список выбранных.

    Args:
        resource_id: ID папки
        chosen: Список выбранных chat_id
        chosen_folders: Список выбранных folder_id
        user_channels: Список загруженных каналов пользователя (опционально) для оптимизации

    Returns:
        tuple: (chosen, chosen_folders) или ("subscribe", "") при ошибке
    """
    folder = await db.user_folder.get_folder_by_id(folder_id=resource_id)
    is_append = resource_id not in chosen_folders

    if is_append:
        chosen_folders.append(resource_id)
    else:
        chosen_folders.remove(resource_id)

    # Создаем карту каналов для быстрого поиска: {chat_id: channel_obj}
    channels_map = {obj.chat_id: obj for obj in user_channels} if user_channels else {}

    channel_ids = [int(cid) for cid in folder.content]

    for chat_id in channel_ids:
        # Оптимизация: Берем из переданного списка (O(1))
        channel = channels_map.get(chat_id)

        # Если канала нет в списке пользователя (редкий кейс, но возможен), грузим из БД
        if not channel:
            channel = await db.channel.get_channel_by_chat_id(chat_id)

        if not channel or not channel.subscribe:
            return "subscribe", ""

        if not channel.session_path:
            return "session_path", ""

        if is_append:
            if chat_id in chosen:
                continue
            chosen.append(chat_id)
        else:
            if chat_id not in chosen:
                continue
            chosen.remove(chat_id)

    return chosen, chosen_folders


@safe_handler(
    "Сторис: выбор каналов"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_channels(call: types.CallbackQuery, state: FSMContext):
    """Выбор каналов для публикации stories."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    chosen: list = data.get("chosen")
    chosen_folders: list = data.get("chosen_folders")
    current_folder_id = data.get("current_folder_id")

    view_mode = await get_user_view_mode(call.from_user.id)

    # Переключение вида
    if temp[1] == "switch_view":
        view_mode = "channels" if view_mode == "folders" else "folders"
        await set_user_view_mode(call.from_user.id, view_mode)

        # Сбрасываем пагинацию и вход в папку
        if view_mode == "channels":
            await state.update_data(current_folder_id=None)
            current_folder_id = None

        temp = list(temp)
        if len(temp) > 2:
            temp[2] = "0"
        else:
            temp.append("0")

    # Определяем что показывать
    if current_folder_id:
        # Внутри папки - показываем содержимое папки
        folder = await db.user_folder.get_folder_by_id(current_folder_id)
        if folder and folder.content:
            objects = await db.channel.get_user_channels(
                user_id=call.from_user.id,
                from_array=[int(cid) for cid in folder.content],
                sort_by="stories",
            )
        else:
            objects = []
        folders = []
    elif view_mode == "channels":
        # Режим "Все каналы": показываем плоский список всех каналов
        objects = await db.channel.get_user_channels(
            user_id=call.from_user.id, sort_by="stories", limit=500
        )
        folders = []
    else:
        # Режим "Папки" (или стандартный)
        objects = await db.channel.get_user_channels(
            user_id=call.from_user.id, sort_by="stories"
        )
        folders = await db.user_folder.get_folders(user_id=call.from_user.id)
        # В режиме папок мы не показываем каналы на верхнем уровне
        if view_mode == "folders":
            objects = []
            kb_folders = [f for f in folders if f.content]
            folders = (
                kb_folders  # Keep consistent nomenclature if needed, or just filter
            )
        else:
            pass

    if temp[1] == "next_step":
        if not chosen:
            return await call.answer(text("error_min_choice"))

        # Сохраняем выбранные каналы
        await state.update_data(chosen=chosen)

        # Переходим к вводу медиа
        await call.message.edit_text(
            text("input_stories"),
            reply_markup=keyboards.cancel(data="InputStoryCancel"),
        )
        await state.set_state(Stories.input_message)
        return

    if temp[1] == "cancel":
        if current_folder_id:
            # Возврат к корневому уровню
            await state.update_data(current_folder_id=None)
            current_folder_id = None

            # Перезагружаем корневые данные
            if view_mode == "folders":
                objects = []
                raw_folders = await db.user_folder.get_folders(
                    user_id=call.from_user.id
                )
                folders = [f for f in raw_folders if f.content]
            else:
                objects = await db.channel.get_user_channels(
                    user_id=call.from_user.id, sort_by="stories", limit=500
                )
                folders = []

            # Сбрасываем remover
            remover_value = 0
            try:
                await call.answer()
            except Exception:
                pass
        else:
            # Возврат в меню историй
            from main_bot.handlers.user.menu import start_stories

            await call.message.delete()
            return await start_stories(call.message)

    if temp[1] in ["next", "back"]:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                chosen_folders=chosen_folders,
                remover=int(temp[2]),
                data="ChoiceStoriesChannels",
                view_mode=view_mode,
                is_inside_folder=bool(current_folder_id),
            )
        )

    if temp[1] == "choice_all":
        current_ids = [i.chat_id for i in objects]

        # Проверяем, все ли выбраны в текущем виде
        all_selected = all(cid in chosen for cid in current_ids)

        if all_selected:
            # Отменяем выбор всех видимых
            for cid in current_ids:
                if cid in chosen:
                    chosen.remove(cid)
        else:
            # Проверяем подписку для всех каналов
            channels_without_sub = []
            for obj in objects:
                if not obj.subscribe:
                    channels_without_sub.append(obj.title)

            if channels_without_sub:
                # Показываем список каналов без подписки
                channels_list = "\n".join(
                    f"• {title}" for title in channels_without_sub[:5]
                )
                if len(channels_without_sub) > 5:
                    channels_list += f"\n... и ещё {len(channels_without_sub) - 5}"

                return await call.answer(
                    f"❌ Невозможно выбрать все каналы\n\n"
                    f"Следующие каналы не имеют активной подписки:\n{channels_list}\n\n"
                    f"Оплатите подписку через меню 💎 Подписка",
                    show_alert=True,
                )

            # Проверка сессии для сторис
            channels_without_session = []
            for obj in objects:
                if not obj.session_path:
                    channels_without_session.append(obj.title)

            if channels_without_session:
                channels_list = "\n".join(
                    f"• {title}" for title in channels_without_session[:5]
                )
                return await call.answer(
                    f"❌ Невозможно выбрать все каналы\n\n"
                    f"Следующие каналы не имеют подключенной сессии для сторис:\n{channels_list}",
                    show_alert=True,
                )

            # Выбираем все видимые
            for cid in current_ids:
                if cid not in chosen:
                    chosen.append(cid)

    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])
        resource_type = temp[3] if len(temp) > 3 else None

        if resource_type == "folder":
            # Вход в папку
            await state.update_data(current_folder_id=resource_id)
            current_folder_id = resource_id

            # Загружаем содержимое папки
            folder = await db.user_folder.get_folder_by_id(resource_id)
            if folder and folder.content:
                objects = await db.channel.get_user_channels(
                    user_id=call.from_user.id,
                    from_array=[int(cid) for cid in folder.content],
                    sort_by="stories",
                )
            else:
                objects = []
            folders = []

            # Сбрасываем пагинацию
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = "0"
            else:
                temp.append("0")
        else:
            # Выбор канала
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                channel = await db.channel.get_channel_by_chat_id(resource_id)
                if not channel.subscribe:
                    return await call.answer(
                        text("error_sub_channel").format(channel.title), show_alert=True
                    )

                # Проверка на наличие MTProto сессии для сторис
                if not channel.session_path:
                    return await call.answer(
                        text("error_story_session").format(channel.title),
                        show_alert=True,
                    )

                chosen.append(resource_id)

    await state.update_data(chosen=chosen, chosen_folders=chosen_folders)

    # Формируем текст
    folder_title = ""
    if current_folder_id:
        try:
            folder_obj = await db.user_folder.get_folder_by_id(current_folder_id)
            if folder_obj:
                folder_title = folder_obj.title
        except Exception:
            pass

    msg_text = (
        text("choice_channels:folder").format(
            folder_title, len(chosen), await get_story_report_text(chosen, objects)
        )
        if current_folder_id and folder_title
        else text("choice_channels:story").format(
            len(chosen), await get_story_report_text(chosen, objects)
        )
    )

    await call.message.edit_text(
        msg_text,
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            chosen_folders=chosen_folders,
            remover=(remover_value if "remover_value" in locals() else int(temp[2])),
            data="ChoiceStoriesChannels",
            view_mode=view_mode,
            is_inside_folder=bool(current_folder_id),
        ),
    )


@safe_handler(
    "Сторис: завершение параметров"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def finish_params(call: types.CallbackQuery, state: FSMContext):
    """Настройка финальных параметров stories перед публикацией."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    # Lazy load post
    post_obj = data.get("post")
    if post_obj:
        from main_bot.keyboards.posting import ensure_obj

        post = ensure_obj(post_obj)
    else:
        post_id = data.get("post_id")
        if not post_id:
            await call.answer(text("keys_data_error"))
            return await call.message.delete()
        post = await db.story.get_story(post_id)
        if not post:
            await call.answer(text("story_not_found"))
            return await call.message.delete()

    story_options = (
        post.story_options
        if isinstance(post.story_options, dict)
        else post.story_options
    )
    options = StoryOptions(**story_options)

    chosen: list = data.get("chosen", post.chat_ids)
    objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="stories"
    )

    if temp[1] == "cancel":
        # Показываем превью сторис
        await call.message.delete()
        await answer_story(call.message, state)
        return

    if temp[1] == "report":
        await db.story.update_story(
            post_id=post.id, return_obj=False, report=not post.report
        )
        # В FSM не обновляем
        post = await db.story.get_story(post.id)
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_params(obj=post, data="FinishStoriesParams")
        )

    if temp[1] == "delete_time":
        return await call.message.edit_text(
            text("manage:story:new:delete_time"),
            reply_markup=keyboards.choice_delete_time_story(),
        )

    if temp[1] == "send_time":
        await call.message.edit_text(
            text("manage:story:new:send_time"),
            reply_markup=keyboards.back(data="BackSendTimeStories"),
        )
        await state.set_state(Stories.input_send_time)
        return

    if temp[1] == "public":
        return await call.message.edit_text(
            text("manage:story:accept:public").format(
                await get_story_report_text(chosen, objects),
                (
                    f"{int(options.period / 3600)} ч."  # type: ignore
                    if options.period
                    else text("manage:post:del_time:not")
                ),
            ),
            reply_markup=keyboards.accept_public(data="AcceptStories"),
        )


@safe_handler(
    "Сторис: время удаления"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_delete_time(call: types.CallbackQuery, state: FSMContext):
    """Выбор времени автоудаления stories."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    # Lazy load post
    post_obj = data.get("post")
    if post_obj:
        from main_bot.keyboards.posting import ensure_obj

        post = ensure_obj(post_obj)
    else:
        post_id = data.get("post_id")
        if not post_id:
            await call.answer(text("keys_data_error"))
            return await call.message.delete()
        post = await db.story.get_story(post_id)
        if not post:
            await call.answer(text("story_not_found"))
            return await call.message.delete()

    story_options = StoryOptions(**post.story_options)

    delete_time = story_options.period
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if story_options.period != delete_time:
        story_options.period = delete_time
        await db.story.update_story(
            post_id=post.id,
            return_obj=False,
            story_options=story_options.model_dump(),
        )
        # В FSM post не обновляем
        # Обновим post.story_options локально для корректной работы ниже
        post.story_options = story_options.model_dump()
        data = await state.get_data()

    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
            text("story:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title,
            ),
            reply_markup=keyboards.manage_remain_story(post=post),
        )

    chosen: list = data.get("chosen")
    objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="stories"
    )

    await call.message.edit_text(
        text("manage:story:finish_params").format(
            len(chosen), await get_story_report_text(chosen, objects)
        ),
        reply_markup=keyboards.finish_params(obj=post, data="FinishStoriesParams"),
    )


@safe_handler(
    "Сторис: отмена времени отправки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def cancel_send_time(call: types.CallbackQuery, state: FSMContext):
    """Отмена ввода времени отправки."""
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    is_edit: bool = data.get("is_edit")

    # Lazy load for cancel (need post for keyboard)
    post_obj = data.get("post")
    if post_obj:
        from main_bot.keyboards.posting import ensure_obj

        post = ensure_obj(post_obj)
    else:
        post_id = data.get("post_id")
        if not post_id:
            await call.answer(text("keys_data_error"))
            return await call.message.delete()
        post = await db.story.get_story(post_id)
        if not post:
            await call.answer(text("story_not_found"))
            return await call.message.delete()

    if is_edit:
        return await call.message.edit_text(
            text("story:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title,
            ),
            reply_markup=keyboards.manage_remain_story(post=post),
        )

    chosen: list = data.get("chosen")
    objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="stories"
    )

    await call.message.edit_text(
        text("manage:story:finish_params").format(
            len(chosen), await get_story_report_text(chosen, objects)
        ),
        reply_markup=keyboards.finish_params(obj=post, data="FinishStoriesParams"),
    )


@safe_handler(
    "Сторис: время отправки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def get_send_time(message: types.Message, state: FSMContext):
    """
    Получение времени отправки от пользователя.

    Поддерживаемые форматы:
    - DD.MM.YYYY HH:MM
    - DD.MM HH:MM (текущий год)
    - HH:MM (сегодня)
    """
    input_date = message.text.strip()
    parts = input_date.split()

    try:
        if len(parts) == 2 and len(parts[0].split(".")) == 3:
            date = datetime.strptime(input_date, "%d.%m.%Y %H:%M")

        elif len(parts) == 2 and len(parts[0].split(".")) == 2:
            year = datetime.now().year
            date = datetime.strptime(f"{parts[0]}.{year} {parts[1]}", "%d.%m.%Y %H:%M")

        elif len(parts) == 1:
            today = datetime.now().strftime("%d.%m.%Y")
            date = datetime.strptime(f"{today} {parts[0]}", "%d.%m.%Y %H:%M")

        else:
            raise ValueError("Invalid format")

        send_time = time.mktime(date.timetuple())

    except Exception as e:
        logger.error(f"Ошибка парсинга времени отправки: {e}")
        return await message.answer(text("error_value"))

    if time.time() > send_time:
        return await message.answer(text("error_time_value"))

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")

    # Lazy load post
    post_obj = data.get("post")
    if post_obj:
        from main_bot.keyboards.posting import ensure_obj

        post = ensure_obj(post_obj)
    else:
        post_id = data.get("post_id")
        if not post_id:
            return await message.answer(text("keys_data_error"))
        post = await db.story.get_story(post_id)
        if not post:
            return await message.answer(text("story_not_found"))

    # Восстанавливаем options для использования ниже
    story_options = post.story_options
    if isinstance(story_options, dict):
        options = StoryOptions(**story_options)
    else:
        # Если уже объект
        options = StoryOptions(**story_options.model_dump())

    if is_edit:
        post_obj = await db.story.update_story(
            post_id=post.id, return_obj=True, send_time=send_time
        )
        send_date = datetime.fromtimestamp(post_obj.send_time)
        send_date_values = (
            send_date.day,
            text("month").get(str(send_date.month)),
            send_date.year,
        )

        await state.clear()
        # НЕ сохраняем post в state, только date values
        data["send_date_values"] = send_date_values
        await state.update_data(data)

        return await message.answer(
            text("story:content").format(
                *send_date_values,
                data.get("channel").emoji_id,
                data.get("channel").title,
            ),
            reply_markup=keyboards.manage_remain_story(post=post_obj),
        )

    weekday = text("weekdays")[str(date.weekday())]
    month = text("month")[str(date.month)]
    day = date.day
    year = date.year
    _time = date.strftime("%H:%M")
    date_values = (
        weekday,
        day,
        month,
        year,
        _time,
    )

    await state.update_data(send_time=send_time, date_values=date_values)
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    chosen: list = data.get("chosen")

    objects = await db.channel.get_user_channels(
        user_id=message.from_user.id, sort_by="stories"
    )

    await message.answer(
        text("manage:story:accept:date").format(
            weekday,
            day,
            month,
            year,
            _time,
            await get_story_report_text(chosen, objects),
            (
                f"{int(options.period / 3600)} ч."  # type: ignore
                if options.period
                else text("manage:post:del_time:not")
            ),
        ),
        reply_markup=keyboards.accept_date(data="AcceptStories"),
    )
