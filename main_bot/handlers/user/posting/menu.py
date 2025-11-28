import time
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.types import FolderType
from main_bot.keyboards.keyboards import keyboards
from main_bot.states.user import Posting
from main_bot.utils.lang.language import text


async def choice(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    temp = call.data.split("|")

    menu = {
        "create_post": {
            "cor": show_create_post,
            "args": (
                call.message,
                state,
            ),
        },
        "channels": {"cor": show_settings, "args": (call.message,)},
        "content_plan": {"cor": show_content, "args": (call.message,)},
    }

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


async def show_create_post(message: types.Message, state: FSMContext):
    """
    Обновленное меню создания поста с улучшенным выбором каналов и папок
    """
    user_id = message.chat.id

    # Получаем все каналы и папки
    channels = await db.get_user_channels(user_id=user_id, sort_by="subscribe")
    folders = await db.get_folders(user_id=user_id, folder_type=FolderType.CHANNEL)

    if not channels:
        await message.answer(text("not_found_channels"))
        return

    # Определяем каналы, которые уже есть в папках
    folder_channel_ids = set()
    for folder in folders:
        # folder.content - это список строк (chat_id каналов)
        for chat_id_str in folder.content:
            if chat_id_str.lstrip('-').isdigit():  # Проверка на число (может быть отрицательным)
                folder_channel_ids.add(int(chat_id_str))

    # Каналы для корневого отображения (те, которых нет ни в одной папке)
    root_channels = [c for c in channels if c.chat_id not in folder_channel_ids]

    # Инициализируем состояние
    await state.update_data(chosen=[], current_folder_id=None)
    
    await message.answer(
        text("choice_channels:post_new").format(
            len(channels),
            "📁 " + ", ".join(f.title for f in folders[:3]) + ("..." if len(folders) > 3 else "") if folders else "Нет папок"
        ),
        reply_markup=keyboards.choice_channels_for_post(
            channels=root_channels,
            folders=folders,
            chosen=[],
            is_folder_view=False
        )
    )
    await state.set_state(Posting.choice_channel)


async def process_choice_channel(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик выбора каналов с поддержкой папок и batch-операций
    """
    data = call.data.split("|")
    action = data[1]
    user_id = call.message.chat.id
    
    state_data = await state.get_data()
    chosen = state_data.get("chosen", [])
    current_folder_id = state_data.get("current_folder_id")

    # Получаем актуальные данные
    all_channels = await db.get_user_channels(user_id=user_id, sort_by="subscribe")
    all_folders = await db.get_folders(user_id=user_id, folder_type=FolderType.CHANNEL)

    def get_current_view_objects():
        """Получаем текущие объекты для отображения"""
        if current_folder_id:
            # Показываем содержимое конкретной папки
            folder = next((f for f in all_folders if f.id == current_folder_id), None)
            if not folder:
                return [], []  # Папка удалена

            folder_content_ids = [int(x) for x in folder.content if x.lstrip('-').isdigit()]
            folder_channels = [c for c in all_channels if c.chat_id in folder_content_ids]
            return [], folder_channels
        else:
            # Показываем корневое меню: папки + каналы не в папках
            folder_channel_ids = set()
            for f in all_folders:
                for chat_id in f.content:
                    if chat_id.lstrip('-').isdigit():
                        folder_channel_ids.add(int(chat_id))
            root_channels = [c for c in all_channels if c.chat_id not in folder_channel_ids]
            return all_folders, root_channels

    current_folders, current_channels = get_current_view_objects()

    if action == "cancel":
        if current_folder_id:
            # Выход из папки в корень
            await state.update_data(current_folder_id=None)

            folder_channel_ids = set()
            for f in all_folders:
                for chat_id in f.content:
                    if chat_id.lstrip('-').isdigit():
                        folder_channel_ids.add(int(chat_id))
            root_channels = [c for c in all_channels if c.chat_id not in folder_channel_ids]
            
            await call.message.edit_text(
                text=text("choice_channels:post_new").format(
                    len(all_channels),
                    "📁 " + ", ".join(f.title for f in all_folders[:3]) + ("..." if len(all_folders) > 3 else "") if all_folders else "Нет папок"
                ),
                reply_markup=keyboards.choice_channels_for_post(
                    channels=root_channels,
                    folders=all_folders,
                    chosen=chosen,
                    is_folder_view=False
                )
            )
            return
        else:
            # Отмена создания поста
            await state.clear()
            await call.message.delete()
            await call.message.answer(
                text("reply_menu:posting"), reply_markup=keyboards.posting_menu()
            )
            return

    if action == "folder":
        # Вход в папку
        folder_id = int(data[2])
        await state.update_data(current_folder_id=folder_id)
        
        folder = next((f for f in all_folders if f.id == folder_id), None)
        if folder:
            folder_content_ids = [int(x) for x in folder.content if x.lstrip('-').isdigit()]
            folder_channels = [c for c in all_channels if c.chat_id in folder_content_ids]
            
            await call.message.edit_text(
                text=text("choice_channels:folder").format(folder.title, len(folder_channels)),
                reply_markup=keyboards.choice_channels_for_post(
                    channels=folder_channels,
                    folders=[],
                    chosen=chosen,
                    is_folder_view=True
                )
            )
        return

    if action == "channel":
        # Переключение выбора канала
        channel_id = int(data[2])

        # Проверяем субскрипцию
        channel = next((c for c in all_channels if c.chat_id == channel_id), None)
        if channel and not channel.subscribe:
            await call.answer(text("error_sub_channel"), show_alert=True)
            return

        if channel_id in chosen:
            chosen.remove(channel_id)
        else:
            chosen.append(channel_id)
        
        await state.update_data(chosen=chosen)
        
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channels_for_post(
                channels=current_channels,
                folders=current_folders,
                chosen=chosen,
                is_folder_view=bool(current_folder_id)
            )
        )
        return

    if action == "choice_all":
        # Выбор/снятие всех каналов с подпиской
        subscribed_channels = [c.chat_id for c in all_channels if c.subscribe]

        if set(subscribed_channels).issubset(set(chosen)):
            # Убираем выделение со всех
            chosen = []
        else:
            # Выбираем все доступные
            chosen = list(set(chosen) | set(subscribed_channels))

        await state.update_data(chosen=chosen)
        
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channels_for_post(
                channels=current_channels,
                folders=current_folders,
                chosen=chosen,
                is_folder_view=bool(current_folder_id)
            )
        )
        return

    if action == "confirm":
        # Подтверждение выбора и переход к созданию поста
        if not chosen:
             await call.answer(text("error_min_choice"), show_alert=True)
             return

        # Сохраняем список выбранных каналов для пакетной отправки
        await state.update_data(chosen_channels=chosen)

        # Показываем сводку выбранных каналов
        selected_channels = [c for c in all_channels if c.chat_id in chosen]
        summary_text = text("batch_summary").format(
            len(chosen),
            "\n".join(f"• {c.title}" for c in selected_channels[:10]),
            "..." if len(chosen) > 10 else ""
        )

        await call.message.delete()
        await call.message.answer(
            summary_text + "\n\n" + text("input_message"),
            reply_markup=keyboards.cancel(data="InputPostCancel")
        )
        await state.set_state(Posting.input_message)
        return

    if action in ["next", "back"]:
        # Навигация по страницам
        remover = int(data[2])
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channels_for_post(
                channels=current_channels,
                folders=current_folders,
                chosen=chosen,
                remover=remover,
                is_folder_view=bool(current_folder_id)
            )
        )
        return


async def show_settings(message: types.Message):
    channels = await db.get_user_channels(user_id=message.chat.id, sort_by="posting")
    await message.answer(
        text("channels_text"), reply_markup=keyboards.channels(channels=channels)
    )


async def show_content(message: types.Message):
    channels = await db.get_user_channels(user_id=message.chat.id)
    await message.answer(
        text("choice_channel:content"),
        reply_markup=keyboards.choice_object_content(channels=channels),
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuPosting")
    router.callback_query.register(process_choice_channel, Posting.choice_channel, F.data.startswith("ChoiceChannelPost"))
    return router
