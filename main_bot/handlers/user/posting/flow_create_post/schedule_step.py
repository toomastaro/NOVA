"""
Модуль выбора каналов, времени отправки и настройки расписания.

Содержит логику:
- Выбор каналов для публикации (с поддержкой папок)
- Настройка финальных параметров (delete_time, cpm_price, report)
- Выбор времени отправки
"""

import time
import logging
import html
from datetime import datetime

from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.utils.message_utils import answer_post
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.keyboards.posting import ensure_obj, safe_post_from_dict
from main_bot.states.user import Posting
from config import Config
from instance_bot import bot as main_bot
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler(
    "Финальные параметры постинга"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post = safe_post_from_dict(data.get("post"))
    if not post:
        await call.answer(text("error_post_not_found"))
        return await call.message.delete()
    chosen: list = data.get("chosen", post.chat_ids)
    # objects = await db.channel.get_user_channels(
    #     user_id=call.from_user.id, sort_by="posting"
    # )

    # Возврат к редактированию поста
    if temp[1] == "cancel":
        # Показываем превью поста с возможностью редактирования
        await call.message.delete()
        await answer_post(call.message, state)
        return

    # Переключение отчетов
    if temp[1] == "report":
        # Логика удалена, так как кнопка убрана из интерфейса
        pass
        return

    # Установка CPM цены
    if temp[1] == "cpm_price":
        # Проверка прав у выбранных каналов для CPM (требуется помощник)
        invalid_channels = []
        # chosen может быть не в data, если это редактирование, берем из post.chat_ids
        target_channels = data.get("chosen") or post.chat_ids

        for chat_id in target_channels:
            channel = await db.channel.get_channel_by_chat_id(int(chat_id))
            if not channel:
                continue

            client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)
            has_perms = False
            if client_row and client_row[0].is_admin:
                has_perms = True

            if not has_perms:
                invalid_channels.append(channel.title)

        if invalid_channels:
            limit_show = 50
            channels_text = "\n".join(
                f"• {title}" for title in invalid_channels[:limit_show]
            )
            if len(invalid_channels) > limit_show:
                channels_text += f"\n... и ещё {len(invalid_channels) - limit_show}"

            logger.warning(
                f"У пользователя {call.from_user.id} нет прав помощника для CPM в каналах:\n{channels_text}"
            )

            # Отправка алерта админам
            if Config.ADMIN_SUPPORT:
                try:
                    alert_text = (
                        f"⚠️ <b>Внимание: Отсутствие прав помощника</b>\n\n"
                        f"Пользователь <a href='tg://user?id={call.from_user.id}'>{call.from_user.id}</a> "
                        f"пытается установить CPM, но помощник не имеет прав в каналах:\n"
                        f"<blockquote>{html.escape(channels_text)}</blockquote>\n"
                        f"<i>Рекомендуется проверить права помощников для корректного сбора статистики.</i>"
                    )
                    await main_bot.send_message(
                        chat_id=Config.ADMIN_SUPPORT, text=alert_text, parse_mode="HTML"
                    )
                except Exception as alert_err:
                    logger.error(f"Не удалось отправить алерт админам: {alert_err}")

        await state.update_data(param=temp[1])
        await call.message.delete()
        message_text = text("manage:post:new:{}".format(temp[1]))

        input_msg = await call.message.answer(
            message_text, reply_markup=keyboards.param_cpm_input(param=temp[1])
        )
        await state.set_state(Posting.input_value)
        await state.update_data(input_msg_id=input_msg.message_id)
        return

    # Выбор времени удаления
    if temp[1] == "delete_time":
        return await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time(),
        )

    # Выбор времени отправки
    if temp[1] == "send_time":
        await call.message.delete()
        await call.message.answer(
            text("manage:post:new:send_time"),
            reply_markup=keyboards.back(data="BackSendTimePost"),
        )
        await state.set_state(Posting.input_send_time)
        return

    # Немедленная публикация
    if temp[1] == "public":
        display_objects = await db.channel.get_user_channels(
            user_id=call.from_user.id, from_array=chosen
        )

        channels_str = "\n".join(
            text("resource_title").format(html.escape(obj.title))
            for obj in display_objects
        )
        channels_block = f"<blockquote expandable>{channels_str}</blockquote>"

        delete_str = text("manage:post:del_time:not")
        if post.delete_time:
            if post.delete_time < 3600:
                delete_str = f"{int(post.delete_time / 60)} мин."
            else:
                delete_str = f"{int(post.delete_time / 3600)} ч."

        await call.message.delete()

        # Force refresh main menu
        from main_bot.keyboards.common import Reply

        await call.message.answer(text("publishing_msg"), reply_markup=Reply.menu())

        await call.message.answer(
            text("manage:post:accept:public").format(channels_block, delete_str),
            reply_markup=keyboards.accept_public(),
            parse_mode="HTML",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
        return


@safe_handler(
    "Выбор времени удаления"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post = safe_post_from_dict(data.get("post"))

    delete_time = post.delete_time
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if temp[1] == "off":
        delete_time = None

    # Обновляем только если значение изменилось
    if post.delete_time != delete_time:
        if data.get("is_published"):
            # Для опубликованных постов в БД хранится абсолютное время удаления
            abs_delete_time = (
                post.created_timestamp + delete_time if delete_time else None
            )
            await db.published_post.update_published_posts_by_post_id(
                post_id=post.post_id, delete_time=abs_delete_time
            )
            # Обновляем объект поста
            post = await db.published_post.get_published_post_by_id(post.id)
        else:
            post = await db.post.update_post(
                post_id=post.id, return_obj=True, delete_time=delete_time
            )

        post_dict = {
            col.name: getattr(post, col.name) for col in post.__table__.columns
        }
        await state.update_data(post=post_dict)
        data = await state.get_data()

    # Если редактируем опубликованный пост
    is_edit: bool = data.get("is_edit")
    if is_edit:
        # Для опубликованных постов используем правильный формат текста
        if data.get("is_published"):
            from main_bot.handlers.user.posting.content import generate_post_info_text

            info_text = await generate_post_info_text(post, is_published=True)
            return await call.message.edit_text(
                info_text,
                reply_markup=keyboards.manage_remain_post(post=post, is_published=True),
            )
        else:
            # Для запланированных постов используем стандартный формат
            return await call.message.edit_text(
                text("post:content").format(
                    *data.get("send_date_values"),
                    ensure_obj(data.get("channel")).emoji_id,
                    ensure_obj(data.get("channel")).title,
                ),
                reply_markup=keyboards.manage_remain_post(
                    post=post, is_published=False
                ),
            )

    # Возврат к финальным параметрам
    chosen: list = data.get("chosen")
    objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="posting"
    )

    await call.message.edit_text(
        text("manage:post:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(obj.title)
                for obj in objects
                if obj.chat_id in chosen
            ),
        ),
        reply_markup=keyboards.finish_params(obj=safe_post_from_dict(data.get("post"))),
    )


