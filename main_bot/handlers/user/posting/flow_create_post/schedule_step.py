"""
Модуль выбора каналов, времени отправки и настройки расписания.

Содержит логику:
- Выбор каналов для публикации (с поддержкой папок)
- Настройка финальных параметров (delete_time, cpm_price, report)
- Выбор времени отправки
"""
import time
import logging
from datetime import datetime

from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.utils.message_utils import answer_post
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.states.user import Posting

logger = logging.getLogger(__name__)


async def choice_channels(call: types.CallbackQuery, state: FSMContext):
    """
    Выбор каналов для публикации поста.
    
    Поддерживает:
    - Навигацию по папкам
    - Выбор/отмену выбора отдельных каналов
    - Выбор/отмену всех видимых каналов
    - Пагинацию списка каналов
    
    Args:
        call: Callback query с данными действия
        state: FSM контекст
    """
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    chosen: list = data.get("chosen")
    current_folder_id = data.get("current_folder_id")

    # Определяем что показывать
    if current_folder_id:
        # Внутри папки
        folder = await db.get_folder_by_id(current_folder_id)
        objects = []
        if folder and folder.content:
            for chat_id in folder.content:
                channel = await db.get_channel_by_chat_id(int(chat_id))
                if channel:
                    objects.append(channel)
        folders = []
    else:
        # Корневой уровень
        objects = await db.get_user_channels_without_folders(
            user_id=call.from_user.id
        )
        folders = await db.get_folders(
            user_id=call.from_user.id
        )

    # Переход к следующему шагу
    if temp[1] == "next_step":
        if not chosen:
            return await call.answer(
                text('error_min_choice')
            )

        # Получаем все выбранные каналы для отображения
        all_chosen_objects = await db.get_user_channels(
            user_id=call.from_user.id,
            from_array=chosen
        )

        return await call.message.edit_text(
            text("manage:post:finish_params").format(
                len(chosen),
                "\\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in all_chosen_objects[:10]
                )
            ),
            reply_markup=keyboards.finish_params(
                obj=data.get('post')
            )
        )

    # Отмена / возврат назад
    if temp[1] == "cancel":
        if current_folder_id:
            # Возврат к корневому уровню
            await state.update_data(current_folder_id=None)
            # Перезагружаем данные корневого уровня
            objects = await db.get_user_channels_without_folders(
                user_id=call.from_user.id
            )
            folders = await db.get_folders(
                user_id=call.from_user.id
            )
            # Сбрасываем remover при переключении видов
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = '0'
            else:
                temp.append('0')
        else:
            # Выход
            await call.message.delete()
            return await answer_post(call.message, state)

    # Пагинация
    if temp[1] in ['next', 'back']:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                remover=int(temp[2])
            )
        )

    # Выбрать/отменить все видимые каналы
    if temp[1] == "choice_all":
        current_ids = [i.chat_id for i in objects]
        
        # Проверяем, все ли выбраны
        all_selected = all(cid in chosen for cid in current_ids)
        
        if all_selected:
            # Отменяем выбор всех видимых
            for cid in current_ids:
                if cid in chosen:
                    chosen.remove(cid)
        else:
            # Выбираем все видимые
            for cid in current_ids:
                if cid not in chosen:
                    chosen.append(cid)

    # Выбор канала или вход в папку
    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])
        resource_type = temp[3] if len(temp) > 3 else None

        if resource_type == 'folder':
            # Вход в папку
            await state.update_data(current_folder_id=resource_id)
            # Перезагружаем данные папки
            folder = await db.get_folder_by_id(resource_id)
            objects = []
            if folder and folder.content:
                for chat_id in folder.content:
                    channel = await db.get_channel_by_chat_id(int(chat_id))
                    if channel:
                        objects.append(channel)
            folders = []
            # Сбрасываем remover
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = '0'
            else:
                temp.append('0')
        else:
            # Переключение выбора канала
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                channel = await db.get_channel_by_chat_id(resource_id)
                if not channel.subscribe:
                    return await call.answer(
                        text("error_sub_channel")
                    )
                chosen.append(resource_id)

    await state.update_data(
        chosen=chosen
    )
    
    # Пересчитываем список для отображения (показываем выбранные каналы)
    display_objects = await db.get_user_channels(
        user_id=call.from_user.id,
        from_array=chosen[:10]
    )

    await call.message.edit_text(
        text("choice_channels:post").format(
            len(chosen),
            "\\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in display_objects
            )
        ),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            remover=int(temp[2]) if temp[1] in ['choice_all', 'next', 'back'] or temp[1].replace("-", "").isdigit() else 0
        )
    )


