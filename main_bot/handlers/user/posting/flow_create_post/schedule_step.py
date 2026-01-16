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
import asyncio
from datetime import datetime

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.channel.model import Channel
from main_bot.utils.message_utils import answer_post
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.keyboards.posting import ensure_obj, safe_post_from_dict
from main_bot.states.user import Posting
from utils.error_handler import safe_handler
from main_bot.utils.user_settings import get_user_view_mode, set_user_view_mode
from main_bot.utils.redis_client import redis_client
import json

logger = logging.getLogger(__name__)


@safe_handler(
    "Выбор каналов для постинга"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_channels(call: types.CallbackQuery, state: FSMContext):
    """
    Выбор каналов для публикации поста.

    Поддерживает:
    - Навигацию по папкам
    - Выбор/отмену выбора отдельных каналов
    - Выбор/отмену всех видимых каналов
    - Пагинацию списка каналов

    Производительность:
    - Параллельная загрузка каналов и папок (asyncio.gather)
    - Батчинг запросов для папок (вместо N+1)
    - Кеширование списка каналов в Redis (60 сек)

    Args:
        call: Callback query с данными действия
        state: FSM контекст
    """
    temp = call.data.split("|")
    logger.info(
        "Пользователь %s: действие выбора каналов: %s", call.from_user.id, temp[1]
    )
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    chosen: list = data.get("chosen")
    current_folder_id = data.get("current_folder_id")

    view_mode = await get_user_view_mode(call.from_user.id)

    # Переключение вида
    # Переключение вида
    # Переключение вида
    if temp[1] == "switch_view":
        # temp[2] теперь целевой режим (folders/channels)
        if len(temp) > 2:
            view_mode = temp[2]
        else:
            # Резервный вариант (не должно происходить с новыми кнопками)
            view_mode = "channels" if view_mode == "folders" else "folders"

        await set_user_view_mode(call.from_user.id, view_mode)
        if view_mode == "channels":
            await state.update_data(current_folder_id=None)
            current_folder_id = None

        pass

    # Определяем что показывать
    try:
        if current_folder_id:
            # Внутри папки - показываем содержимое папки (каналы)
            folder = await db.user_folder.get_folder_by_id(current_folder_id)
            if folder and folder.content:
                objects = await db.channel.get_user_channels(
                    user_id=call.from_user.id,
                    from_array=[int(cid) for cid in folder.content],
                )
            else:
                objects = []
            folders = []

        elif view_mode == "channels":
            # Режим "Все каналы": показываем плоский список всех каналов
            # Пытаемся получить из кеша
            cache_key = f"user_channels:{call.from_user.id}"
            cached_data = await redis_client.get(cache_key)

            if cached_data:
                try:
                    objects = [Channel(**item) for item in json.loads(cached_data)]
                    # Восстанавливаем типы
                    for obj in objects:
                        if isinstance(obj.subscribe, int):
                            pass  # уже ок
                except Exception as e:
                    logger.error(f"Ошибка десериализации кеша каналов: {e}")
                    objects = []
            else:
                objects = None

            if objects is None:
                objects = await db.channel.get_user_channels(
                    user_id=call.from_user.id, sort_by="posting", limit=500
                )
                # Кешируем
                try:
                    to_cache = [
                        {
                            "id": c.id,
                            "chat_id": c.chat_id,
                            "title": c.title,
                            "subscribe": c.subscribe,
                            "emoji_id": c.emoji_id,
                            "admin_id": c.admin_id,
                        }
                        for c in objects
                    ]
                    await redis_client.setex(cache_key, 60, json.dumps(to_cache))
                except Exception as e:
                    logger.error(f"Ошибка сериализации кеша каналов: {e}")

            folders = []

        else:  # view_mode == "folders"
            # Режим "Папки": показываем папки И каналы без папок
            objects = await db.channel.get_user_channels_without_folders(
                user_id=call.from_user.id
            )
            raw_folders = await db.user_folder.get_folders(user_id=call.from_user.id)
            folders = [f for f in raw_folders if f.content]

    except Exception as e:
        logger.error(
            "Ошибка загрузки каналов для пользователя %s: %s",
            call.from_user.id,
            str(e),
            exc_info=True,
        )
        await call.answer(
            text("error_load_channels"), show_alert=True
        )
        return
    except Exception as e:
        logger.error(
            "Ошибка загрузки каналов для пользователя %s: %s",
            call.from_user.id,
            str(e),
            exc_info=True,
        )
        await call.answer(
            text("error_load_channels"), show_alert=True
        )
        return

    # Переход к следующему шагу
    if temp[1] == "next_step":
        if not chosen:
            return await call.answer(text("error_min_choice"))

        logger.info(
            "Пользователь %s выбрал %d каналов для постинга",
            call.from_user.id,
            len(chosen),
        )

        # Сохраняем выбранные каналы
        await state.update_data(chosen=chosen)

        # Переходим к вводу контента
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await call.message.answer(
            text("input_message"), reply_markup=keyboards.cancel(data="InputPostCancel")
        )
        await state.set_state(Posting.input_message)
        return

    # Отмена / возврат назад
    if temp[1] == "cancel":
        if current_folder_id:
            # Возврат к корневому уровню
            await state.update_data(current_folder_id=None)
            # Обновляем локальную переменную
            current_folder_id = None

            # Перезагружаем данные корневого уровня
            try:
                if view_mode == "folders":
                    objects = await db.channel.get_user_channels_without_folders(
                        user_id=call.from_user.id
                    )
                    raw_folders = await db.user_folder.get_folders(
                        user_id=call.from_user.id
                    )
                    folders = [f for f in raw_folders if f.content]
                else:
                    objects, folders = await asyncio.gather(
                        db.channel.get_user_channels_without_folders(
                            user_id=call.from_user.id
                        ),
                        db.user_folder.get_folders(user_id=call.from_user.id),
                    )
                    folders = [f for f in folders if f.content]
            except Exception as e:
                logger.error(
                    "Ошибка при возврате к корневому уровню: %s", str(e), exc_info=True
                )
                await call.answer(
                    text("error_load_generic"), show_alert=True
                )
                return
            # Сбрасываем remover при выходе из папки
            remover_value = 0

            # Подтверждаем действие для снятия спиннера
            try:
                await call.answer()
            except Exception:
                pass
        else:
            # Выход - возврат в меню постинга
            from main_bot.handlers.user.menu import start_posting

            await call.message.delete()
            return await start_posting(call.message)

    # Пагинация
    if temp[1] in ["next", "back"]:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                remover=int(temp[2]),
                view_mode=view_mode,
            )
        )

    # Выбрать/отменить все видимые каналы
    if temp[1] == "choice_all":
        current_ids = [i.chat_id for i in objects]
        logger.debug(
            "Попытка выбрать все каналы: видимых=%d, выбрано=%d",
            len(objects),
            len(chosen),
        )

        # Проверяем, все ли выбраны
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
                logger.warning(
                    "Пользователь %s: попытка выбрать %d каналов без подписки",
                    call.from_user.id,
                    len(channels_without_sub),
                )
                # Показываем список каналов без подписки
                channels_list = "\n".join(
                    f"• {title}" for title in channels_without_sub
                )
                if len(channels_without_sub) > 5:
                    channels_list += f"\n... и ещё {len(channels_without_sub) - 5}"

                logger.warning(
                    f"Пользователь {call.from_user.id} заблокирован по подписке: {len(channels_without_sub)} каналов"
                )

                return await call.answer(
                    text("error_choice_all_no_sub").format(channels_list),
                    show_alert=True,
                )

            # Выбираем все видимые, НЕ удаляя уже выбранные (Merging)
            for cid in current_ids:
                if cid not in chosen:
                    chosen.append(cid)

    # Выбор канала или вход в папку
    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])
        resource_type = temp[3] if len(temp) > 3 else None

        if resource_type == "folder":
            # Вход в папку
            logger.debug(
                "Пользователь %s вошел в папку %s", call.from_user.id, resource_id
            )
            await state.update_data(current_folder_id=resource_id)
            # Обновляем локальную переменную для корректного отображения
            current_folder_id = resource_id

            # Перезагружаем данные папки (батчинг)
            try:
                folder = await db.user_folder.get_folder_by_id(resource_id)
                if folder and folder.content:
                    # Батчинг: один запрос вместо N запросов (N+1 fix)
                    objects = await db.channel.get_user_channels(
                        user_id=call.from_user.id,
                        from_array=[int(cid) for cid in folder.content],
                    )
                else:
                    objects = []
                folders = []
            except Exception as e:
                logger.error(
                    "Ошибка загрузки папки %s: %s", resource_id, str(e), exc_info=True
                )
                await call.answer(
                    "❌ Ошибка загрузки папки. Попробуйте позже.", show_alert=True
                )
                return
            # Сбрасываем remover
            if len(temp) > 2:
                temp[2] = "0"
            else:
                temp.append("0")
        else:
            # Переключение выбора канала
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                channel = await db.channel.get_channel_by_chat_id(resource_id)
                if not channel.subscribe:
                    logger.warning(
                        "Пользователь %s: попытка выбрать канал без подписки: %s",
                        call.from_user.id,
                        channel.title,
                    )
                    return await call.answer(
                        text("error_sub_channel").format(channel.title), show_alert=True
                    )
                chosen.append(resource_id)

    await state.update_data(chosen=chosen)

    # Пересчитываем список для отображения (показываем выбранные каналы)
    display_objects = await db.channel.get_user_channels(
        user_id=call.from_user.id, from_array=[int(x) for x in chosen]
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

    # Проверяем, в папке мы или нет
    folder_title = ""
    if current_folder_id:
        try:
            # Попытка найти папку в списке загруженных folders (если есть) или загружаем
            # Но folders здесь может быть пустым списком если мы внутри папки.
            # Лучше загрузить отдельно или найти эффективный способ.
            # Выше мы уже делали get_folder_by_id(current_folder_id), но переменную folder не сохранили в scope.
            # Повторный вызов get_folder_by_id - это cheap (db call).
            # Однако, в блоке "if current_folder_id:" переменная folder локальна.

            # Загружаем для отображения названия
            folder_obj = await db.user_folder.get_folder_by_id(current_folder_id)
            if folder_obj:
                folder_title = folder_obj.title
        except Exception:
            pass

    try:
        msg_text = (
            text("choice_channels:folder").format(
                folder_title, len(chosen), channels_list
            )
            if current_folder_id and folder_title
            else text("choice_channels:post").format(len(chosen), channels_list)
        )

        await call.message.edit_text(
            msg_text,
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                remover=(
                    remover_value
                    if "remover_value" in locals()
                    else (
                        int(temp[2])
                        if (
                            len(temp) > 2
                            and temp[1] in ["choice_all", "next", "back"]
                            and temp[2].isdigit()
                        )
                        or (
                            len(temp) > 2
                            and temp[1].replace("-", "").isdigit()
                            and temp[2].isdigit()
                        )  # temp[1] это id, temp[2] это remover
                        else 0
                    )
                ),
                view_mode=view_mode,
                is_inside_folder=bool(current_folder_id),
            ),
        )
    except TelegramBadRequest:
        logger.debug("Сообщение не изменено, пропускаем обновление")
        await call.answer()


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
            channels_text = "\n".join(f"• {title}" for title in invalid_channels[:5])
            if len(invalid_channels) > 5:
                channels_text += f"\n... и ещё {len(invalid_channels) - 5}"

            return await call.answer(
                text("error_cpm_perms").format(channels_text),
                show_alert=True,
            )

        await state.update_data(param=temp[1])
        await call.message.delete()
        message_text = text("manage:post:new:{}".format(temp[1]))

        input_msg = await call.message.answer(
            message_text, reply_markup=keyboards.param_cancel(param=temp[1])
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
            await db.published_post.update_published_posts_by_post_id(
                post_id=post.post_id, delete_time=delete_time
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
        return await call.message.edit_text(
            text("post:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title,
            ),
            reply_markup=keyboards.manage_remain_post(
                post=post, is_published=data.get("is_published")
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

        return await message.answer(
            text("post:content").format(
                *send_date_values,
                data.get("channel").emoji_id,
                data.get("channel").title,
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

    await message.answer(
        text("manage:post:accept:date").format(
            _time, weekday, day, month, year, channels_block, delete_str
        ),
        reply_markup=keyboards.accept_date(),
        parse_mode="HTML",
        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
    )
