"""
Модуль выбора ботов для публикации поста.

Реализует:
- Выбор ботов (каналов)
- Поддержку папок с каналами
- Статистику охвата (доступные пользователи)
- Навигацию по папкам
"""
import logging
from typing import List, Tuple, Union

from aiogram import types
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.db import db
from main_bot.handlers.user.menu import start_bots
from main_bot.handlers.user.bots.menu import show_create_post
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.utils.user_settings import get_user_view_mode, set_user_view_mode
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


async def set_folder_content(
    resource_id: int, chosen: List[int], chosen_folders: List[int]
) -> Tuple[Union[List[int], str], Union[List[int], str]]:
    """
    Управление выбором содержимого папки.
    Добавляет или удаляет каналы папки из списка выбранных.

    Аргументы:
        resource_id (int): ID папки.
        chosen (List[int]): Список выбранных каналов.
        chosen_folders (List[int]): Список выбранных папок.

    Возвращает:
        Tuple: (обновленный список chosen, обновленный список chosen_folders)
               или ("subscribe", "") если не оплачена подписка.
    """
    folder = await db.user_folder.get_folder_by_id(folder_id=resource_id)
    is_append = resource_id not in chosen_folders

    if is_append:
        chosen_folders.append(resource_id)
    else:
        chosen_folders.remove(resource_id)

    for chat_id in folder.content:
        chat_id = int(chat_id)

        channel = await db.channel.get_channel_by_chat_id(chat_id)
        if not channel.subscribe:
            return "subscribe", ""

        if is_append:
            if chat_id in chosen:
                continue
            chosen.append(chat_id)
        else:
            if chat_id not in chosen:
                continue
            chosen.remove(chat_id)

    return chosen, chosen_folders


