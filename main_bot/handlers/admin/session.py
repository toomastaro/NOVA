"""
Модуль управления сессиями (MtClient).

Содержит:
- Просмотр списка сессий (внутренние/внешние)
- Добавление новых сессий через номер телефона/код
- Сканирование "сиротских" файлов сессий
- Управление состоянием сессий (сброс, проверка здоровья)
- Ручное добавление найденных файлов сессий
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from aiogram import types, Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from instance_bot import bot as main_bot_obj
from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.admin import Session
from main_bot.utils.lang.language import text
from main_bot.utils.mt_client_utils import (
    reset_client_task,
    determine_pool_type,
    generate_client_alias,
)
from main_bot.utils.session_manager import SessionManager
from main_bot.utils.support_log import send_support_alert, SupportAlert
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

apps: Dict[str, SessionManager] = {}


@safe_handler("Admin Session Choice")
async def choice(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик действий с сессиями.

    Поддерживает:
    - add: выбор типа пула для добавления
    - pool_select: выбор пула
    - cancel/back_to_main: возврат в главное меню
    - internal/external: просмотр списка сессий по типу
    - scan: поиск неучтенных файлов сессий
    - manage: управление конкретной сессией
    - check_health: принудительная проверка статуса
    - reset_ask/reset_confirm: сброс сессии

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    action = temp[1]

    if action == "add":
        # Автоматическое определение пула по username после авторизации
        await call.message.edit_text(
            text("admin:session:enter_phone"),
            reply_markup=keyboards.back(data="AdminSessionNumberBack"),
        )
        return await state.set_state(Session.phone)

    if action == "cancel" or action == "back_to_main":
        # Показываем только клиенты из БД (без автосканирования)
        all_clients = await db.mt_client.get_mt_clients_by_pool(
            "internal"
        ) + await db.mt_client.get_mt_clients_by_pool("external")

        try:
            await call.message.edit_text(
                text("admin:session:main_menu").format(len(all_clients)),
                reply_markup=keyboards.admin_sessions(),
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибку если сообщение не изменилось
            if "message is not modified" not in str(e):
                logger.error(f"Error editing message: {e}")
                raise
        return

    if action in ["internal", "external"]:
        pool_type = action
        clients = await db.mt_client.get_mt_clients_by_pool(pool_type)

        # Сохраняем тип пула в состояние, чтобы вернуться к списку позже, если потребуется
        await state.update_data(current_pool=pool_type)

        await call.message.edit_text(
            text("admin:session:list").format(pool_type, len(clients)),
            reply_markup=keyboards.admin_sessions(clients=clients),
        )
        return

    if action == "back_to_list":
        data = await state.get_data()
        pool_type = data.get("current_pool", "internal")
        clients = await db.mt_client.get_mt_clients_by_pool(pool_type)
        await call.message.edit_text(
            text("admin:session:list").format(pool_type, len(clients)),
            reply_markup=keyboards.admin_sessions(clients=clients),
        )
        return

    if action == "scan":
        # Автоматическое сканирование и добавление orphaned сессий
        await call.answer("🔍 Сканирую сессии...", show_alert=False)

        all_clients = await db.mt_client.get_mt_clients_by_pool(
            "internal"
        ) + await db.mt_client.get_mt_clients_by_pool("external")
        db_session_paths = {Path(c.session_path).name for c in all_clients}

        # Сканируем директорию
        session_dir = Path("main_bot/utils/sessions/")
        orphaned = []
        if session_dir.exists():
            for file in session_dir.glob("*.session"):
                if file.name not in db_session_paths:
                    orphaned.append(file)

        if not orphaned:
            await call.answer("✅ Неучтённых сессий не найдено", show_alert=True)
            return

        # Автоматическое добавление всех найденных сессий
        added_sessions = []
        errors = []
        added_count = 0

        for session_path in orphaned:
            try:
                async with SessionManager(session_path) as manager:
                    if not manager.client:
                        errors.append(
                            f"❌ {session_path.name}: не удалось подключиться"
                        )
                        continue

                    # Получаем информацию о клиенте
                    me = await manager.me()
                    if not me:
                        errors.append(
                            f"❌ {session_path.name}: не удалось получить данные"
                        )
                        continue

                    username = me.username if me else None
                    pool_type = determine_pool_type(
                        username,
                        me.first_name if me else None,
                        me.last_name if me else None,
                    )

                    # Формируем alias
                    alias = generate_client_alias(
                        me, pool_type, len(all_clients) + added_count
                    )
                    added_count += 1

                    # Создаем клиента в БД
                    new_client = await db.mt_client.create_mt_client(
                        alias=alias,
                        pool_type=pool_type,
                        session_path=str(session_path),
                        status="NEW",
                        is_active=False,
                    )

                    # Health check
                    health = await manager.health_check()
                    current_time = int(time.time())
                    updates = {"last_self_check_at": current_time}

                    if health["ok"]:
                        updates["status"] = "ACTIVE"
                        updates["is_active"] = True
                        status_icon = "✅"
                    else:
                        updates["status"] = "DISABLED"
                        updates["is_active"] = False
                        updates["last_error_code"] = health.get("error_code", "UNKNOWN")
                        updates["last_error_at"] = current_time
                        status_icon = "❌"

                    await db.mt_client.update_mt_client(
                        client_id=new_client.id, **updates
                    )

                    added_sessions.append(
                        {
                            "file": session_path.name,
                            "alias": alias,
                            "pool": pool_type,
                            "status": status_icon,
                            "username": username or "N/A",
                        }
                    )

                    logger.info(
                        f"Автоматически добавлена сессия: {session_path.name} → {pool_type} (username: {username})"
                    )

            except Exception as e:
                logger.error(
                    f"Ошибка обработки {session_path.name}: {e}", exc_info=True
                )
                errors.append(f"❌ {session_path.name}: {str(e)[:50]}")

        # Формируем отчёт
        report = "🔍 Результаты сканирования:\n\n"

        if added_sessions:
            report += f"✅ Добавлено сессий: {len(added_sessions)}\n\n"
            for s in added_sessions:
                pool_emoji = "🏠" if s["pool"] == "internal" else "🌐"
                report += f"{s['status']} {pool_emoji} {s['alias']}\n"
                report += f"   Username: @{s['username']}\n"

        if errors:
            report += f"\n\n❌ Ошибки: {len(errors)}\n"
            for err in errors[:5]:  # Показываем только первые 5 ошибок
                report += f"{err}\n"
            if len(errors) > 5:
                report += f"... и ещё {len(errors) - 5}\n"

        if not added_sessions and not errors:
            report = "✅ Все сессии уже добавлены в систему"

        await call.message.edit_text(
            report, reply_markup=keyboards.back(data="AdminSession|back_to_main")
        )
        return

    if action == "manage":
        client_id = int(temp[2])
        client = await db.mt_client.get_mt_client(client_id)
        if not client:
            await call.answer(text("admin:session:not_found"), show_alert=True)
            return

        created_at = "N/A"
        if client.created_at:
            created_at = datetime.fromtimestamp(client.created_at).strftime(
                "%d.%m.%Y %H:%M"
            )

        last_check = "N/A"
        if client.last_self_check_at:
            last_check = datetime.fromtimestamp(client.last_self_check_at).strftime(
                "%d.%m.%Y %H:%M"
            )

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
            error_time = (
                datetime.fromtimestamp(client.last_error_at).strftime("%d.%m.%Y %H:%M")
                if client.last_error_at
                else "N/A"
            )
            info += f"❌ Последняя ошибка: {client.last_error_code} ({error_time})\n"
        if client.flood_wait_until:
            flood_time = datetime.fromtimestamp(client.flood_wait_until).strftime(
                "%d.%m.%Y %H:%M"
            )
            info += f"⏳ Флуд до: {flood_time}\n"

        await call.message.edit_text(
            info,
            reply_markup=keyboards.admin_client_manage(client_id, client.pool_type),
        )
        return

    if action == "check_health":
        client_id = int(temp[2])
        client = await db.mt_client.get_mt_client(client_id)
        if not client:
            await call.answer(text("admin:session:not_found"), show_alert=True)
            return

        session_path = Path(client.session_path)
        if not session_path.exists():
            await call.answer(text("admin:session:session_not_found"), show_alert=True)
            return

        # Защита от множественных вызовов (debounce)
        data = await state.get_data()
        last_check_key = f"last_health_check_{client_id}"
        last_check = data.get(last_check_key, 0)
        current_time = int(time.time())

        if current_time - last_check < 5:  # 5 секунд между проверками
            await call.answer(text("admin:session:wait_check"), show_alert=True)
            return

        await state.update_data(**{last_check_key: current_time})

        await call.answer(text("admin:session:checking"), show_alert=False)

        async with SessionManager(session_path) as manager:
            health = await manager.health_check()

        current_time = int(time.time())
        updates = {"last_self_check_at": current_time}

        if health["ok"]:
            updates["status"] = "ACTIVE"
            updates["is_active"] = True
            msg = text("admin:session:active")

            # Синхронизация имени/юзернейма
            me = health.get("me")
            if me:
                new_alias = generate_client_alias(me, client.pool_type)
                if new_alias and new_alias != client.alias:
                    updates["alias"] = new_alias
                    logger.info(
                        f"Синхронизация клиента {client.id}: {client.alias} -> {new_alias}"
                    )
        else:
            updates["status"] = "DISABLED"
            updates["is_active"] = False
            error_code = health.get("error_code", "UNKNOWN")
            updates["last_error_code"] = error_code
            updates["last_error_at"] = current_time
            msg = text("admin:session:error").format(error_code)

            # Send alert for critical errors
            if (
                "DEACTIVATED" in error_code
                or "UNREGISTERED" in error_code
                or "BANNED" in error_code
            ):
                event_type = (
                    "CLIENT_BANNED"
                    if "BANNED" in error_code or "DEACTIVATED" in error_code
                    else "CLIENT_DISABLED"
                )

                await send_support_alert(
                    main_bot_obj,
                    SupportAlert(
                        event_type=event_type,
                        client_id=client.id,
                        client_alias=client.alias,
                        pool_type=client.pool_type,
                        error_code=error_code,
                        error_text=text("admin:session:health_failed"),
                    ),
                )

        await db.mt_client.update_mt_client(client_id=client.id, **updates)

        # Refresh view with updated data
        client = await db.mt_client.get_mt_client(
            client_id
        )  # Получаем обновленные данные

        created_at = "N/A"
        if client.created_at:
            created_at = datetime.fromtimestamp(client.created_at).strftime(
                "%d.%m.%Y %H:%M"
            )

        last_check = "N/A"
        if client.last_self_check_at:
            last_check = datetime.fromtimestamp(client.last_self_check_at).strftime(
                "%d.%m.%Y %H:%M"
            )

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
            error_time = (
                datetime.fromtimestamp(client.last_error_at).strftime("%d.%m.%Y %H:%M")
                if client.last_error_at
                else "N/A"
            )
            info += f"❌ Последняя ошибка: {client.last_error_code} ({error_time})\n"
        if client.flood_wait_until:
            flood_time = datetime.fromtimestamp(client.flood_wait_until).strftime(
                "%d.%m.%Y %H:%M"
            )
            info += f"⏳ Флуд до: {flood_time}\n"

        await call.message.edit_text(
            info,
            reply_markup=keyboards.admin_client_manage(client_id, client.pool_type),
        )
        await call.answer(msg, show_alert=True)
        return

    if action == "reset_ask":
        client_id = int(temp[2])
        await call.message.edit_text(
            text("admin:session:reset_confirm").format(client_id),
            reply_markup=keyboards.admin_client_reset_confirm(client_id),
        )
        return

    if action == "reset_confirm":
        client_id = int(temp[2])

        # Trigger background task
        asyncio.create_task(reset_client_task(client_id))

        await call.answer(text("admin:session:reset_started"), show_alert=True)

        # Go back to client details (it will update status on next refresh)
        client = await db.mt_client.get_mt_client(client_id)
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
            reply_markup=keyboards.admin_client_manage(client_id, client.pool_type),
        )
        return

    if action == "move_pool":
        client_id = int(temp[2])
        new_pool = temp[3]

        client = await db.mt_client.get_mt_client(client_id)
        if not client:
            await call.answer(text("admin:session:not_found"), show_alert=True)
            return

        await db.mt_client.update_mt_client(client_id=client_id, pool_type=new_pool)
        await call.answer(
            f"✅ Клиент перенесен в пул {new_pool.upper()}", show_alert=True
        )

        # Обновляем вид
        client = await db.mt_client.get_mt_client(client_id)

        created_at = "N/A"
        if client.created_at:
            created_at = datetime.fromtimestamp(client.created_at).strftime(
                "%d.%m.%Y %H:%M"
            )

        last_check = "N/A"
        if client.last_self_check_at:
            last_check = datetime.fromtimestamp(client.last_self_check_at).strftime(
                "%d.%m.%Y %H:%M"
            )

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
            error_time = (
                datetime.fromtimestamp(client.last_error_at).strftime("%d.%m.%Y %H:%M")
                if client.last_error_at
                else "N/A"
            )
            info += f"❌ Последняя ошибка: {client.last_error_code} ({error_time})\n"

        await call.message.edit_text(
            info,
            reply_markup=keyboards.admin_client_manage(client_id, client.pool_type),
        )
        return


@safe_handler("Admin Session Back")
async def admin_session_back(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Возврат назад из процесса добавления сессии.
    Удаляет временные файлы сессий, если они были созданы.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()

    try:
        number = data.get("number")
        if number:
            app: Optional[SessionManager] = apps.get(number)
            if app:
                if isinstance(app.session_path, (str, Path)) and os.path.exists(
                    app.session_path
                ):
                    os.remove(app.session_path)
                await app.close()
    except Exception as e:
        logger.error(f"Error removing session during back: {e}")

    await state.clear()

    # Получаем все сессии из базы данных (без автосканирования)
    all_clients = await db.mt_client.get_mt_clients_by_pool(
        "internal"
    ) + await db.mt_client.get_mt_clients_by_pool("external")

    await call.message.delete()
    await call.message.answer(
        text("admin:session:main_menu").format(len(all_clients)),
        reply_markup=keyboards.admin_sessions(),
    )


@safe_handler("Admin Session Get Number")
async def get_number(message: types.Message, state: FSMContext) -> None:
    """
    Получение номера телефона для новой сессии.
    Инициализирует SessionManager и запрашивает код подтверждения.

    Аргументы:
        message (types.Message): Сообщение с номером телефона.
        state (FSMContext): Контекст состояния.
    """
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
        logger.error(f"Error sending code request: {e}")
        await manager.close()
        try:
            if session_path.exists():
                os.remove(session_path)
        except Exception:
            pass
        await message.answer(
            text("admin:session:init_error"),
            reply_markup=keyboards.cancel(data="AdminSessionNumberBack"),
        )
        return

    await state.update_data(
        hash_code=code.phone_code_hash,
        number=number,
    )

    await message.answer(
        text("admin:session:enter_code"),
        reply_markup=keyboards.cancel(data="AdminSessionNumberBack"),
    )
    await state.set_state(Session.code)


@safe_handler("Admin Session Get Code")
async def get_code(message: types.Message, state: FSMContext) -> None:
    """
    Получение кода подтверждения и завершение авторизации.
    Создает запись MtClient в БД.

    Аргументы:
        message (types.Message): Сообщение с кодом.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    number = data.get("number")
    hash_code = data.get("hash_code")

    app: Optional[SessionManager] = apps.get(number)
    if not app:
        await message.answer(text("admin:session:session_lost"))
        return

    try:
        await app.client.sign_in(number, message.text, phone_code_hash=hash_code)
        # Пока не закрываем приложение, оно нужно для проверки здоровья (health check)

    except Exception as e:
        logger.error(f"Error signing in: {e}")
        await app.close()
        try:
            if isinstance(app.session_path, (str, Path)) and os.path.exists(
                app.session_path
            ):
                os.remove(app.session_path)
        except Exception:
            pass

        await state.clear()
        await message.answer(
            text("admin:session:auth_error"),
            reply_markup=keyboards.cancel(data="AdminSessionNumberBack"),
        )
        return

    # --- MtClient Creation Logic ---

    # 1. Получить username и автоматически определить пул
    pool_type = "internal"  # По умолчанию
    alias = None
    username = None

    try:
        me = await app.me()
        if me:
            # Получаем данные для определения пула
            username = me.username if me else None
            pool_type = determine_pool_type(
                username,
                me.first_name if me else None,
                me.last_name if me else None,
            )

            logger.info(
                f"Автоопределение пула для сессии {number}: "
                f"username=@{username or 'N/A'}, pool={pool_type}"
            )

            # Формат alias: 👤 Имя Фамилия (@username)
            alias = generate_client_alias(me, pool_type)
    except Exception as e:
        logger.error(f"Error getting user info: {e}")

    # Fallback: если не удалось получить имя
    if not alias:
        existing_clients = await db.mt_client.get_mt_clients_by_pool(pool_type)
        alias = f"{pool_type}-{len(existing_clients) + 1}"

    # 2. Создание MtClient
    new_client = await db.mt_client.create_mt_client(
        alias=alias,
        pool_type=pool_type,
        session_path=str(app.session_path),
        status="NEW",
        is_active=False,
    )

    # 3. Проверка здоровья (Health Check)
    health = await app.health_check()
    current_time = int(time.time())

    updates = {"last_self_check_at": current_time}

    if health["ok"]:
        updates["status"] = "ACTIVE"
        updates["is_active"] = True
        result_text = "✅ ACTIVE"
    else:
        updates["status"] = "DISABLED"
        updates["is_active"] = False
        updates["last_error_code"] = health.get("error_code", "UNKNOWN")
        updates["last_error_at"] = current_time
        result_text = f"❌ ERROR: {health.get('error_code')}"

    await db.mt_client.update_mt_client(client_id=new_client.id, **updates)

    await app.close()
    await state.clear()

    session_dir = "main_bot/utils/sessions/"
    session_count = len(os.listdir(session_dir)) if os.path.exists(session_dir) else 0

    await message.answer(
        text("admin:session:success_add").format(
            new_client.id, alias, pool_type, result_text, session_count
        ),
        reply_markup=keyboards.admin_sessions(),
    )


def get_router() -> Router:
    """
    Регистрация роутера для управления сессиями.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "AdminSession")
    router.callback_query.register(
        admin_session_back, F.data.split("|")[0] == "AdminSessionNumberBack"
    )
    router.message.register(get_number, Session.phone, F.text)
    router.message.register(get_code, Session.code, F.text)
    return router
