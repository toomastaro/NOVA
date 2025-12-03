import os
from pathlib import Path

from aiogram.fsm.context import FSMContext
from aiogram import types, Router, F

from main_bot.keyboards.keyboards import keyboards
from main_bot.states.admin import Session
from main_bot.utils.session_manager import SessionManager
from main_bot.database.db import db

apps = {}


async def choice(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] == 'add':
        await call.message.edit_text(
            'Отправьте цифры сессии: ',
            reply_markup=keyboards.back(
                data="AdminSessionNumberBack"
            )
        )
        return await state.set_state(Session.phone)

    if temp[1] == 'cancel':
        await call.message.edit_text(
            'Админ меню',
            reply_markup=keyboards.admin()
        )

    if temp[1] in ['internal', 'external']:
        pool_type = temp[1]
        clients = await db.get_mt_clients_by_pool(pool_type)

        text_response = f"Список {pool_type} клиентов:\n\n"
        if not clients:
            text_response += "Пусто"
        else:
            for client in clients:
                text_response += f"ID: {client.id} | Alias: {client.alias} | Status: {client.status} | Pool: {client.pool_type}\n"

        await call.message.edit_text(
            text_response,
            reply_markup=keyboards.admin_sessions()
        )


async def admin_session_back(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    try:
        number = data.get("number")
        app: SessionManager = apps[number]
        os.remove(app.session_path)
        await app.close()
    except Exception as e:
        print(e)

    await state.clear()
    session_count = len(os.listdir("main_bot/utils/sessions/"))

    await call.message.delete()
    await call.message.answer(
        "Доступно сессий: {}".format(session_count),
        reply_markup=keyboards.admin_sessions()
    )


async def get_number(message: types.Message, state: FSMContext):
    number = message.text
    session_path = Path("main_bot/utils/sessions/{}.session".format(number))
    manager = SessionManager(session_path)
    await manager.init_client()

    try:
        if not manager.client:
            raise Exception("Error Init")

        code = await manager.client.send_code_request(number)
        apps[number] = manager

    except Exception as e:
        print(e)
        await manager.close()
        os.remove(session_path)
        return await message.answer(
            '❌ Неверный номер',
            reply_markup=keyboards.cancel(
                data="AdminSessionNumberBack"
            )
        )

    await state.update_data(
        hash_code=code.phone_code_hash,
        number=number,
    )

    await message.answer(
        "Дай цифры с уведомления:",
        reply_markup=keyboards.cancel(
            data="AdminSessionNumberBack"
        )
    )
    await state.set_state(Session.code)


async def get_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    number = data.get("number")
    hash_code = data.get("hash_code")
    app: SessionManager = apps[number]

    try:
        await app.client.sign_in(
            number,
            message.text,
            phone_code_hash=hash_code
        )
        await app.close()

    except Exception as e:
        print(e)

        await app.close()
        os.remove(app.session_path)

        await state.clear()
        return await message.answer(
            '❌ Неверный код',
            reply_markup=keyboards.cancel(
                data="AdminSessionNumberBack"
            )
        )

    await state.clear()
    session_count = len(os.listdir("main_bot/utils/sessions/"))
    await message.answer(
        "Доступно сессий: {}".format(session_count),
        reply_markup=keyboards.admin_sessions()
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split('|')[0] == "AdminSession")
    router.callback_query.register(admin_session_back, F.data.split('|')[0] == "AdminSessionNumberBack")
    router.message.register(get_number, Session.phone, F.text)
    router.message.register(get_code, Session.code, F.text)
    return router