@safe_handler("Bots Choice Bots")
async def choice_bots(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик меню выбора ботов для постинга.
    Поддерживает режимы просмотра (список/папки), навигацию внутри папок,
    выбор "всех", и отображение статистики доступных получателей.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    chosen: list = data.get("chosen")
    chosen_folders: list = data.get("chosen_folders")
    current_folder_id = data.get("current_folder_id")

    channels = await db.channel_bot_settings.get_bot_channels(call.from_user.id)

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
                call.from_user.id, from_array=[int(cid) for cid in folder.content]
            )
        else:
            objects = []
        folders = []
    elif view_mode == "channels":
        objects = await db.channel.get_user_channels(
            call.from_user.id, from_array=[i.id for i in channels]
        )
        folders = []
    else:
        # В режиме папок верхнего уровня не показываем каналы
        objects = []
        raw_folders = await db.user_folder.get_folders(
            user_id=call.from_user.id,
        )
        bound_ids = {i.id for i in channels}
        folders = [
            f
            for f in raw_folders
            if f.content and any(int(cid) in bound_ids for cid in f.content)
        ]

    if temp[1] == "next_step":
        if not chosen:
            await call.answer(text("error_min_choice"))
            return

        # Strict validation of subscriptions
        for chat_id in chosen:
            user_bot = await db.channel.get_channel_by_chat_id(chat_id)
            if not user_bot or not user_bot.subscribe:
                await call.answer(
                    text("error_sub_channel:bots").format(
                        user_bot.title if user_bot else "Unknown"
                    ),
                    show_alert=True,
                )
                return

        await call.message.delete()
        await show_create_post(call.message, state)
        return

    if temp[1] == "cancel":
        if current_folder_id:
            # Возврат к корневому уровню (Закрыть папку)
            await state.update_data(current_folder_id=None)
            current_folder_id = None

            # Перезагружаем корневые данные
            if view_mode == "folders":
                objects = []
                folders = await db.user_folder.get_folders(user_id=call.from_user.id)
            else:
                objects = await db.channel.get_user_channels(
                    call.from_user.id, from_array=[i.id for i in channels]
                )
                folders = []

            remover_value = 0
            try:
                await call.answer()
            except Exception:
                pass
        else:
            # Выход в главное меню ботов
            await call.message.delete()
            await start_bots(call.message)
            return

    if temp[1] in ["next", "back"]:
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                chosen_folders=chosen_folders,
                remover=int(temp[2]),
                data="ChoicePostBots",
                view_mode=view_mode,
                is_inside_folder=bool(current_folder_id),
            )
        )
        return

    if temp[1] == "choice_all":
        current_ids = [i.chat_id for i in objects]

        # Проверяем все ли выбраны в текущем отображении
        all_selected = all(cid in chosen for cid in current_ids)

        if all_selected:
            # Снимаем выделение
            for cid in current_ids:
                if cid in chosen:
                    chosen.remove(cid)
        else:
            # Проверяем подписку для всех ботов
            bots_without_sub = []
            for obj in objects:
                if not obj.subscribe:
                    bots_without_sub.append(obj.title)

            if bots_without_sub:
                # Показываем список ботов без подписки
                bots_list = "\n".join(f"• {title}" for title in bots_without_sub[:5])
                if len(bots_without_sub) > 5:
                    bots_list += f"\n... и ещё {len(bots_without_sub) - 5}"

                await call.answer(
                    f"❌ Невозможно выбрать всех ботов\n\n"
                    f"Следующие боты не имеют активной подписки:\n{bots_list}\n\n"
                    f"Оплатите подписку через меню 💎 Подписка",
                    show_alert=True,
                )
                return

            # Выбираем все видимые
            for cid in current_ids:
                if cid not in chosen:
                    chosen.append(cid)

            # Если были папки (только на верхнем уровне в режиме папок), выбираем их тоже
            if folders:
                for folder in folders:
                    sub_channels = []
                    for chat_id in folder.content:
                        user_bot = await db.channel.get_channel_by_chat_id(int(chat_id))

                        if not user_bot.subscribe:
                            continue

                        sub_channels.append(int(chat_id))

                    if len(sub_channels) == len(folder.content):
                        chosen_folders.append(folder.id)

            chosen = list(set(chosen))

    logger.info(f"Коллбэк выбора ботов: {temp}")

    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])
        logger.info(f"Обработка resource_id: {resource_id}")
        resource_type = temp[3] if len(temp) > 3 else None

        if resource_type == "folder":
            # Вход в папку
            await state.update_data(current_folder_id=resource_id)
            current_folder_id = resource_id

            # Загружаем содержимое
            folder = await db.user_folder.get_folder_by_id(resource_id)
            if folder and folder.content:
                objects = await db.channel.get_user_channels(
                    call.from_user.id, from_array=[int(cid) for cid in folder.content]
                )
            else:
                objects = []
            folders = []

            # Сброс пагинации
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = "0"
            else:
                temp.append("0")

        elif temp[3] == "channel" or not resource_type:
            if resource_id in chosen:
                chosen.remove(resource_id)
                logger.info(f"Удален канал {resource_id} из выбранных")
            else:
                user_bot = await db.channel.get_channel_by_chat_id(resource_id)
                logger.info(
                    f"Проверка подписки для канала {resource_id}: {user_bot.subscribe if user_bot else 'Не найден'}"
                )
                if not user_bot.subscribe:
                    logger.warning(f"У канала {resource_id} нет подписки")
                    await call.answer(
                        text("error_sub_channel:bots").format(user_bot.title),
                        show_alert=True,
                    )
                    return

                chosen.append(resource_id)
                logger.info(f"Добавлен канал {resource_id} в выбранные")

    # Recalculate stats
    all_settings = await db.channel_bot_settings.get_bot_channels(call.from_user.id)
    selected_settings = [s for s in all_settings if s.id in chosen]
    unique_bot_ids = list(set(s.bot_id for s in selected_settings if s.bot_id))

    logger.info(f"Выбраны уникальные боты: {unique_bot_ids}")

    total_users = 0
    active_users = 0

    for bot_id in unique_bot_ids:
        user_bot = await db.user_bot.get_bot_by_id(bot_id)
        if not user_bot:
            continue

        other_db = Database()
        other_db.schema = user_bot.schema
        stats = await other_db.get_count_users()
        logger.info(f"Статистика для бота {bot_id}: {stats}")
        total_users += stats.get("total", 0)
        active_users += stats.get("active", 0)

    unavailable = total_users - active_users
    available = active_users

    logger.info(
        f"Финальная статистика - Доступно: {available}, Недоступно: {unavailable}"
    )

    await state.update_data(
        chosen=chosen, chosen_folders=chosen_folders, available=available
    )

    logger.info("Обновление UI с новой статистикой")

    folder_title = ""
    if current_folder_id:
        try:
            folder_obj = await db.user_folder.get_folder_by_id(current_folder_id)
            if folder_obj:
                folder_title = folder_obj.title
        except Exception:
            pass

    list_text = (
        "\n".join(
            text("resource_title").format(obj.title)
            for obj in objects
            if obj.chat_id in chosen[:10]
        )
        if chosen
        else ""
    )

    if current_folder_id and folder_title:
        msg_text = (
            f"📂 <b>Папка: {folder_title}</b>\n\n"
            + text("choice_bots:post").format(len(chosen), list_text, available)
        )
    else:
        msg_text = text("choice_bots:post").format(len(chosen), list_text, available)

    await call.message.edit_text(
        msg_text,
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            chosen_folders=chosen_folders,
            remover=(
                remover_value if "remover_value" in locals() else int(temp[2])
            ),
            data="ChoicePostBots",
            view_mode=view_mode,
            is_inside_folder=bool(current_folder_id),
        ),
    )
