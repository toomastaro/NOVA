"""
Планировщик задач для очистки данных и обслуживания системы.

Этот модуль содержит функции для:
- Проверки подписок и уведомлений пользователей
- Самопроверки MT клиентов
"""
import logging
import time
from pathlib import Path

from sqlalchemy import select

from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.mt_client.model import MtClient
from main_bot.utils.lang.language import text
from main_bot.utils.session_manager import SessionManager
from main_bot.utils.support_log import SupportAlert, send_support_alert

logger = logging.getLogger(__name__)

# Хранилище отправленных уведомлений (сбрасывается при перезапуске)
_sent_notifications = set()


def get_sub_status(expire_time: int | None) -> tuple[str | None, int | None]:
    """
    Получить статус подписки на основе времени истечения.
    
    Args:
        expire_time: Unix timestamp времени истечения подписки
        
    Returns:
        Tuple из (статус, количество дней) или (None, None)
    """
    if not expire_time:
        return None, None

    delta = expire_time - time.time()

    if 86400 * 2 < delta < 86400 * 3:
        return "expire_3d", 3
    elif 0 < delta < 86400:
        return "expire_1d", 1
    elif delta < 0:
        return "expired", 0
    return None, None


async def check_subscriptions():
    """
    Периодическая задача: проверка подписок и уведомления пользователей.
    
    Проверяет все активные каналы на истечение подписки и отправляет
    уведомления пользователям за 3 дня, за 1 день и при истечении.
    """
    current_day = time.strftime("%Y-%m-%d", time.localtime())
    
    active_channels = await db.channel.get_active_channels()
    
    for channel in active_channels:
        for field, text_prefix in [("subscribe", "post")]:
            expire_time = getattr(channel, field, None)
            status, days = get_sub_status(expire_time)
            if not status:
                continue

            # Проверяем, было ли уже отправлено уведомление сегодня
            notification_key = f"{current_day}_{channel.id}_{field}_{status}"
            if notification_key in _sent_notifications:
                continue

            if status == "expired":
                msg = text("expire_off_sub").format(channel.title)
                # Сбрасываем поле подписки в БД
                await db.channel.update_channel_by_id(channel.id, **{field: None})
            else:
                formatted_date = time.strftime("%d.%m.%Y", time.localtime(expire_time))
                msg = text("expire_sub").format(channel.title, formatted_date)

            try:
                await bot.send_message(channel.admin_id, msg, parse_mode="HTML")
                # Добавляем в set отправленных уведомлений
                _sent_notifications.add(notification_key)
            except Exception as e:
                logger.error(f"Ошибка уведомления [{text_prefix.upper()}] для {channel.title}: {e}")


async def mt_clients_self_check():
    """
    Периодическая задача: самопроверка MT клиентов.
    
    Проверяет состояние всех активных MT клиентов:
    - Наличие файла сессии
    - Работоспособность клиента
    - Обработка ошибок (AUTH_KEY_UNREGISTERED, FLOOD_WAIT и т.д.)
    - Отправка алертов в поддержку при проблемах
    """
    logger.info("Запуск самопроверки MT клиентов")

    stmt = select(MtClient).where(MtClient.is_active == True)
    active_clients = await db.fetch_all(stmt)
    
    if not active_clients:
        return

    for client in active_clients:
        try:
            session_path = Path(client.session_path)
            if not session_path.exists():
                logger.error(
                    f"Файл сессии не найден для клиента {client.id}: {session_path}"
                )
                await db.mt_client.update_mt_client(
                    client_id=client.id,
                    status="ERROR",
                    last_error_code="SESSION_FILE_MISSING",
                    last_error_at=int(time.time()),
                    is_active=False,
                )

                await send_support_alert(
                    bot,
                    SupportAlert(
                        event_type="CLIENT_FILE_MISSING",
                        client_id=client.id,
                        client_alias=client.alias,
                        pool_type=client.pool_type,
                        error_code="SESSION_FILE_MISSING",
                        manual_steps="Восстановить файл сессии или удалить запись клиента.",
                    ),
                )
                continue

            async with SessionManager(session_path) as manager:
                res = await manager.health_check()

                current_time = int(time.time())
                updates = {"last_self_check_at": current_time}

                if res["ok"]:
                    updates["status"] = "ACTIVE"
                    updates["is_active"] = True
                    updates["last_error_code"] = None
                    updates["flood_wait_until"] = None
                else:
                    error_code = res.get("error_code", "UNKNOWN")
                    updates["last_error_code"] = error_code
                    updates["last_error_at"] = current_time

                    if (
                        "AUTH_KEY_UNREGISTERED" in error_code
                        or "USER_DEACTIVATED" in error_code
                    ):
                        updates["status"] = "DISABLED"
                        updates["is_active"] = False

                        await send_support_alert(
                            bot,
                            SupportAlert(
                                event_type="CLIENT_DISABLED",
                                client_id=client.id,
                                client_alias=client.alias,
                                pool_type=client.pool_type,
                                error_code=error_code,
                                manual_steps="Сессия клиента мертва. Замените файл сессии или выполните повторный вход.",
                            ),
                        )

                    elif "FLOOD_WAIT" in error_code:
                        updates["status"] = "TEMP_BLOCKED"
                        try:
                            seconds = int(error_code.split("_")[-1])
                            updates["flood_wait_until"] = current_time + seconds
                        except (ValueError, IndexError):
                            updates["flood_wait_until"] = current_time + 300
                        updates["is_active"] = True

                        wait_time = updates['flood_wait_until'] - current_time
                        await send_support_alert(
                            bot,
                            SupportAlert(
                                event_type="CLIENT_FLOOD_WAIT",
                                client_id=client.id,
                                client_alias=client.alias,
                                pool_type=client.pool_type,
                                error_code=error_code,
                                manual_steps=f"Клиент временно заблокирован на {wait_time}с. Действий не требуется.",
                            ),
                        )
                    else:
                        updates["status"] = "ERROR"
                        updates["is_active"] = False

                        await send_support_alert(
                            bot,
                            SupportAlert(
                                event_type="CLIENT_ERROR",
                                client_id=client.id,
                                client_alias=client.alias,
                                pool_type=client.pool_type,
                                error_code=error_code,
                                manual_steps="Исследуйте код ошибки. Может потребоваться ручное вмешательство.",
                            ),
                        )

                await db.mt_client.update_mt_client(client_id=client.id, **updates)

        except Exception as e:
            logger.error(f"Ошибка при проверке MT клиента {client.id}: {e}", exc_info=True)
            await db.mt_client.update_mt_client(
                client_id=client.id,
                status="ERROR",
                last_error_code=f"CHECK_EXCEPTION_{str(e)}",
                last_error_at=int(time.time()),
                is_active=False,
            )
