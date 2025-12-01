from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.types import FolderType
from main_bot.database.user.model import User
from main_bot.handlers.user.profile.profile import show_setting
from main_bot.handlers.user.profile.settings import show_folders
from main_bot.keyboards.keyboards import keyboards
from main_bot.states.user import Folder
from main_bot.utils.lang.language import text


async def show_manage_folder(message: types.Message, state: FSMContext):
    data = await state.get_data()
    folder_id = data.get('folder_id')
    folder = await db.get_folder_by_id(folder_id)

    await message.answer(
        text('manage:folder').format(folder.title),
        reply_markup=keyboards.manage_folder()
    )


async def choice(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] in ['next', 'back']:
        folders = await db.get_folders()

        return await call.message.edit_reply_markup(
            reply_markup=keyboards.folders(
                folders=folders,
                remover=int(temp[2])
            )
        )

    await call.message.delete()

    if temp[1] == 'cancel':
        return await show_setting(call.message)

    if temp[1] == 'create':
        return await call.message.answer(
            text('choice_folder_type'),
            reply_markup=keyboards.choice_type_folder()
        )

    folder_id = int(temp[1])
    await state.update_data(
        folder_id=folder_id
    )

    await show_manage_folder(call.message, state)


async def choice_type(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')

    if temp[1] == 'back':
        await call.message.delete()
        return await show_folders(call.message)

    await state.update_data(
        folder_type=temp[1]
    )

    if temp[1] == FolderType.BOT:
        cor = db.get_user_bots
        object_type = 'bots'
    else:
        cor = db.get_user_channels
        object_type = 'channels'

    objects = await cor(
        user_id=user.id,
    )
    if not objects:
        return await call.answer(
            text(f'not_found_{object_type}'),
            show_alert=True
        )

    await state.update_data(
        object_type=object_type,
        cor=cor,
        chosen=[]
    )

    await call.message.delete()
    await call.message.answer(
        text(f'folders:chosen:{object_type}').format(
            ""
        ),
        reply_markup=keyboards.choice_object_folders(
            resources=objects,
            chosen=[]
        )
    )


async def choice_object(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    cor = data.get('cor')
    object_type = data.get('object_type')
    chosen: list = data.get('chosen')
    folder_edit = data.get('folder_edit')

    if temp[1] == 'cancel':
        await call.message.delete()

        if not folder_edit:
            await call.message.answer(
                text('choice_folder_type'),
                reply_markup=keyboards.choice_type_folder()
            )
        else:
            await show_manage_folder(call.message, state)

        return

    objects = await cor(
        user_id=user.id,
    )

    if temp[1] in ['next', 'back']:
        return await call.message.edit_text(
            text(f'folders:chosen:{object_type}').format(
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if getattr(obj, "id" if object_type == "bots" else "chat_id") in chosen[:10]
                )
            ),
            reply_markup=keyboards.choice_object_folders(
                resources=objects,
                chosen=chosen,
                remover=int(temp[2])
            )
        )

    if temp[1] == 'next_step':
        if not chosen:
            return await call.answer(
                text('error_min_choice'),
                show_alert=True
            )

        await call.message.delete()

        if not folder_edit:
            await call.message.answer(
                text('input_folder_name'),
                reply_markup=keyboards.back(
                    data='InputFolderName'
                )
            )
            await state.set_state(Folder.input_name)
        else:
            await db.update_folder(
                folder_id=data.get('folder_id'),
                content=[str(i) for i in chosen]
            )
            await show_manage_folder(call.message, state)

        return

    if temp[1] == 'choice_all':
        if len(objects) == len(chosen):
            chosen.clear()
        else:
            chosen.extend(
                [i.id for i in objects
                 if i.id not in chosen]
            )

    if temp[1].isdigit():
        resource_id = int(temp[1])
        if resource_id in chosen:
            chosen.remove(resource_id)
        else:
            chosen.append(resource_id)

    await state.update_data(
        chosen=chosen
    )
    await call.message.edit_text(
        text(f'folders:chosen:{object_type}').format(
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if getattr(obj, "id" if object_type == "bots" else "chat_id") in chosen[:10]
            )
        ),
        reply_markup=keyboards.choice_object_folders(
            resources=objects,
            chosen=chosen,
            remover=int(temp[2])
        )
    )