async def finish_params(call: types.CallbackQuery, state: FSMContext):
    """
    Настройка финальных параметров поста перед публикацией.
    
    Параметры:
    - cancel: возврат к выбору каналов
    - report: включение/выключение отчетов
    - cpm_price: установка цены CPM
    - delete_time: выбор времени удаления
    - send_time: выбор времени отправки
    - public: немедленная публикация
    
    Args:
        call: Callback query с данными действия
        state: FSM контекст
    """
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Post = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )

    # Возврат к выбору каналов
    if temp[1] == 'cancel':
        current_folder_id = data.get("current_folder_id")
        
        if current_folder_id:
            folder = await db.get_folder_by_id(current_folder_id)
            objects = []
            if folder and folder.content:
                for chat_id in folder.content:
                    channel = await db.get_channel_by_chat_id(int(chat_id))
                    if channel:
                        objects.append(channel)
            folders = []
        else:
            objects = await db.get_user_channels_without_folders(
                user_id=call.from_user.id
            )
            folders = await db.get_folders(
                user_id=call.from_user.id
            )

        # Пересчитываем список для отображения
        display_objects = await db.get_user_channels(
            user_id=call.from_user.id,
            from_array=chosen[:10]
        )

        return await call.message.edit_text(
            text("choice_channels:post").format(
                len(chosen),
                "\\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in display_objects
                )
            ),
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders
            )
        )

    # Переключение отчетов
    if temp[1] == "report":
        post = await db.update_post(
            post_id=post.id,
            return_obj=True,
            report=not post.report
        )
        await state.update_data(
            post=post
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_params(
                obj=post
            )
        )

    # Установка CPM цены
    if temp[1] == "cpm_price":
        if not post.delete_time:
            return await call.answer(text("error_cpm_without_timer"), show_alert=True)

        await state.update_data(
            param=temp[1]
        )
        await call.message.delete()
        message_text = text("manage:post:new:{}".format(temp[1]))
        
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
        return

    # Выбор времени удаления
    if temp[1] == "delete_time":
        await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time()
        )

    # Выбор времени отправки
    if temp[1] == "send_time":
        if post.cpm_price and not post.delete_time:
            return await call.answer(text("error_cpm_without_timer"), show_alert=True)

        await call.message.edit_text(
            text("manage:post:new:send_time"),
            reply_markup=keyboards.back(data="BackSendTimePost")
        )
        await state.set_state(Posting.input_send_time)

    # Немедленная публикация
    if temp[1] == "public":
        if post.cpm_price and not post.delete_time:
            return await call.answer(text("error_cpm_without_timer"), show_alert=True)

        await call.message.edit_text(
            text("manage:post:accept:public").format(
                "\\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                f"{int(post.delete_time / 3600)} ч."  # type: ignore
                if post.delete_time else text("manage:post:del_time:not")
            ),
            reply_markup=keyboards.accept_public()
        )


