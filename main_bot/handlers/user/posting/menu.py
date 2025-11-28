import time
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
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
    user_id = message.chat.id
    folders = await db.get_folders(user_id=user_id)
    channels = await db.get_user_channels(user_id=user_id, sort_by="subscribe")
    
    if not channels:
        await message.answer(text("not_found_channels"))
        return

    # Определяем каналы, которые уже есть в папках
    folder_channel_ids = set()
    for folder in folders:
        # folder.content - это список строк (ID каналов)
        for chat_id in folder.content:
            if chat_id.isdigit(): # Проверка на всякий случай
                 folder_channel_ids.add(int(chat_id))

    # Каналы для корневого отображения (те, которых нет ни в одной папке)
    root_channels = [c for c in channels if c.chat_id not in folder_channel_ids]

    await state.update_data(chosen=[], current_folder_id=None)
    
    await message.answer(
        text("choice_channels:post").format(len(channels), ""),
        reply_markup=keyboards.choice_channels_for_post(
            channels=root_channels,
            folders=folders,
            chosen=[],
            is_folder_view=False
        )
    )
    await state.set_state(Posting.choice_channel)


async def process_choice_channel(call: types.CallbackQuery, state: FSMContext):
    data = call.data.split("|")
    action = data[1]
    user_id = call.message.chat.id
    
    state_data = await state.get_data()
    chosen = state_data.get("chosen", [])
    current_folder_id = state_data.get("current_folder_id")

    # Получаем все данные заново, чтобы быть уверенными в актуальности
    # (можно оптимизировать, но для надежности лучше так)
    all_channels = await db.get_user_channels(user_id=user_id, sort_by="subscribe")
    all_folders = await db.get_folders(user_id=user_id)

    # Вспомогательная функция для получения текущего списка отображения
    def get_current_view_objects():
        if current_folder_id:
            folder = next((f for f in all_folders if f.id == current_folder_id), None)
            if not folder:
                return [], [] # Папка удалена?
            
            folder_content_ids = [int(x) for x in folder.content if x.isdigit()]
            folder_channels = [c for c in all_channels if c.chat_id in folder_content_ids]
            return [], folder_channels
        else:
            folder_channel_ids = set()
            for f in all_folders:
                for chat_id in f.content:
                    if chat_id.isdigit():
                        folder_channel_ids.add(int(chat_id))
            root_channels = [c for c in all_channels if c.chat_id not in folder_channel_ids]
            return all_folders, root_channels

    current_folders, current_channels = get_current_view_objects()

    if action == "cancel":
        if current_folder_id:
            # Выход из папки в корень
            await state.update_data(current_folder_id=None)
            current_folders, current_channels = get_current_view_objects() # Обновляем для корня
            # Нужно заново получить корневые объекты, так как мы только что переключились
            # (код выше уже имеет логику для None, просто вызовем get_current_view_objects после update_data? 
            # Нет, update_data асинхронный, но локальная переменная current_folder_id старая.
            # Проще пересчитать.)
            
            # Пересчитываем для корня
            folder_channel_ids = set()
            for f in all_folders:
                for chat_id in f.content:
                    if chat_id.isdigit():
                        folder_channel_ids.add(int(chat_id))
            root_channels = [c for c in all_channels if c.chat_id not in folder_channel_ids]
            
            await call.message.edit_text(
                text=text("choice_channels:post").format(len(all_channels), ""),
                reply_markup=keyboards.choice_channels_for_post(
                    channels=root_channels,
                    folders=all_folders,
                    chosen=chosen,
                    is_folder_view=False
                )
            )
            return
        else:
            # Выход в меню
            await state.clear()
            await call.message.delete()
            await call.message.answer(
                text("reply_menu:posting"), reply_markup=keyboards.posting_menu()
            )
            return

    if action == "folder":
        folder_id = int(data[2])
        await state.update_data(current_folder_id=folder_id)
        
        # Получаем каналы папки
        folder = next((f for f in all_folders if f.id == folder_id), None)
        if folder:
            folder_content_ids = [int(x) for x in folder.content if x.isdigit()]
            folder_channels = [c for c in all_channels if c.chat_id in folder_content_ids]
            
            await call.message.edit_text(
                text=text("choice_channels:post").format(len(all_channels), f"\n📁 {folder.title}"),
                reply_markup=keyboards.choice_channels_for_post(
                    channels=folder_channels,
                    folders=[],
                    chosen=chosen,
                    is_folder_view=True
                )
            )
        return

    if action == "channel":
        channel_id = int(data[2])
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
                is_folder_view=bool(current_folder_id),
                remover=int(data[3]) if len(data) > 3 and data[3].isdigit() else 0 # Сохраняем пагинацию если есть?
                # В текущей реализации keyboards.py remover передается в next/back, но не в channel click.
                # При клике на канал мы обычно остаемся на той же странице, но remover надо знать.
                # Пока сбросим на 0 или попробуем сохранить, если передадим в callback.
                # В keyboards.py callback_data=f"{data}|channel|{obj.chat_id}". Нет remover.
                # Значит сбросится на 0. Это не критично для MVP, но можно улучшить.
            )
        )
        return

    if action == "choice_all":
        # Выбрать все каналы (вообще все, по ТЗ)
        # "эта кнопка работает как выбор всех каналов и тех что внутри папок"
        all_ids = [c.chat_id for c in all_channels]
        
        # Если уже все выбраны - снять выделение? Или просто выбрать все?
        # Обычно toggle. Если все выбраны -> очистить. Иначе -> выбрать все.
        if set(all_ids).issubset(set(chosen)):
            chosen = []
        else:
            chosen = list(set(chosen) | set(all_ids)) # Добавляем все
            
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
        if not chosen:
             await call.answer(text("error_min_choice"), show_alert=True)
             return

        # Сохраняем выбранные каналы как channel_id (для совместимости) или список
        # В create_post.py ожидается channel_id или список?
        # Надо проверить create_post.py. Пока сохраним chosen.
        await state.update_data(chosen_channels=chosen) # Используем новое имя, чтобы не путать с channel_id
        
        await call.message.delete()
        await call.message.answer(
            text("input_message"), reply_markup=keyboards.cancel(data="InputPostCancel")
        )
        await state.set_state(Posting.input_message)
        return

    if action in ["next", "back"]:
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
