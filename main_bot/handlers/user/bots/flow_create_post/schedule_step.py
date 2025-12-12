"""
Модуль настройки расписания для постов ботов.

Содержит логику:
- Настройка финальных параметров
- Выбор времени удаления
- Выбор времени отправки (с календарем)
"""
import time
import logging
from datetime import datetime, timedelta

from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.bot_post.model import BotPost
from main_bot.utils.message_utils import answer_bot_post
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.states.user import Bots

logger = logging.getLogger(__name__)
from main_bot.utils.error_handler import safe_handler


@safe_handler("Bots Finish Params")
async def finish_params(call: types.CallbackQuery, state: FSMContext):
    """Настройка финальных параметров поста для ботов."""
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: BotPost = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)

    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

    if temp[1] == 'cancel':
        await call.message.delete()
        return await answer_bot_post(call.message, state)

    if temp[1] == "report":
        post = await db.update_bot_post(
            post_id=post.id,
            return_obj=True,
            report=not post.report
        )
        await state.update_data(
            post=post
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_bot_post_params(
                obj=post
            )
        )

    if temp[1] == "text_with_name":
        post = await db.update_bot_post(
            post_id=post.id,
            return_obj=True,
            text_with_name=not post.text_with_name
        )
        await state.update_data(
            post=post
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_bot_post_params(
                obj=post
            )
        )

    if temp[1] == "delete_time":
        await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time_bot_post()
        )

    if temp[1] == "send_time":
        day = datetime.today()
        day_values = (day.day, text("month").get(str(day.month)), day.year,)

        await state.update_data(
            day=day,
            day_values=day_values
        )

        await call.message.edit_text(
            text("manage:post_bot:new:send_time"),
            reply_markup=keyboards.back(data="BackSendTimeBots")
        )
        await state.set_state(Bots.input_send_time)
        return

    if temp[1] == "public":
        return await call.message.edit_text(
            text("manage:post_bot:accept:public").format(
                "\n".join(
                    text("resource_title").format(
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
            ),
            reply_markup=keyboards.accept_bot_public(
                data="AcceptBotPost"
            )
        )


@safe_handler("Bots Choice Delete Time")
async def choice_delete_time(call: types.CallbackQuery, state: FSMContext):
    """Выбор времени автоудаления поста для ботов."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: BotPost = data.get("post")
    available: int = data.get("available")

    delete_time = post.delete_time
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if temp[1] == "off":
        delete_time = None

    if post.delete_time != delete_time:
        post = await db.update_bot_post(
            post_id=post.id,
            return_obj=True,
            delete_time=delete_time
        )
        await state.update_data(
            post=post
        )
        data = await state.get_data()

    is_edit: bool = data.get("is_edit")
    if is_edit:
        send_date_values = data.get("send_date_values")
        return await call.message.edit_text(
            text("bot_post:content").format(
                "Нет" if not post.delete_time else f"{int(post.delete_time / 3600)} час.",
                send_date_values[0],  # день
                send_date_values[1],  # месяц (уже строка)
                send_date_values[2],  # год
                (await call.bot.get_chat(post.admin_id)).username or "Unknown"
            ),
            reply_markup=keyboards.manage_remain_bot_post(
                post=post
            )
        )

    chosen: list = data.get("chosen")
    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

    await call.message.edit_text(
        text("manage:post_bot:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            available
        ),
        reply_markup=keyboards.finish_bot_post_params(
            obj=data.get('post')
        )
    )


@safe_handler("Bots Send Time Inline")
async def send_time_inline(call: types.CallbackQuery, state: FSMContext):
    """Обработка inline выбора времени отправки (календарь)."""
    data = await state.get_data()
    temp = call.data.split("|")

    if temp[1] == "cancel":
        await state.clear()
        await state.update_data(data)

        is_edit: bool = data.get("is_edit")
        if is_edit:
            return await call.message.edit_text(
                text("post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_bot_post(
                    post=data.get("post")
                )
            )

        chosen: list = data.get("chosen")
        channels = await db.get_bot_channels(call.from_user.id)
        objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

        return await call.message.edit_text(
            text("manage:post_bot:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                data.get("available")
            ),
            reply_markup=keyboards.finish_bot_post_params(
                obj=data.get('post')
            )
        )

    day: datetime = data.get("day")

    if temp[1] in ['next_day', 'next_month', 'back_day', 'back_month', "choice_day", "show_more"]:
        if temp[1] == "choice_day":
            day = datetime.strptime(temp[2], '%Y-%m-%d')
        else:
            day = day - timedelta(days=int(temp[2]))

        day_values = (day.day, text("month").get(str(day.month)), day.year,)

        await state.update_data(
            day=day,
            day_values=day_values,
        )

        return await call.message.edit_text(
            text("manage:post_bot:new:send_time"),
            reply_markup=None
        )


@safe_handler("Bots Get Send Time")
async def get_send_time(message: types.Message, state: FSMContext):
    """
    Получение времени отправки от пользователя.
    
    Поддерживаемые форматы:
    - HH:MM (только время, дата = сегодня)
    - HH:MM DD.MM (день и месяц, год = текущий)
    - DD.MM.YYYY HH:MM
    - HH:MM DD.MM.YYYY
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
        
        # Формат: HH:MM DD.MM (без года)
        elif len(parts) == 2 and ':' in parts[0] and len(parts[1].split('.')) == 2:
            year = datetime.now().year
            date = datetime.strptime(f"{parts[1]}.{year} {parts[0]}", "%d.%m.%Y %H:%M")
        
        # Формат: HH:MM (только время, используем сегодняшнюю дату)
        elif len(parts) == 1 and ':' in parts[0]:
            today = datetime.now().strftime("%d.%m.%Y")
            date = datetime.strptime(f"{today} {parts[0]}", "%d.%m.%Y %H:%M")
        
        else:
            raise ValueError("Неверный формат")

        send_time = time.mktime(date.timetuple())

    except Exception as e:
        logger.error(f"Ошибка парсинга времени отправки: {e}")
        return await message.answer(
            text("error_value")
        )

    if time.time() > send_time:
        return await message.answer(
            text("error_time_value")
        )

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")
    post: BotPost = data.get('post')
    is_changing_time = data.get("send_time") is not None  # Проверяем, меняем ли мы время

    if is_edit:
        post = await db.update_bot_post(
            post_id=post.id,
            return_obj=True,
            send_time=send_time
        )
        send_date = datetime.fromtimestamp(post.send_time)
        send_date_values = (send_date.day, text("month").get(str(send_date.month)), send_date.year,)

        await state.clear()
        data['send_date_values'] = send_date_values
        await state.update_data(data)
        
        # Получаем username автора
        try:
            author = (await message.bot.get_chat(post.admin_id)).username or "Unknown"
        except:
            author = "Unknown"

        return await message.answer(
            text("bot_post:content").format(
                "Нет" if not post.delete_time else f"{int(post.delete_time / 3600)} час.",
                send_date_values[0],  # день
                send_date_values[1],  # месяц
                send_date_values[2],  # год
                author
            ),
            reply_markup=keyboards.manage_remain_bot_post(
                post=post
            )
        )

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

    channels = await db.get_bot_channels(message.from_user.id)
    objects = await db.get_user_channels(message.from_user.id, from_array=[i.id for i in channels])

    # Если меняем время (уже было запланировано), сразу возвращаемся на экран "Готов к рассылке"
    if is_changing_time:
        await db.update_bot_post(
            post_id=post.id,
            send_time=send_time
        )
        
        return await message.answer(
            text("manage:post_bot:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                data.get("available")
            ),
            reply_markup=keyboards.finish_bot_post_params(obj=post)
        )

    # Первый раз планируем - показываем экран с кнопкой "Запланировать"
    await message.answer(
        text("manage:post_bot:accept:date").format(
            _time,
            weekday,
            day,
            month,
            year,
            "\n".join(
                text("resource_title").format(
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        ),
        reply_markup=keyboards.accept_bot_date(
            data="AcceptBotPost"
        )
    )


@safe_handler("Bots Back Send Time")
async def back_send_time(call: types.CallbackQuery, state: FSMContext):
    """Возврат с экрана ввода времени на экран финальных параметров."""
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)
    
    post: BotPost = data.get("post")
    chosen: list = data.get("chosen") or post.chat_ids  # Используем post.chat_ids если chosen None
    
    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])
    
    await call.message.edit_text(
        text("manage:post_bot:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            data.get("available") or 0  # Используем 0 если available None
        ),
        reply_markup=keyboards.finish_bot_post_params(obj=post)
    )
