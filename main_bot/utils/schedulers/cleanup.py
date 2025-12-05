"""
Планировщик задач для очистки данных и обслуживания системы.

Этот модуль содержит функции для:
- Проверки подписок и уведомлений пользователей
- Самопроверки MT клиентов
"""
import logging
import time
from pathlib import Path

from instance_bot import bot
from main_bot.database.db import db
from main_bot.utils.lang.language import text
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


def get_sub_status(expire_time: int) -> tuple[str | None, int | None]:
    """Получить статус подписки"""
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
    """Периодическая задача: проверка подписок и уведомления пользователей"""
    for channel in await db.get_active_channels():
        for field, text_prefix in [
            ("subscribe", "post"),
        ]:
            expire_time = getattr(channel, field)
            status, days = get_sub_status(expire_time)
            if not status:
                continue

            if status == "expired":
                msg = text(f"expire_off_sub").format(channel.emoji_id, channel.title)
                await db.update_channel_by_id(channel.id, **{field: None})
            else:
                msg = text(f"expire_sub").format(
                    channel.emoji_id,
                    channel.title,
                    days,
                    time.strftime("%d.%m.%Y", time.localtime(expire_time)),
                )

            try:
                await bot.send_message(channel.admin_id, msg)
            except Exception as e:
                logger.error(f"[{text_prefix.upper()}_NOTIFY] {channel.title}: {e}", exc_info=True)


async def mt_clients_self_check():
    """Периодическая задача: самопроверка MT клиентов"""
    from sqlalchemy import select

    from main_bot.database.mt_client.model import MtClient
    from main_bot.utils.support_log import SupportAlert, send_support_alert

    logger.info("Starting MtClient self-check")

    stmt = select(MtClient).where(MtClient.is_active == True)
    active_clients = await db.fetch(stmt)

    for client in active_clients:
        try:
            session_path = Path(client.session_path)
            if not session_path.exists():
                logger.error(
                    f"Session file not found for client {client.id}: {session_path}"
                )
                await db.update_mt_client(
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
                        manual_steps="Restore session file or delete client record.",
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
                                manual_steps="Client session is dead. Replace session file or re-login.",
                            ),
                        )

                    elif "FLOOD_WAIT" in error_code:
                        updates["status"] = "TEMP_BLOCKED"
                        try:
                            seconds = int(error_code.split("_")[-1])
                            updates["flood_wait_until"] = current_time + seconds
                        except:
                            updates["flood_wait_until"] = current_time + 300
                        updates["is_active"] = True

                        await send_support_alert(
                            bot,
                            SupportAlert(
                                event_type="CLIENT_FLOOD_WAIT",
                                client_id=client.id,
                                client_alias=client.alias,
                                pool_type=client.pool_type,
                                error_code=error_code,
                                manual_steps=f"Client is temporarily blocked for {updates['flood_wait_until'] - current_time}s. No action needed, just wait.",
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
                                manual_steps="Investigate error code. Might need manual intervention.",
                            ),
                        )

                await db.update_mt_client(client_id=client.id, **updates)

        except Exception as e:
            logger.error(f"Error checking MtClient {client.id}: {e}", exc_info=True)
            await db.update_mt_client(
                client_id=client.id,
                status="ERROR",
                last_error_code=f"CHECK_EXCEPTION_{str(e)}",
                last_error_at=int(time.time()),
                is_active=False,
            )