async def cancel(call: types.CallbackQuery, state: FSMContext, user: User):
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    await state.clear()
    await state.update_data(data)

    cor = data.get('cor')
    chosen = data.get('chosen')
    object_type = data.get('object_type')
    folder_edit = data.get('folder_edit')

    await call.message.delete()

    if not folder_edit:
        objects = await cor(
            user_id=user.id
        )
        await call.message.answer(
            text(f'folders:chosen:{object_type}').format(
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if getattr(obj, "id" if object_type == "bots" else "chat_id") in chosen[:10]
                )
            ),
            reply_markup=keyboards.choice_object_folders(
                resources=objects,
                chosen=chosen,
            )
        )
    else:
        await show_manage_folder(call.message, state)


async def get_folder_name(message: types.Message, state: FSMContext, user: User):
    title = message.text
    if len(title) > 20:
        return await message.answer(
            text('error_symbol_folder_name')
        )

    folder = await db.get_folder_by_title(title, user.id)
    if folder:
        return await message.answer(
            text('error_exist_folder_name')
        )

    data = await state.get_data()
    folder_type = data.get('folder_type')
    chosen = data.get('chosen')
    folder_edit = data.get('folder_edit')

    if not folder_edit:
        await db.add_folder(
            user_id=user.id,
            title=title,
            type=folder_type,
            content=[str(i) for i in chosen]
        )
    else:
        folder_id = data.get('folder_id')
        await db.update_folder(
            folder_id=folder_id,
            title=title
        )

    folder = await db.get_folder_by_title(
        title=title,
        user_id=user.id
    )
    await state.clear()
    await state.update_data(
        folder_id=folder.id,
    )
    await show_manage_folder(message, state)


async def manage_folder(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    await call.message.delete()

    if temp[1] in ['back', 'remove']:
        if temp[1] == 'remove':
            await db.remove_folder(
                folder_id=data.get('folder_id')
            )

        return await show_folders(call.message)

    await state.update_data(
        folder_edit=True
    )

    if temp[1] == 'title':
        await call.message.answer(
            text('input_folder_name'),
            reply_markup=keyboards.back(
                data='InputFolderName'
            )
        )
        await state.set_state(Folder.input_name)

    if temp[1] == 'content':
        folder = await db.get_folder_by_id(
            folder_id=data.get('folder_id')
        )
        chosen = [
            int(i) for i in folder.content
        ]
        if folder.type == FolderType.BOT:
            cor = db.get_user_bots
            object_type = 'bots'
        else:
            cor = db.get_user_channels
            object_type = 'channels'

        objects = await cor(
            user_id=user.id
        )
        await state.update_data(
            cor=cor,
            chosen=chosen,
            object_type=object_type,
        )
        await call.message.answer(
            text(f'folders:chosen:{object_type}').format(
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if getattr(obj, "id" if object_type == "bots" else "chat_id") in chosen[:10]
                )
            ),
            reply_markup=keyboards.choice_object_folders(
                resources=objects,
                chosen=chosen,
            )
        )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split('|')[0] == 'ChoiceFolder')
    router.callback_query.register(choice_type, F.data.split('|')[0] == 'ChoiceTypeFolder')
    router.callback_query.register(choice_object, F.data.split('|')[0] == 'ChoiceResourceFolder')
    router.callback_query.register(cancel, F.data.split('|')[0] == 'InputFolderName')
    router.message.register(get_folder_name, Folder.input_name, F.text)
    router.callback_query.register(manage_folder, F.data.split('|')[0] == 'ManageFolder')
    return router
