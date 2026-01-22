"""
Модуль выбора канала для просмотра контент-плана.

Содержит логику:
- Показ списка каналов и папок
- Навигацию по папкам
- Переключение режимов отображения (папки/все каналы)
"""

import logging
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.utils.user_settings import get_user_view_mode, set_user_view_mode
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

@safe_handler("Постинг: выбор канала для контент-плана (начало)")
async def show_selection(message: types.Message, state: FSMContext):
    """
    Точка входа: отображает выбор канала для контент-плана.
    """
    await state.clear()
    view_mode = await get_user_view_mode(message.chat.id)
    
    # Инициализируем данные в стейте
    await state.update_data(current_folder_id=None)

    # Загружаем данные для показа
    try:
            # Загружаем папки всегда, чтобы в клавиатуре был доступен переключатель вида,
            # даже если текущий режим - "все каналы".
            all_folders = await db.user_folder.get_folders(user_id=message.chat.id)
            folders_with_content = [f for f in all_folders if f.content]
        
            if view_mode == "folders":
                channels = await db.channel.get_user_channels_without_folders(user_id=message.chat.id)
                folders = folders_with_content
            else:
                channels = await db.channel.get_user_channels(user_id=message.chat.id, sort_by="posting")
                # Папки передаются в клавиатуру для отображения переключателя.
                folders = folders_with_content
        await message.answer(
            text("choice_channel:content"),
            reply_markup=keyboards.choice_channel_single(
                channels=channels,
                folders=folders,
                view_mode=view_mode
            )
        )
    except Exception as e:
        logger.error(f"Ошибка при показе выбора каналов для контент-плана: {e}", exc_info=True)
        await message.answer(text("error_loading_channels"))

@safe_handler("Постинг: выбор канала для контент-плана (callback)")
async def choice_channels(call: types.CallbackQuery, state: FSMContext):
    """
    Обработка навигации и выбора в меню каналов.
    """
    temp = call.data.split("|")
    action = temp[1] if len(temp) > 1 else None
    
    data = await state.get_data()
    current_folder_id = data.get("current_folder_id")
    view_mode = await get_user_view_mode(call.from_user.id)

    # 1. Отмена / возврат
    if action == "cancel":
        if current_folder_id:
            # Выход из папки
            await state.update_data(current_folder_id=None)
            return await update_menu(call, state, view_mode, None)
        else:
            # Возврат в меню постинга
            await call.message.delete()
            from main_bot.keyboards import keyboards
            await call.message.answer(
                text("posting_menu_text"),
                reply_markup=keyboards.posting_menu()
            )
            return

    # 2. Переключение режима (папки/каналы)
    if action == "switch_view":
        new_mode = temp[2]
        await set_user_view_mode(call.from_user.id, new_mode)
        await state.update_data(current_folder_id=None)
        return await update_menu(call, state, new_mode, None)

    # 3. Навигация (пагинация)
    if action in ["next", "back"]:
        remover = int(temp[2])
        return await update_menu(call, state, view_mode, current_folder_id, remover)

    # 4. Вход в папку или выбор канала
    target = temp[1]
    
    # Если это ID папки (метка 'folder' в конце)
    if len(temp) > 3 and temp[3] == "folder":
        folder_id = int(target)
        await state.update_data(current_folder_id=folder_id)
        return await update_menu(call, state, view_mode, folder_id)

    # Иначе это выбор канала (callback ChoiceObjectContentPost|CHAT_ID)
    # Передаем управление в основной хендлер контента
    from main_bot.handlers.user.posting.content import choice_channel
    return await choice_channel(call, state)

async def update_menu(call: types.CallbackQuery, state: FSMContext, view_mode: str, folder_id: int = None, remover: int = 0):
    """Вспомогательная функция для обновления интерфейса выбора."""
    try:
        if folder_id:
            folder = await db.user_folder.get_folder_by_id(folder_id)
            if folder and folder.content:
                channels = await db.channel.get_user_channels(
                    user_id=call.from_user.id,
                    from_array=[int(cid) for cid in folder.content]
                )
            else:
                channels = []
            folders = []
            is_inside = True
        elif view_mode == "folders":
            channels = await db.channel.get_user_channels_without_folders(user_id=call.from_user.id)
            folders = await db.user_folder.get_folders(user_id=call.from_user.id)
            folders = [f for f in folders if f.content]
            is_inside = False
        else:
            channels = await db.channel.get_user_channels(user_id=call.from_user.id, sort_by="posting")
            folders = []
            is_inside = False

        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_single(
                channels=channels,
                folders=folders,
                remover=remover,
                view_mode=view_mode,
                is_inside_folder=is_inside
            )
        )
    except Exception as e:
        logger.error(f"Ошибка при обновлении меню выбора канала: {e}")
        await call.answer(text("error_load_generic"))

def get_router():
    router = Router()
    router.callback_query.register(choice_channels, F.data.split("|")[0] == "ChoiceContentPlanChannel")
    return router