async def choice_delete_time(call: types.CallbackQuery, state: FSMContext):
    """
    Выбор времени автоудаления поста.
    
    Args:
        call: Callback query с выбранным временем
        state: FSM контекст
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Post = data.get("post")

    delete_time = post.delete_time
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if temp[1] == "off":
        delete_time = None

    # Обновляем только если значение изменилось
    if post.delete_time != delete_time:
        if data.get("is_published"):
            await db.update_published_posts_by_post_id(
                post_id=post.post_id,
                delete_time=delete_time
            )
            # Обновляем объект поста
            post = await db.get_published_post_by_id(post.id)
        else:
            post = await db.update_post(
                post_id=post.id,
                return_obj=True,
                delete_time=delete_time
            )
        
        await state.update_data(
            post=post
        )
        data = await state.get_data()

    # Если редактируем опубликованный пост
    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
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

    # Возврат к финальным параметрам
    chosen: list = data.get("chosen")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )

    await call.message.edit_text(
        text("manage:post:finish_params").format(
            len(chosen),
            "\\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        ),
        reply_markup=keyboards.finish_params(
            obj=data.get('post')
        )
    )


async def cancel_send_time(call: types.CallbackQuery, state: FSMContext):
    """
    Отмена ввода времени отправки.
    
    Args:
        call: Callback query
        state: FSM контекст
    """
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    # Если редактируем опубликованный пост
    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
            text("post:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            ),
            reply_markup=keyboards.manage_remain_post(
                post=data.get("post"),
                is_published=data.get("is_published")
            )
        )

    # Возврат к финальным параметрам
    chosen: list = data.get("chosen")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )

    await call.message.edit_text(
        text("manage:post:finish_params").format(
            len(chosen),
            "\\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        ),
        reply_markup=keyboards.finish_params(
            obj=data.get('post')
        )
    )


async def get_send_time(message: types.Message, state: FSMContext):
    """
    Получение времени отправки от пользователя.
    
    Поддерживаемые форматы:
    - HH:MM (только время, дата = сегодня)
    - DD.MM.YYYY HH:MM
    - HH:MM DD.MM.YYYY
    
    Args:
        message: Сообщение с временем отправки
        state: FSM контекст
    """
    input_date = message.text.strip()
    parts = input_date.split()

    try:
        # Формат: DD.MM.YYYY HH:MM
        if len(parts) == 2 and len(parts[0].split('.')) == 3 and ':' in parts[1]:
            date = datetime.strptime(input_date, "%d.%m.%Y %H:%M")
        
        # Формат: HH:MM DD.MM.YYYY
        elif len(parts) == 2 and ':' in parts[0] and len(parts[1].split('.')) == 3:
            date = datetime.strptime(f"{parts[1]} {parts[0]}", "%d.%m.%Y %H:%M")
        
        # Формат: HH:MM (только время, используем сегодняшнюю дату)
        elif len(parts) == 1 and ':' in parts[0]:
            today = datetime.now().strftime("%d.%m.%Y")
            date = datetime.strptime(f"{today} {parts[0]}", "%d.%m.%Y %H:%M")
        
        else:
            raise ValueError("Invalid format")

        send_time = time.mktime(date.timetuple())

    except Exception as e:
        print(e)
        return await message.answer(
            text("error_value")
        )

    # Проверка что время в будущем
    if time.time() > send_time:
        return await message.answer(
            text("error_time_value")
        )

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")
    post: Post = data.get('post')

    # Если редактируем опубликованный пост
    if is_edit:
        post = await db.update_post(
            post_id=post.id,
            return_obj=True,
            send_time=send_time
        )
        send_date = datetime.fromtimestamp(post.send_time)
        send_date_values = (send_date.day, text("month").get(str(send_date.month)), send_date.year,)

        await state.clear()
        data['send_date_values'] = send_date_values
        await state.update_data(data)

        return await message.answer(
            text("post:content").format(
                *send_date_values,
                data.get("channel").emoji_id,
                data.get("channel").title
            ),
            reply_markup=keyboards.manage_remain_post(
                post=post
            )
        )

    # Форматируем дату для отображения
    weekday = text("weekdays")[str(date.weekday())]
    month = text("month")[str(date.month)]
    day = date.day
    year = date.year
    _time = date.strftime('%H:%M')
    date_values = (weekday, day, month, year, _time,)

    await state.update_data(
        send_time=send_time,
        date_values=date_values
    )
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    chosen: list = data.get('chosen')

    objects = await db.get_user_channels(
        user_id=message.from_user.id,
        sort_by="posting"
    )

    await message.answer(
        text("manage:post:accept:date").format(
            *date_values,
            "\\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            f"{int(post.delete_time / 3600)} ч."  # type: ignore
            if post.delete_time else text("manage:post:del_time:not")
        ),
        reply_markup=keyboards.accept_date()
    )
