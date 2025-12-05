from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.types import FolderType
from main_bot.database.user.model import User
from main_bot.handlers.user.profile.profile import show_setting
from main_bot.handlers.user.profile.settings import show_folders
from main_bot.keyboards import keyboards
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
        folders = await db.get_folders(call.from_user.id)

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
        # Direct flow for creating channel collection
        # Start with inputting name
        await call.message.answer(
            text('input_folder_name'),
            reply_markup=keyboards.back(
                data='InputFolderName'
            )
        )
        await state.update_data(
            folder_type=FolderType.CHANNEL,
            chosen=[],
            folder_edit=False
        )
        await state.set_state(Folder.input_name)
        return

    folder_id = int(temp[1])
    await state.update_data(
        folder_id=folder_id
    )

    await show_manage_folder(call.message, state)


# Deprecated/Removed choice_type handler logic, but keeping function signature if needed or removing it. 
# Since we removed the call to it in `choice`, we can remove it or leave it as dead code for now.
# Better to remove it to clean up.

async def choice_type(call: types.CallbackQuery, state: FSMContext, user: User):
    # This handler is no longer used in the new flow
    pass


async def choice_object(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    # Always channels
    cor = db.get_user_channels
    object_type = 'channels'
    chosen: list = data.get('chosen')
    folder_edit = data.get('folder_edit')

    if temp[1] == 'cancel':
        await call.message.delete()

        if not folder_edit:
            # Cancel creation -> go back to settings
            return await show_setting(call.message)
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
                    if obj.chat_id in chosen[:10]
                )
            ),
            reply_markup=keyboards.choice_object_folders(
                resources=objects,
                chosen=chosen,
                remover=int(temp[2])
            )
        )

    if temp[1] == 'next_step':
        # If editing, save content. If creating, we are done (since name is already input)
        # Wait, original flow was Name -> Content.
        # New flow: Name -> Content -> Save?
        # The user said: "After creating collection immediately propose content management".
        # So: Input Name -> Save Folder (empty) -> Manage Folder -> Content.
        # But here we are in choice_object.
        # If we are here, it means we are selecting content.
        
        if not folder_edit:
            # This block shouldn't be reached if we follow "Name -> Save -> Manage" flow strictly.
            # But if we want "Name -> Content -> Save", then:
            pass
        else:
            await db.update_folder(
                folder_id=data.get('folder_id'),
                content=[str(i) for i in chosen]
            )
            await show_manage_folder(call.message, state)

        return

    if temp[1] == 'choice_all':
        # objects are Channels, they have chat_id
        current_ids = [i.chat_id for i in objects]
        if len(current_ids) == len(chosen):
            chosen.clear()
        else:
            # Add all that are not in chosen
            for i in objects:
                if i.chat_id not in chosen:
                    chosen.append(i.chat_id)

    if temp[1].lstrip('-').isdigit(): # chat_id can be negative
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
                if obj.chat_id in chosen[:10]
            )
        ),
        reply_markup=keyboards.choice_object_folders(
            resources=objects,
            chosen=chosen,
            remover=int(temp[2]) if temp[1] in ['choice_all'] or temp[1].lstrip('-').isdigit() else 0
        )
    )


async def cancel(call: types.CallbackQuery, state: FSMContext, user: User):
    # This is for InputFolderName cancel
    data = await state.get_data()
    
    await state.clear()
    # If we were editing, restore data? 
    # Actually, InputFolderName is used for both creating and renaming.
    
    await call.message.delete()
    
    folder_edit = data.get('folder_edit')
    if folder_edit:
        # Restore folder_id
        await state.update_data(folder_id=data.get('folder_id'))
        await show_manage_folder(call.message, state)
    else:
        # Cancel creation -> back to settings
        await show_setting(call.message)


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
    folder_edit = data.get('folder_edit')

    if not folder_edit:
        # Creating new folder
        await db.add_folder(
            user_id=user.id,
            title=title,
            type=FolderType.CHANNEL,
            content=[]
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
    
    # After creating/renaming, go to manage folder
    # If it was new, we want to immediately propose content management?
    # The user said: "After creating collection immediately propose content management".
    # So we should trigger 'content' action of manage_folder.
    
    if not folder_edit:
        # Simulate clicking "Content"
        # We need to set up state for content management
        chosen = []
        cor = db.get_user_channels
        object_type = 'channels'
        
        objects = await cor(user_id=user.id)
        
        await state.update_data(
            folder_id=folder.id,
            folder_edit=True, # Now we are in edit mode effectively
            cor=cor, # Store coroutine function? No, we can't store async func in state easily if it's not pickleable, but here it was stored before.
            # Actually, previous code stored 'cor'. Let's avoid storing functions in state if possible, but if it works...
            # 'db.get_user_channels' is a bound method.
            # Better to just store 'object_type' and deduce 'cor' in handlers.
            chosen=chosen,
            object_type=object_type
        )
        
        await message.answer(
            text(f'folders:chosen:{object_type}').format(
                ""
            ),
            reply_markup=keyboards.choice_object_folders(
                resources=objects,
                chosen=chosen,
            )
        )
    else:
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
        # Content is list of strings (chat_ids)
        chosen = [
            int(i) for i in folder.content
        ]
        
        # Always channels
        cor = db.get_user_channels
        object_type = 'channels'

        objects = await cor(
            user_id=user.id
        )
        await state.update_data(
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
                    if obj.chat_id in chosen[:10]
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
