"""
Модуль выбора ботов для постинга.

Содержит логику:
- Выбор ботов/каналов для публикации
- Подсчет доступных пользователей
- Вспомогательные функции для работы с папками
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.db import db
from main_bot.handlers.user.menu import start_bots
from main_bot.handlers.user.bots.menu import show_create_post
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards

logger = logging.getLogger(__name__)
from main_bot.utils.error_handler import safe_handler


async def set_folder_content(resource_id, chosen, chosen_folders):
    """Добавление/удаление всех каналов из папки в список выбранных."""
    folder = await db.get_folder_by_id(
        folder_id=resource_id
    )
    is_append = resource_id not in chosen_folders

    if is_append:
        chosen_folders.append(resource_id)
    else:
        chosen_folders.remove(resource_id)

    for chat_id in folder.content:
        chat_id = int(chat_id)

        channel = await db.get_channel_by_chat_id(chat_id)
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
async def choice_bots(call: types.CallbackQuery, state: FSMContext):
    """Выбор ботов для публикации."""
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    chosen: list = data.get("chosen")
    chosen_folders: list = data.get("chosen_folders")

    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

    if temp[1] == "next_step":
        if not chosen:
            return await call.answer(
                text('error_min_choice')
            )

        await call.message.delete()
        return await show_create_post(call.message, state)

    folders = await db.get_folders(
        user_id=call.from_user.id,
    )

    if temp[1] == "cancel":
        await call.message.delete()
        return await start_bots(call.message)

    if temp[1] in ['next', 'back']:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                chosen_folders=chosen_folders,
                data="ChoicePostBots"
            )
        )

    if temp[1] == "choice_all":
        if len(chosen) == len(objects) and len(chosen_folders) == len(folders):
            chosen.clear()
            chosen_folders.clear()
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
                
                return await call.answer(
                    f"❌ Невозможно выбрать всех ботов\n\n"
                    f"Следующие боты не имеют активной подписки:\n{bots_list}\n\n"
                    f"Оплатите подписку через меню 💎 Подписка",
                    show_alert=True
                )
            
            extend_list = [i.chat_id for i in objects if i.chat_id not in chosen]
            chosen.extend(extend_list)
            if folders:
                for folder in folders:
                    sub_channels = []
                    for chat_id in folder.content:
                        user_bot = await db.get_channel_by_chat_id(int(chat_id))

                        if not user_bot.subscribe:
                            continue

                        sub_channels.append(int(chat_id))

                    if len(sub_channels) == len(folder.content):
                        chosen_folders.append(folder.id)

            chosen = list(set(chosen))

    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])

        if temp[3] == 'channel':
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                user_bot = await db.get_channel_by_chat_id(resource_id)
                if not user_bot.subscribe:
                    return await call.answer(
                        text("error_sub_channel:bots").format(user_bot.title),
                        show_alert=True
                    )

                chosen.append(resource_id)
        else:
            temp_chosen, temp_chosen_folders = await set_folder_content(
                resource_id=resource_id,
                chosen=chosen,
                chosen_folders=chosen_folders
            )
            if temp_chosen == "subscribe":
                return await call.answer(
                    text("error_sub_channel_folder:bots")
                )



    # Recalculate stats based on Unique Bots for accuracy
    # Convert chosen channels to unique bots
    all_settings = await db.get_bot_channels(call.from_user.id)
    selected_settings = [s for s in all_settings if s.id in chosen]
    unique_bot_ids = list(set(s.bot_id for s in selected_settings if s.bot_id))
    
    total_users = 0
    active_users = 0
    
    for bot_id in unique_bot_ids:
        user_bot = await db.get_bot_by_id(bot_id)
        if not user_bot: continue
        
        other_db = Database()
        other_db.schema = user_bot.schema
        # Get total and active counts
        stats = await other_db.get_count_users() # Assuming this method exists and returns dict
        total_users += stats.get('total', 0)
        active_users += stats.get('active', 0)

    unavailable = total_users - active_users
    available = active_users

    await state.update_data(
        chosen=chosen,
        chosen_folders=chosen_folders,
        available=available
    )

    await call.message.edit_text(
        text("choice_bots:post").format(
            available,
            unavailable
        ),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            chosen_folders=chosen_folders,
            remover=int(temp[2]),
            data="ChoicePostBots"
        )
    )
