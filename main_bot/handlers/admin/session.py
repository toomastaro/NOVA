import os
import time
from datetime import datetime
from pathlib import Path

from aiogram.fsm.context import FSMContext
from aiogram import types, Router, F
from aiogram.exceptions import TelegramBadRequest

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
        # Показываем только клиенты из БД (без автосканирования)
        all_clients = await db.get_mt_clients_by_pool('internal') + await db.get_mt_clients_by_pool('external')
        
        try:
            await call.message.edit_text(
                f"Управление MTProto клиентами\nВсего в базе: {len(all_clients)}",
                reply_markup=keyboards.admin_sessions()
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибку если сообщение не изменилось
            if "message is not modified" not in str(e):
                raise
        return

    if action in ['internal', 'external']:
        pool_type = action
        clients = await db.get_mt_clients_by_pool(pool_type)
        
        # Store pool type in state to return to list later if needed
        await state.update_data(current_pool=pool_type)

        # Also scan for orphans to show them mixed or at top? 
        # Requirement says: "if there are such that are not in the database... offer to add them"
        # It seems better to show orphans on the main screen or mixed. 
        # Let's keep orphans on the main screen (back_to_main) as implemented above.
        # Here we just show the specific pool list.

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

    if action == 'scan':
        # Ручное сканирование orphaned сессий
        all_clients = await db.get_mt_clients_by_pool('internal') + await db.get_mt_clients_by_pool('external')
        db_session_paths = {Path(c.session_path).name for c in all_clients}
        
        # Сканируем директорию
        session_dir = Path("main_bot/utils/sessions/")
        orphaned = []
        if session_dir.exists():
            for file in session_dir.glob("*.session"):
                if file.name not in db_session_paths:
                    orphaned.append(file.name)
        
        if orphaned:
            await call.message.edit_text(
                f"🔍 Найдено новых сессий: {len(orphaned)}\nВыберите сессию для добавления:",
                reply_markup=keyboards.admin_sessions(orphaned_sessions=orphaned)
            )
        else:
            await call.answer("✅ Новых сессий не найдено", show_alert=True)
        return


    if action == 'add_orphan':
        session_file = temp[2]
        await call.message.edit_text(
            f"Добавление найденной сессии: {session_file}\nВыберите тип пула:",
            reply_markup=keyboards.admin_orphan_pool_select(session_file)
        )
        return

    if action == 'orphan_pool':
        pool_type = temp[2]
        session_file = temp[3]
        session_path = Path(f"main_bot/utils/sessions/{session_file}")
        
        if not session_path.exists():
             await call.answer("Файл сессии исчез!", show_alert=True)
             return

        # Create MtClient
        import time
        from main_bot.database.mt_client.model import MtClient
        
        # Получить имя из профиля через SessionManager
        alias = None
        async with SessionManager(session_path) as manager:
            if manager.client:
                try:
                    me = await manager.me()
                    if me:
                        # Формат: "👤 Имя Фамилия"
                        first_name = me.first_name or ""
                        last_name = me.last_name or ""
                        full_name = f"{first_name} {last_name}".strip()
                        if full_name:
                            alias = f"👤 {full_name}"
                except Exception as e:
                    print(f"Error getting user info: {e}")
            
            # Fallback: если не удалось получить имя
            if not alias:
                existing_clients = await db.get_mt_clients_by_pool(pool_type)
                alias = f"{pool_type}-{len(existing_clients) + 1}"
        
        new_client = await db.create_mt_client(
            alias=alias,
            pool_type=pool_type,
            session_path=str(session_path),
            status='NEW',
            is_active=False
        )
        
        # Health Check
        async with SessionManager(session_path) as manager:
            health = await manager.health_check()
            
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
        
        await call.message.edit_text(
            f"✅ Сессия {session_file} добавлена!\n\n"
            f"🆔 ID: {new_client.id}\n"
            f"👤 Псевдоним: {alias}\n"
            f"🏊 Пул: {pool_type}\n"
            f"📊 Результат: {result_text}",
            reply_markup=keyboards.back(data="AdminSession|back_to_main")
        )
        return

    if action == 'manage':
        client_id = int(temp[2])
        client = await db.get_mt_client(client_id)
        if not client:
            await call.answer("Клиент не найден", show_alert=True)
            return

        created_at = "N/A"
        if client.created_at:
             created_at = datetime.fromtimestamp(client.created_at).strftime("%d.%m.%Y %H:%M")
             
        last_check = "N/A"
        if client.last_self_check_at:
            last_check = datetime.fromtimestamp(client.last_self_check_at).strftime("%d.%m.%Y %H:%M")

        info = (
            f"🆔 ID: {client.id}\n"
            f"👤 Псевдоним: {client.alias}\n"
            f"🏊 Пул: {client.pool_type}\n"
            f"📊 Статус: {client.status}\n"
            f"🔛 Активен: {client.is_active}\n"
            f"📅 Создан: {created_at}\n"
            f"🕒 Последняя проверка: {last_check}\n"
        )
        if client.last_error_code:
            error_time = datetime.fromtimestamp(client.last_error_at).strftime("%d.%m.%Y %H:%M") if client.last_error_at else "N/A"
            info += f"❌ Последняя ошибка: {client.last_error_code} ({error_time})\n"
        if client.flood_wait_until:
            flood_time = datetime.fromtimestamp(client.flood_wait_until).strftime("%d.%m.%Y %H:%M")
            info += f"⏳ Флуд до: {flood_time}\n"

        await call.message.edit_text(
            info,
            reply_markup=keyboards.admin_client_manage(client_id)
        )
        return

    if action == 'check_health':
        client_id = int(temp[2])
        client = await db.get_mt_client(client_id)
        if not client:
            await call.answer("Клиент не найден", show_alert=True)
            return
            
        session_path = Path(client.session_path)
        if not session_path.exists():
             await call.answer("Файл сессии не найден!", show_alert=True)
             return

        # Защита от множественных вызовов (debounce)
        data = await state.get_data()
        last_check_key = f"last_health_check_{client_id}"
        last_check = data.get(last_check_key, 0)
        current_time = int(time.time())
        
        if current_time - last_check < 5:  # 5 секунд между проверками
            await call.answer("⏳ Подождите 5 секунд между проверками", show_alert=True)
            return
        
        await state.update_data(**{last_check_key: current_time})

        await call.answer("Проверка...", show_alert=False)
        
        async with SessionManager(session_path) as manager:
            health = await manager.health_check()
            
        current_time = int(time.time())
        updates = {
            "last_self_check_at": current_time
        }
        
        if health["ok"]:
            updates["status"] = 'ACTIVE'
            updates["is_active"] = True
            msg = "✅ Клиент активен"
        else:
            updates["status"] = 'DISABLED'
            updates["is_active"] = False
            error_code = health.get("error_code", "UNKNOWN")
            updates["last_error_code"] = error_code
            updates["last_error_at"] = current_time
            msg = f"❌ Ошибка: {error_code}"
            
            # Send alert for critical errors
            if "DEACTIVATED" in error_code or "UNREGISTERED" in error_code or "BANNED" in error_code:
                from main_bot.utils.support_log import send_support_alert, SupportAlert
                from instance_bot import bot as main_bot_obj
                
                event_type = 'CLIENT_BANNED' if 'BANNED' in error_code or 'DEACTIVATED' in error_code else 'CLIENT_DISABLED'
                
                await send_support_alert(main_bot_obj, SupportAlert(
                    event_type=event_type,
                    client_id=client.id,
                    client_alias=client.alias,
                    pool_type=client.pool_type,
                    error_code=error_code,
                    error_text=f"Клиент не прошел проверку здоровья"
                ))
            
        await db.update_mt_client(client_id=client.id, **updates)
        
        # Refresh view with updated data
        client = await db.get_mt_client(client_id)  # Получаем обновленные данные
        
        created_at = "N/A"
        if client.created_at:
             created_at = datetime.fromtimestamp(client.created_at).strftime("%d.%m.%Y %H:%M")
             
        last_check = "N/A"
        if client.last_self_check_at:
            last_check = datetime.fromtimestamp(client.last_self_check_at).strftime("%d.%m.%Y %H:%M")

        info = (
            f"🆔 ID: {client.id}\n"
            f"👤 Псевдоним: {client.alias}\n"
            f"🏊 Пул: {client.pool_type}\n"
            f"📊 Статус: {client.status}\n"
            f"🔛 Активен: {client.is_active}\n"
            f"📅 Создан: {created_at}\n"
            f"🕒 Последняя проверка: {last_check}\n"
        )
        if client.last_error_code:
            error_time = datetime.fromtimestamp(client.last_error_at).strftime("%d.%m.%Y %H:%M") if client.last_error_at else "N/A"
            info += f"❌ Последняя ошибка: {client.last_error_code} ({error_time})\n"
        if client.flood_wait_until:
            flood_time = datetime.fromtimestamp(client.flood_wait_until).strftime("%d.%m.%Y %H:%M")
            info += f"⏳ Флуд до: {flood_time}\n"

        await call.message.edit_text(
            info,
            reply_markup=keyboards.admin_client_manage(client_id)
        )
        await call.answer(msg, show_alert=True)
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
            f"👤 Псевдоним: {client.alias}\n"
            f"🏊 Пул: {client.pool_type}\n"
            f"📊 Статус: СБРОС (Запущен)\n"
            f"🔛 Активен: False\n"
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
    
    # Получаем все сессии из базы данных (без автосканирования)
    all_clients = await db.get_mt_clients_by_pool('internal') + await db.get_mt_clients_by_pool('external')

    await call.message.delete()
    await call.message.answer(
        f"Управление MTProto клиентами\nВсего в базе: {len(all_clients)}",
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
    
    # 1. Получить имя из профиля
    alias = None
    try:
        me = await app.me()
        if me:
            # Формат: "👤 Имя Фамилия"
            first_name = me.first_name or ""
            last_name = me.last_name or ""
            full_name = f"{first_name} {last_name}".strip()
            if full_name:
                alias = f"👤 {full_name}"
    except Exception as e:
        print(f"Error getting user info: {e}")
    
    # Fallback: если не удалось получить имя
    if not alias:
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
        f"👤 Псевдоним: {alias}\n"
        f"🏊 Пул: {pool_type}\n"
        f"📊 Результат: {result_text}\n\n"
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
