"""
Управление папками пользователя (коллекции каналов).

Позволяет создавать папки, добавлять в них каналы и управлять ими.
Используется для группировки каналов при массовых операциях (аналитика, покупка рекламы).
"""

import logging
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.db_types import FolderType
from main_bot.database.user.model import User

from main_bot.handlers.user.profile.settings import show_folders
from main_bot.keyboards import keyboards
from main_bot.keyboards.common import Reply
from main_bot.states.user import Folder
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler(
    "Папки: управление"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_manage_folder(message: types.Message, state: FSMContext):
    """Показывает меню управления конкретной папкой."""
    data = await state.get_data()
    folder_id = data.get("folder_id")
    folder = await db.user_folder.get_folder_by_id(folder_id)

    await message.answer(
        text("manage:folder").format(folder.title),
        reply_markup=keyboards.manage_folder(),
    )


@safe_handler(
    "Папки: выбор"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice(call: types.CallbackQuery, state: FSMContext):
    """Маршрутизатор главного меню папок."""
    temp = call.data.split("|")

    if temp[1] in ["next", "back"]:
        folders = await db.user_folder.get_folders(call.from_user.id)

        return await call.message.edit_reply_markup(
            reply_markup=keyboards.folders(folders=folders, remover=int(temp[2]))
        )

    if temp[1] == "cancel":
        # Возврат в меню настроек (профиль) - используем edit для скорости
        return await call.message.edit_text(
            text("start_profile_text"),
            reply_markup=keyboards.profile_menu(),
            parse_mode="HTML",
        )

    await call.message.delete()

    if temp[1] == "create":
        # Прямой поток создания коллекции каналов
        # Начинаем с ввода названия
        await call.message.answer(
            text("input_folder_name"),
            reply_markup=keyboards.back(data="InputFolderName"),
        )
        await state.update_data(
            folder_type=FolderType.CHANNEL, chosen=[], folder_edit=False
        )
        await state.set_state(Folder.input_name)
        return

    folder_id = int(temp[1])
    await state.update_data(folder_id=folder_id)

    await show_manage_folder(call.message, state)


# Устаревшая логика выбора типа, но оставляем сигнатуру или удаляем
# Лучше удалить для чистоты, но пока оставляем как заглушку


@safe_handler(
    "Папки: выбор типа"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_type(call: types.CallbackQuery, state: FSMContext, user: User):
    """Заглушка для выбора типа папки (устаревшее)."""
    # Этот хендлер больше не используется в новом потоке
    pass


@safe_handler(
    "Папки: выбор объекта"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_object(call: types.CallbackQuery, state: FSMContext, user: User):
    """Обработчик выбора объектов (каналов) для папки."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    # Всегда каналы
    cor = db.channel.get_user_channels
    object_type = "channels"
    chosen: list = data.get("chosen")
    folder_edit = data.get("folder_edit")

    if temp[1] == "cancel":
        await call.message.delete()

        if not folder_edit:
            # Отмена создания -> назад к настройкам
            return await call.message.answer(
                text("start_profile_text"),
                reply_markup=keyboards.profile_menu(),
                parse_mode="HTML",
            )
        else:
            await show_manage_folder(call.message, state)

        return

    objects = await cor(
        user_id=user.id,
    )

    if temp[1] in ["next", "back"]:
        return await call.message.edit_text(
            text(f"folders:chosen:{object_type}").format(
                "<blockquote expandable>"
                + "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                )
                + "</blockquote>"
            ),
            reply_markup=keyboards.choice_object_folders(
                resources=objects, chosen=chosen, remover=int(temp[2])
            ),
        )

    if temp[1] == "next_step":
        # Если редактирование - сохраняем контент. Если создание, мы закончили (так как имя уже введено).
        # Но подождите, оригинальный поток был Имя -> Контент.
        # Новый поток: Имя -> Контент -> Сохранить?
        # Ввод имени -> Сохранить папку (пустую) -> Управление папкой -> Контент.

        if not folder_edit:
            # Этот блок не должен быть достигнут, если строго следовать потоку "Имя -> Сохранить -> Управление".
            pass
        else:
            await db.user_folder.update_folder(
                folder_id=data.get("folder_id"), content=[str(i) for i in chosen]
            )
            await show_manage_folder(call.message, state)
            # Перезагрузка главного меню
            await call.message.answer("Главное меню", reply_markup=Reply.menu())

        return

    if temp[1] == "choice_all":
        # objects это каналы, у них есть chat_id
        current_ids = [i.chat_id for i in objects]
        if len(current_ids) == len(chosen):
            chosen.clear()
        else:
            # Добавляем все, которых нет в chosen
            for i in objects:
                if i.chat_id not in chosen:
                    chosen.append(i.chat_id)

    if temp[1].lstrip("-").isdigit():  # chat_id может быть отрицательным
        resource_id = int(temp[1])
        if resource_id in chosen:
            chosen.remove(resource_id)
        else:
            chosen.append(resource_id)

    await state.update_data(chosen=chosen)
    await call.message.edit_text(
        text(f"folders:chosen:{object_type}").format(
            "<blockquote expandable>"
            + "\n".join(
                text("resource_title").format(obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            )
            + "</blockquote>"
        ),
        reply_markup=keyboards.choice_object_folders(
            resources=objects,
            chosen=chosen,
            remover=(
                int(temp[2])
                if temp[1] in ["choice_all"] or temp[1].lstrip("-").isdigit()
                else 0
            ),
        ),
    )


@safe_handler(
    "Папки: отмена"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def cancel(call: types.CallbackQuery, state: FSMContext, user: User):
    """Отмена текущего действия (создания или переименования)."""

    data = await state.get_data()

    await state.clear()

    await call.message.delete()

    folder_edit = data.get("folder_edit")
    if folder_edit:
        # Восстанавливаем folder_id
        await state.update_data(folder_id=data.get("folder_id"))
        await show_manage_folder(call.message, state)
    else:
        # Отмена создания -> назад в настройки
        await call.message.answer(
            text("start_profile_text"),
            reply_markup=keyboards.profile_menu(),
            parse_mode="HTML",
        )
        # Перезагрузка главного меню
        await call.message.answer("Главное меню", reply_markup=Reply.menu())


@safe_handler(
    "Папки: ввод имени"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def get_folder_name(message: types.Message, state: FSMContext, user: User):
    """Обработчик ввода имени папки."""
    title = message.text
    if len(title) > 20:
        return await message.answer(text("error_symbol_folder_name"))

    folder = await db.user_folder.get_folder_by_title(title, user.id)
    if folder:
        return await message.answer(text("error_exist_folder_name"))

    data = await state.get_data()
    folder_edit = data.get("folder_edit")

    if not folder_edit:
        # Создание новой папки
        await db.user_folder.add_folder(
            user_id=user.id, title=title, type=FolderType.CHANNEL, content=[]
        )
    else:
        folder_id = data.get("folder_id")
        await db.user_folder.update_folder(folder_id=folder_id, title=title)

    folder = await db.user_folder.get_folder_by_title(title=title, user_id=user.id)
    await state.clear()
    await state.update_data(
        folder_id=folder.id,
    )

    if not folder_edit:
        chosen = []
        cor = db.channel.get_user_channels
        object_type = "channels"

        objects = await cor(user_id=user.id)

        await state.update_data(
            folder_id=folder.id,
            folder_edit=True,
            chosen=chosen,
            object_type=object_type,
        )

        await message.answer(
            text(f"folders:chosen:{object_type}").format(
                "<blockquote expandable>" + "" + "</blockquote>"
            ),
            reply_markup=keyboards.choice_object_folders(
                resources=objects,
                chosen=chosen,
            ),
        )
        # Перезагрузка главного меню
        await message.answer("Главное меню", reply_markup=Reply.menu())
    else:
        await show_manage_folder(message, state)
        # Перезагрузка главного меню
        await message.answer("Главное меню", reply_markup=Reply.menu())


@safe_handler(
    "Папки: управление папкой"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def manage_folder(call: types.CallbackQuery, state: FSMContext, user: User):
    """Управление папкой: переименование, изменение контента, удаление."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    await call.message.delete()

    if temp[1] in ["back", "remove"]:
        if temp[1] == "remove":
            await db.user_folder.remove_folder(folder_id=data.get("folder_id"))

        await show_folders(call.message)
        # Перезагрузка главного меню
        await call.message.answer("Главное меню", reply_markup=Reply.menu())
        return

    await state.update_data(folder_edit=True)

    if temp[1] == "title":
        await call.message.answer(
            text("input_folder_name"),
            reply_markup=keyboards.back(data="InputFolderName"),
        )
        await state.set_state(Folder.input_name)

    if temp[1] == "content":
        folder = await db.user_folder.get_folder_by_id(folder_id=data.get("folder_id"))

        chosen = [int(i) for i in folder.content]

        # Always channels
        cor = db.channel.get_user_channels
        object_type = "channels"

        objects = await cor(user_id=user.id)
        await state.update_data(
            chosen=chosen,
            object_type=object_type,
        )
        await call.message.answer(
            text(f"folders:chosen:{object_type}").format(
                "<blockquote expandable>"
                + "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                )
                + "</blockquote>"
            ),
            reply_markup=keyboards.choice_object_folders(
                resources=objects,
                chosen=chosen,
            ),
        )


def get_router():
    """Регистрация роутеров для папок."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoiceFolder")
    router.callback_query.register(
        choice_type, F.data.split("|")[0] == "ChoiceTypeFolder"
    )
    router.callback_query.register(
        choice_object, F.data.split("|")[0] == "ChoiceResourceFolder"
    )
    router.callback_query.register(cancel, F.data.split("|")[0] == "InputFolderName")
    router.message.register(get_folder_name, Folder.input_name, F.text)
    router.callback_query.register(
        manage_folder, F.data.split("|")[0] == "ManageFolder"
    )
    return router