@safe_handler(
    "Отмена ввода времени"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
                data.get("channel").title,
            ),
            reply_markup=keyboards.manage_remain_post(
                post=ensure_obj(data.get("post")), is_published=data.get("is_published")
            ),
        )

    # Возврат к финальным параметрам
    chosen: list = data.get("chosen")
    objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="posting"
    )

    await call.message.edit_text(
        text("manage:post:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(obj.title)
                for obj in objects
                if obj.chat_id in chosen
            ),
        ),
        reply_markup=keyboards.finish_params(obj=safe_post_from_dict(data.get("post"))),
    )


@safe_handler(
    "Получение времени отправки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
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
        if len(parts) == 2 and len(parts[0].split(".")) == 3 and ":" in parts[1]:
            date = datetime.strptime(input_date, "%d.%m.%Y %H:%M")

        # Формат: HH:MM DD.MM.YYYY
        elif len(parts) == 2 and ":" in parts[0] and len(parts[1].split(".")) == 3:
            date = datetime.strptime(f"{parts[1]} {parts[0]}", "%d.%m.%Y %H:%M")

        # Формат: HH:MM (только время, используем сегодняшнюю дату)
        elif len(parts) == 1 and ":" in parts[0]:
            today = datetime.now().strftime("%d.%m.%Y")
            date = datetime.strptime(f"{today} {parts[0]}", "%d.%m.%Y %H:%M")

        else:
            raise ValueError(text("error_format"))

        send_time = time.mktime(date.timetuple())

    except Exception as e:
        logger.error("Ошибка парсинга времени отправки: %s", str(e), exc_info=True)
        return await message.answer(text("error_value"))

    # Проверка что время в будущем
    if time.time() > send_time:
        return await message.answer(text("error_time_value"))

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")
    post: Post = safe_post_from_dict(data.get("post"))

    # Если редактируем опубликованный пост
    if is_edit:
        post = await db.post.update_post(
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

        channel = ensure_obj(data.get("channel"))
        return await message.answer(
            text("post:content").format(
                *send_date_values,
                channel.emoji_id,
                channel.title,
            ),
            reply_markup=keyboards.manage_remain_post(post=post),
        )

    # Форматируем дату для отображения
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

    display_objects = await db.channel.get_user_channels(
        user_id=message.from_user.id, from_array=chosen
    )

    channels_str = "\n".join(
        text("resource_title").format(html.escape(obj.title)) for obj in display_objects
    )
    channels_block = f"<blockquote expandable>{channels_str}</blockquote>"

    delete_str = text("manage:post:del_time:not")
    if post.delete_time:
        if post.delete_time < 3600:
            delete_str = f"{int(post.delete_time / 60)} {text('minutes_short')}"
        else:
            delete_str = f"{int(post.delete_time / 3600)} {text('hours_short')}"

    from main_bot.keyboards.common import Reply

    await message.answer(text("time_accepted"), reply_markup=Reply.menu())

    full_date_str = f"{_time}, {date.strftime('%d.%m.%Y')}"

    await message.answer(
        text("manage:post:accept:date").format(
            full_date_str, channels_block, delete_str
        ),
        reply_markup=keyboards.accept_date(),
        parse_mode="HTML",
        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
    )
