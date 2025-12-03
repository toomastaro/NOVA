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
    action = temp[1]

    if action == 'add':
        await call.message.edit_text(
            'Выберите тип клиента:',
            reply_markup=keyboards.admin_session_pool_select()
        )
        return await state.set_state(Session.pool_select)

    if action == 'pool_select':
        pool_type = temp[2]
        await state.update_data(pool_type=pool_type)
        
        await call.message.edit_text(
            f'Выбран тип: {pool_type}\nОтправьте номер телефона (цифры сессии):',
            reply_markup=keyboards.back(
                data="AdminSessionNumberBack"
            )
        )
        return await state.set_state(Session.phone)

    if action == 'cancel' or action == 'back_to_main':
        session_count = len(os.listdir("main_bot/utils/sessions/"))
        await call.message.edit_text(
            "Доступно сессий: {}".format(session_count),
            reply_markup=keyboards.admin_sessions()
        )
        return

    if action in ['internal', 'external']:
        pool_type = action
        clients = await db.get_mt_clients_by_pool(pool_type)
        
        # Store pool type in state to return to list later if needed
        await state.update_data(current_pool=pool_type)

        await call.message.edit_text(
            f"Список {pool_type} клиентов:",
            reply_markup=keyboards.admin_sessions(clients=clients)
        )
        return

    if action == 'back_to_list':
        data = await state.get_data()
        pool_type = data.get("current_pool", "internal")
        clients = await db.get_mt_clients_by_pool(pool_type)
        await call.message.edit_text(
            f"Список {pool_type} клиентов:",
            reply_markup=keyboards.admin_sessions(clients=clients)
        )
        return

    if action == 'manage':
        client_id = int(temp[2])
        client = await db.get_mt_client(client_id)
        if not client:
            await call.answer("Клиент не найден", show_alert=True)
            return

        info = (
            f"🆔 ID: {client.id}\n"
            f"👤 Alias: {client.alias}\n"
            f"🏊 Pool: {client.pool_type}\n"
            f"📊 Status: {client.status}\n"
            f"🔛 Active: {client.is_active}\n"
            f"📅 Created: {client.created_at}\n"
            f"🕒 Last Check: {client.last_self_check_at}\n"
        )
        if client.last_error_code:
            info += f"❌ Last Error: {client.last_error_code} ({client.last_error_at})\n"
        if client.flood_wait_until:
            info += f"⏳ Flood Wait Until: {client.flood_wait_until}\n"

        await call.message.edit_text(
            info,
            reply_markup=keyboards.admin_client_manage(client_id)
        )
        return

    if action == 'reset_ask':
        client_id = int(temp[2])
        await call.message.edit_text(
            f"⚠️ ВЫ УВЕРЕНЫ, что хотите сбросить клиента {client_id}?\n\n"
            "Это приведет к выходу из всех каналов и очистке базы данных для этого клиента.",
            reply_markup=keyboards.admin_client_reset_confirm(client_id)
        )
        return

    if action == 'reset_confirm':
        client_id = int(temp[2])
        from main_bot.utils.mt_client_utils import reset_client_task
        import asyncio
        
        # Trigger background task
        asyncio.create_task(reset_client_task(client_id))
        
        await call.answer("Задача на сброс запущена", show_alert=True)
        
        # Go back to client details (it will update status on next refresh)
        client = await db.get_mt_client(client_id)
        # Manually set status for immediate feedback in UI
        info = (
            f"🆔 ID: {client_id}\n"
            f"👤 Alias: {client.alias}\n"
            f"🏊 Pool: {client.pool_type}\n"
            f"📊 Status: RESETTING (Started)\n"
            f"🔛 Active: False\n"
        )
        await call.message.edit_text(
            info,
            reply_markup=keyboards.admin_client_manage(client_id)
        )
        return


async def admin_session_back(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    try:
        number = data.get("number")
        if number:
            app: SessionManager = apps.get(number)
            if app:
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
        try:
            os.remove(session_path)
        except:
            pass
        return await message.answer(
            '❌ Неверный номер или ошибка инициализации',
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
    pool_type = data.get("pool_type", "internal") # Default to internal if missing
    
    app: SessionManager = apps.get(number)
    if not app:
         return await message.answer("Ошибка: сессия не найдена. Начните заново.")

    try:
        await app.client.sign_in(
            number,
            message.text,
            phone_code_hash=hash_code
        )
        # Do not close app yet, we need it for health check
        
    except Exception as e:
        print(e)
        await app.close()
        try:
            os.remove(app.session_path)
        except:
            pass

        await state.clear()
        return await message.answer(
            '❌ Неверный код или ошибка входа',
            reply_markup=keyboards.cancel(
                data="AdminSessionNumberBack"
            )
        )

    # --- MtClient Creation Logic ---
    import time
    from main_bot.database.mt_client.model import MtClient
    
    # 1. Generate Alias
    existing_clients = await db.get_mt_clients_by_pool(pool_type)
    alias = f"{pool_type}-{len(existing_clients) + 1}"
    
    # 2. Create MtClient
    new_client = await db.create_mt_client(
        alias=alias,
        pool_type=pool_type,
        session_path=str(app.session_path),
        status='NEW',
        is_active=False
    )
    
    # 3. Health Check
    health = await app.health_check()
    current_time = int(time.time())
    
    updates = {
        "last_self_check_at": current_time
    }
    
    if health["ok"]:
        updates["status"] = 'ACTIVE'
        updates["is_active"] = True
        result_text = "✅ ACTIVE"
    else:
        updates["status"] = 'DISABLED'
        updates["is_active"] = False
        updates["last_error_code"] = health.get("error_code", "UNKNOWN")
        updates["last_error_at"] = current_time
        result_text = f"❌ ERROR: {health.get('error_code')}"
        
    await db.update_mt_client(client_id=new_client.id, **updates)
    
    await app.close()
    await state.clear()
    
    session_count = len(os.listdir("main_bot/utils/sessions/"))
    
    await message.answer(
        f"✅ Сессия добавлена!\n\n"
        f"🆔 ID: {new_client.id}\n"
        f"👤 Alias: {alias}\n"
        f"🏊 Pool: {pool_type}\n"
        f"📊 Result: {result_text}\n\n"
        f"Всего сессий: {session_count}",
        reply_markup=keyboards.admin_sessions()
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split('|')[0] == "AdminSession")
    router.callback_query.register(admin_session_back, F.data.split('|')[0] == "AdminSessionNumberBack")
    router.message.register(get_number, Session.phone, F.text)
    router.message.register(get_code, Session.code, F.text)
    return router
