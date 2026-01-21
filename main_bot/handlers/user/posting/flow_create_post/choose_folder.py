"""
Модуль выбора каналов для постинга.

Содержит логику:
- Выбор каналов для публикации (с поддержкой папок)
- Навигацию по папкам
- Пагинацию списка каналов
"""

import json
import logging
import asyncio

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.channel.model import Channel
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.states.user import Posting
from utils.error_handler import safe_handler
from main_bot.utils.user_settings import get_user_view_mode, set_user_view_mode
from main_bot.utils.redis_client import redis_client

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
        await call.answer(text("error_load_channels"), show_alert=True)
        return
    except Exception as e:
        logger.error(
            "Ошибка загрузки каналов для пользователя %s: %s",
            call.from_user.id,
            str(e),
            exc_info=True,
        )
        await call.answer(text("error_load_channels"), show_alert=True)
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
                await call.answer(text("error_load_generic"), show_alert=True)
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
            folder_obj = await db.user_folder.get_folder_by_id(current_folder_id)
            if folder_obj:
                folder_title = folder_obj.title
        except Exception:
            pass

    # Вычисляем выбранные папки для индикации
    chosen_folders = []
    if folders and chosen:
        # Получаем все каналы пользователя для маппинга chat_id -> id
        user_channels = await db.channel.get_user_channels(user_id=call.from_user.id)
        chat_id_to_db_id = {c.chat_id: str(c.id) for c in user_channels}
        
        # Строковые ID выбранных каналов в базе
        chosen_db_ids = {chat_id_to_db_id.get(cid) for cid in chosen if chat_id_to_db_id.get(cid)}
        
        for folder in folders:
            if folder.content:
                # Если хотя бы один канал из папки есть в списке выбранных
                if any(str(cid) in chosen_db_ids for cid in folder.content):
                    chosen_folders.append(folder.id)

    msg_text = (
        text("choice_channels:folder").format(
            folder_title, len(chosen), channels_list
        )
        if current_folder_id and folder_title
        else text("choice_channels:post").format(len(chosen), channels_list)
    )

    try:
        await call.message.edit_text(
            msg_text,
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                chosen_folders=chosen_folders,
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
