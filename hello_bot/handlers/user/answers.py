"""
Модуль управления автоответами (answers).

Позволяет создавать, редактировать и удалять настройки автоответов на ключевые слова.
"""

import random
import string

from loguru import logger

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext


from hello_bot.database.db import Database
from hello_bot.handlers.user.menu import show_answers
from hello_bot.states.user import Answer
from hello_bot.utils.lang.language import text
from hello_bot.keyboards.keyboards import keyboards
from hello_bot.utils.schemas import Media, MessageOptions, Answer as AnswerObj
from hello_bot.utils.functions import answer_message
from utils.error_handler import safe_handler


@safe_handler("Автоответы: выбор действия")
async def choice(call: types.CallbackQuery, state: FSMContext, settings):
    """
    Обрабатывает выбор действия в меню автоответов.

    :param call: CallbackQuery
    :param state: FSMContext
    :param settings: Настройки канала
    """
    temp = call.data.split("|")
    logger.debug(f"Выбор в автоответах: {temp}")

    if temp[1] == "cancel":
        return await call.message.edit_text(
            text("start_text"), reply_markup=keyboards.menu()
        )

    if temp[1] == "add":
        await state.update_data(step="keyword", edit=None)
        await call.message.edit_text(
            text("answer:add:keyword"),
            reply_markup=keyboards.back(data="BackAddAnswer"),
        )
        return await state.set_state(Answer.keyword)

    for answer in settings.answers:
        answer = AnswerObj(**answer)

        if answer.id != temp[1]:
            continue

        await state.update_data(answer=answer)

        await call.message.delete()
        await answer_message(call.message, answer.message, keyboards.manage_answer())


@safe_handler("Автоответы: возврат назад")
async def back_answer(call: types.CallbackQuery, state: FSMContext, settings):
    """
    Возврат к предыдущему шагу или меню списка ответов.
    """
    temp = call.data.split("|")
    data = await state.get_data()

    step = data.get("step")

    if len(temp) == 1 or temp[1] == "cancel" or step == "keyword":
        await call.message.delete()
        return await show_answers(call.message, settings)

    if step == "message":
        await state.update_data(step="keyword")
        await call.message.edit_text(
            text("answer:add:keyword"),
            reply_markup=keyboards.back(data="BackAddAnswer"),
        )
        await state.set_state(Answer.keyword)


@safe_handler("Автоответы: получение ключевого слова")
async def get_keyword(
    message: types.Message, state: FSMContext, db: Database, settings
):
    """
    Обрабатывает ввод ключевого слова для автоответа.
    """
    data = await state.get_data()
    edit = data.get("edit")
    logger.info(f"Установка ключевого слова: {message.text}, режим_правки={edit}")

    if edit:
        for i_answer in settings.answers:
            if i_answer["id"] != data.get("answer").id:
                continue

            i_answer["key"] = message.text
            await db.update_setting(return_obj=True, answers=settings.answers)

            answer = AnswerObj(**i_answer)
            await state.update_data(answer=answer)

            reply = keyboards.manage_answer()
            return await answer_message(message, answer.message, reply)

    await state.update_data(key=message.text, step="message")
    await message.answer(
        text("answer:add:message").format(message.text),
        reply_markup=keyboards.param_answers_back(),
    )
    await state.set_state(Answer.message)


@safe_handler("Автоответы: получение сообщения")
async def get_message(
    message: types.Message, state: FSMContext, db: Database, settings
):
    """
    Обрабатывает ввод сообщения (ответа) ботом.
    """
    message_text_length = len(message.caption or message.text or "")
    if message_text_length > 1024:
        return await message.answer(text("error_length_text"))

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)

    message_options = MessageOptions(**dump_message)
    if message_text_length:
        if message_options.text:
            message_options.text = message.html_text
        if message_options.caption:
            message_options.caption = message.html_text

    data = await state.get_data()
    edit = data.get("edit")

    if edit:
        answer = data.get("answer")
        for i_answer in settings.answers:
            if i_answer["id"] != data.get("answer").id:
                continue

            i_answer["message"] = message_options.model_dump()
            settings = await db.update_setting(
                return_obj=True, answers=settings.answers
            )
            answer = AnswerObj(**i_answer)
    else:
        answer = AnswerObj(
            id="".join(random.sample(string.ascii_letters, k=8)),
            message=message_options,
            key=data.get("key"),
        )
        settings.answers.append(answer.model_dump())
        logger.info(f"Добавлен новый автоответ: {answer.id} -> {answer.key}")

    await db.update_setting(answers=settings.answers)

    await state.clear()
    await state.update_data(answer=answer)

    reply = keyboards.manage_answer()
    await answer_message(message, message_options, reply)


@safe_handler("Автоответы: управление ответом")
async def manage_answer(
    call: types.CallbackQuery, state: FSMContext, db: Database, settings
):
    """Управление конкретным автоответом (редактирование/удаление)."""
    temp = call.data.split("|")
    data = await state.get_data()

    if temp[1] in ["cancel", "delete"]:
        if temp[1] == "delete":
            for answer in settings.answers:
                if answer["id"] != data.get("answer").id:
                    continue
                settings.answers.remove(answer)
                logger.info(f"Автоответ удален: {answer['id']}")

            settings = await db.update_setting(
                return_obj=True, answers=settings.answers
            )

        await call.message.delete()
        return await show_answers(call.message, settings)

    await state.update_data(step="keyword", edit=True)

    message_text = text("answer:change:{}".format(temp[1]))
    if temp[1] == "keyword":
        state_name = Answer.keyword
        reply = keyboards.back(data="BackAddAnswer")
    else:
        state_name = Answer.message
        reply = keyboards.param_answers_back()

    await call.message.delete()
    await call.message.answer(message_text, reply_markup=reply)
    await state.set_state(state_name)


def hand_add():
    """Регистрация хэндлеров для ответов."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Answer")
    router.callback_query.register(back_answer, F.data.split("|")[0] == "BackAddAnswer")
    router.message.register(get_keyword, Answer.keyword, F.text)
    router.message.register(
        get_message, Answer.message, F.text | F.photo | F.video | F.animation
    )
    router.callback_query.register(
        manage_answer, F.data.split("|")[0] == "ManageAnswer"
    )

    return router
