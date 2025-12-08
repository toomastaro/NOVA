"""
Модуль обработки кнопок и реакций в посте.

Содержит логику:
- Добавление hide кнопок (скрытый текст для подписчиков/неподписчиков)
- Обработка кликов на hide кнопки
- Обработка кликов на реакции
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import Hide, React
from main_bot.keyboards import keyboards
from main_bot.states.user import AddHide
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Posting Add Hide Value")
async def add_hide_value(call: types.CallbackQuery, state: FSMContext):
    """
    Начало добавления hide кнопки.
    
    Args:
        call: Callback query с действием
        state: FSM контекст
    """
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    await call.message.delete()

    if temp[1] == "...":
        return await call.answer()

    if temp[1] == "add":
        await state.update_data(
            hide_step="button_name"
        )
        await call.message.answer(
            text("manage:post:add:param:hide:button_name"),
            reply_markup=keyboards.back(data="BackButtonHide")
        )
        await state.set_state(AddHide.button_name)


@safe_handler("Posting Back Input Button Name")
async def back_input_button_name(call: types.CallbackQuery, state: FSMContext):
    """
    Возврат назад при добавлении hide кнопки.
    
    Args:
        call: Callback query
        state: FSM контекст
    """
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    await state.clear()
    await state.update_data(data)
    await call.message.delete()

    hide_step = data.get("hide_step")
    temp = call.data.split("|")

    # Возврат к списку hide кнопок
    if len(temp) == 1 or hide_step == "button_name" or temp[1] == "cancel":
        return await call.message.answer(
            text("manage:post:new:hide"),
            reply_markup=keyboards.param_hide(
                post=data.get('post')
            )
        )
    
    # Возврат к вводу имени кнопки
    if hide_step == "not_member":
        await call.message.answer(
            text("manage:post:add:param:hide:button_name"),
            reply_markup=keyboards.back(data="BackButtonHide")
        )
        return await state.set_state(AddHide.button_name)

    # Возврат к вводу текста для неподписчиков
    if hide_step == "for_member":
        await call.message.answer(
            text("manage:post:add:param:hide:not_member"),
            reply_markup=keyboards.param_hide_back()
        )
        return await state.set_state(AddHide.not_member_text)


@safe_handler("Posting Get Button Name")
async def get_button_name(message: types.Message, state: FSMContext):
    """
    Получение имени hide кнопки.
    
    Args:
        message: Сообщение с именем кнопки
        state: FSM контекст
    """
    await state.update_data(
        hide_button_name=message.text,
        hide_step="not_member"
    )

    await message.answer(
        text("manage:post:add:param:hide:not_member"),
        reply_markup=keyboards.param_hide_back()
    )
    await state.set_state(AddHide.not_member_text)


@safe_handler("Posting Get Not Member Text")
async def get_not_member_text(message: types.Message, state: FSMContext):
    """
    Получение текста для неподписчиков.
    
    Args:
        message: Сообщение с текстом
        state: FSM контекст
    """
    if len(message.text) > 200:
        return await message.answer(
            text("error_200_length_text")
        )

    await state.update_data(
        hide_not_member_text=message.text,
        hide_step="for_member"
    )

    await message.answer(
        text("manage:post:add:param:hide:for_member"),
        reply_markup=keyboards.param_hide_back()
    )
    await state.set_state(AddHide.for_member_text)


@safe_handler("Posting Get For Member Text")
async def get_for_member_text(message: types.Message, state: FSMContext):
    """
    Получение текста для подписчиков и сохранение hide кнопки.
    
    Args:
        message: Сообщение с текстом
        state: FSM контекст
    """
    if len(message.text) > 200:
        return await message.answer(
            text("error_200_length_text")
        )

    await state.update_data(
        hide_for_member_text=message.text
    )
    data = await state.get_data()
    post: Post = data.get('post')

    if post.hide is None:
        post.hide = []

    post.hide.append(
        {
            'id': len(post.hide) + 1,
            'button_name': data.get("hide_button_name"),
            'for_member': data.get("hide_for_member_text"),
            'not_member': data.get("hide_not_member_text"),
        }
    )

    post = await db.update_post(
        post_id=post.id,
        return_obj=True,
        hide=post.hide
    )

    await state.clear()
    await state.update_data(
        post=post,
        show_more=data.get("show_more"),
        param="hide"
    )

    await message.answer(
        text("manage:post:new:hide"),
        reply_markup=keyboards.param_hide(
            post=post
        )
    )


@safe_handler("Posting Click Hide")
async def click_hide(call: types.CallbackQuery):
    """
    Обработка клика на hide кнопку в опубликованном посте.
    
    Показывает разный текст для подписчиков и неподписчиков канала.
    
    Args:
        call: Callback query от hide кнопки
    """
    temp = call.data.split('|')

    published_post = await db.get_published_post(
        chat_id=call.message.sender_chat.id,
        message_id=call.message.message_id,
    )
    if not published_post:
        return

    user = await call.bot.get_chat_member(
        chat_id=call.message.sender_chat.id,
        user_id=call.from_user.id
    )

    hide_model = Hide(hide=published_post.hide)
    for row_hide in hide_model.hide:
        if row_hide.id != int(temp[1]):
            continue

        await call.answer(
            row_hide.for_member if user.status != "left" else row_hide.not_member,
            show_alert=True
        )


@safe_handler("Posting Click React")
async def click_react(call: types.CallbackQuery):
    """
    Обработка клика на реакцию в опубликованном посте.
    
    Добавляет/убирает пользователя из списка реакций и обновляет кнопки.
    
    Args:
        call: Callback query от кнопки реакции
    """
    temp = call.data.split('|')

    published_post = await db.get_published_post(
        chat_id=call.message.sender_chat.id,
        message_id=call.message.message_id,
    )
    if not published_post:
        return

    react_model = React(rows=published_post.reaction.get("rows"))
    for react_row in react_model.rows:
        for react in react_row.reactions:
            # Если пользователь уже нажал на эту реакцию - показываем галочку
            if call.from_user.id in react.users and int(temp[1]) == react.id:
                return await call.answer("✅")

            # Убираем пользователя из других реакций
            if call.from_user.id in react.users:
                react.users.remove(call.from_user.id)
            
            # Добавляем пользователя к выбранной реакции
            if int(temp[1]) == react.id:
                react.users.append(call.from_user.id)

    # Обновляем пост в БД
    post = await db.update_published_post(
        post_id=published_post.id,
        return_obj=True,
        reaction=react_model.model_dump()
    )
    
    # Обновляем кнопки с новыми счетчиками
    await call.message.edit_reply_markup(
        reply_markup=keyboards.post_kb(
            post=post
        )
    )
