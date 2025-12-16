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
from pathlib import Path

from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.story.model import Story
from main_bot.utils.message_utils import answer_story
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import StoryOptions
from main_bot.utils.session_manager import SessionManager
from main_bot.keyboards import keyboards
from main_bot.states.user import Stories
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


async def get_story_report_text(chosen, objects):
    """
    Формирование текста отчета с лимитами stories для выбранных каналов.

    Args:
        chosen: Список выбранных chat_id
        objects: Список объектов каналов

    Returns:
        str: Форматированный текст с информацией о лимитах
    """
    lines = []
    target_ids = chosen[:10]
    target_objects = [obj for obj in objects if obj.chat_id in target_ids]

    for obj in target_objects:
        posted_stories = await db.story.get_stories(obj.chat_id, datetime.now())
        posted = len(posted_stories)

        limit = 0
        if obj.session_path:
            try:
                async with SessionManager(Path(obj.session_path)) as manager:
                    limit = await manager.get_story_limit(int(obj.chat_id))
            except Exception:
                pass

        lines.append(text("resource_title").format(obj.title) + f" ({posted}/{limit})")

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


@safe_handler("Stories Choice Channels")
async def choice_channels(call: types.CallbackQuery, state: FSMContext):
    """Выбор каналов для публикации stories."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    chosen: list = data.get("chosen")
    chosen_folders: list = data.get("chosen_folders")

    objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="stories"
    )

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

    folders = await db.user_folder.get_folders(user_id=call.from_user.id)

    if temp[1] == "cancel":
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
                data="ChoiceStoriesChannels",
            )
        )

    if temp[1] == "choice_all":
        if len(chosen) == len(objects) and len(chosen_folders) == len(folders):
            chosen.clear()
            chosen_folders.clear()
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

            _ = [i.chat_id for i in objects if i.chat_id not in chosen]
            if folders:
                for folder in folders:
                    sub_channels = []
                    for chat_id in folder.content:
                        channel = await db.channel.get_channel_by_chat_id(int(chat_id))

                        if not channel.subscribe:
                            continue

                        sub_channels.append(int(chat_id))

                    if len(sub_channels) == len(folder.content):
                        chosen_folders.append(folder.id)

            chosen = list(set(chosen))

    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])

        if temp[3] == "channel":
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
                        text("error_story_session").format(channel.title), show_alert=True
                    )

                chosen.append(resource_id)
        else:
            temp_chosen, temp_chosen_folders = await set_folder_content(
                resource_id=resource_id, 
                chosen=chosen, 
                chosen_folders=chosen_folders,
                user_channels=objects # Passing already loaded channels to avoid N+1
            )
            if temp_chosen == "subscribe":
                return await call.answer(text("error_sub_channel_folder"))
            if temp_chosen == "session_path":
                return await call.answer(text("error_story_session_folder"))

    await state.update_data(chosen=chosen, chosen_folders=chosen_folders)
    await call.message.edit_text(
        text("choice_channels:story").format(
            len(chosen), await get_story_report_text(chosen, objects)
        ),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            chosen_folders=chosen_folders,
            remover=int(temp[2]),
            data="ChoiceStoriesChannels",
        ),
    )


@safe_handler("Stories Finish Params")
async def finish_params(call: types.CallbackQuery, state: FSMContext):
    """Настройка финальных параметров stories перед публикацией."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post: Story = data.get("post")
    options = StoryOptions(**post.story_options)

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
        post = await db.story.update_story(
            post_id=post.id, return_obj=True, report=not post.report
        )
        await state.update_data(post=post)
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


@safe_handler("Stories Choice Delete Time")
async def choice_delete_time(call: types.CallbackQuery, state: FSMContext):
    """Выбор времени автоудаления stories."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post: Story = data.get("post")
    story_options = StoryOptions(**post.story_options)

    delete_time = story_options.period
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if story_options.period != delete_time:
        story_options.period = delete_time
        post = await db.story.update_story(
            post_id=post.id, return_obj=True, story_options=story_options.model_dump()
        )
        await state.update_data(post=post)
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
        reply_markup=keyboards.finish_params(
            obj=data.get("post"), data="FinishStoriesParams"
        ),
    )


@safe_handler("Stories Cancel Send Time")
async def cancel_send_time(call: types.CallbackQuery, state: FSMContext):
    """Отмена ввода времени отправки."""
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
            text("story:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title,
            ),
            reply_markup=keyboards.manage_remain_story(post=data.get("post")),
        )

    chosen: list = data.get("chosen")
    objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="stories"
    )

    await call.message.edit_text(
        text("manage:story:finish_params").format(
            len(chosen), await get_story_report_text(chosen, objects)
        ),
        reply_markup=keyboards.finish_params(
            obj=data.get("post"), data="FinishStoriesParams"
        ),
    )


@safe_handler("Stories Get Send Time")
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
        logger.error(f"Error parsing send time: {e}")
        return await message.answer(text("error_value"))

    if time.time() > send_time:
        return await message.answer(text("error_time_value"))

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")
    post: Story = data.get("post")
    options = StoryOptions(**post.story_options)

    if is_edit:
        post = await db.story.update_story(
            post_id=post.id, return_obj=True, send_time=send_time
        )
        send_date = datetime.fromtimestamp(post.send_time)
        send_date_values = (
            send_date.day,
            text("month").get(str(send_date.month)),
            send_date.year,
        )

        await state.clear()
        data["send_date_values"] = send_date_values
        await state.update_data(data)

        return await message.answer(
            text("story:content").format(
                *send_date_values,
                data.get("channel").emoji_id,
                data.get("channel").title,
            ),
            reply_markup=keyboards.manage_remain_story(post=post),
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
            f"{day} {month} {year} {_time}",
            weekday,
            await get_story_report_text(chosen, objects),
            (
                f"{int(options.period / 3600)} ч."  # type: ignore
                if options.period
                else text("manage:post:del_time:not")
            ),
        ),
        reply_markup=keyboards.accept_date(data="AcceptStories"),
    )
