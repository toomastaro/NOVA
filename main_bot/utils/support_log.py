"""
Модуль для отправки алертов в служебный канал поддержки.
Отслеживает критические ошибки работы Нова помощников.
"""
import time
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Конфигурация
SUPPORT_CHANNEL_ID = -1002049832561
ALERT_SPAM_PROTECTION_HOURS = 6

# In-memory кэш для защиты от спама
# Структура: {cache_key: last_sent_timestamp}
_alert_cache: dict[str, int] = {}


class SupportAlert(BaseModel):
    """Структура алерта для служебного канала"""
    event_type: str  # например 'INTERNAL_ACCESS_LOST'
    client_id: Optional[int] = None
    client_alias: Optional[str] = None
    pool_type: Optional[str] = None
    channel_id: Optional[int] = None
    channel_username: Optional[str] = None
    is_our_channel: Optional[bool] = None
    task_id: Optional[int] = None
    task_type: Optional[str] = None
    error_code: Optional[str] = None
    error_text: Optional[str] = None
    manual_steps: Optional[str] = None


def _get_cache_key(alert: SupportAlert) -> str:
    """Генерирует ключ для кэша на основе алерта"""
    return f"{alert.client_id}_{alert.channel_id}_{alert.event_type}_{alert.error_code}"


def _should_send_alert(alert: SupportAlert) -> bool:
    """
    Проверяет, нужно ли отправлять алерт (защита от спама).
    Возвращает True, если алерт можно отправить.
    """
    cache_key = _get_cache_key(alert)
    current_time = int(time.time())
    ttl_seconds = ALERT_SPAM_PROTECTION_HOURS * 3600
    
    # Очистка устаревших записей
    expired_keys = [
        key for key, timestamp in _alert_cache.items()
        if current_time - timestamp > ttl_seconds
    ]
    for key in expired_keys:
        del _alert_cache[key]
    
    # Проверка на дубликат
    if cache_key in _alert_cache:
        last_sent = _alert_cache[cache_key]
        if current_time - last_sent < ttl_seconds:
            return False  # Алерт уже отправлялся недавно
    
    # Обновляем кэш
    _alert_cache[cache_key] = current_time
    return True


def _get_event_emoji(event_type: str) -> str:
    """Возвращает эмодзи для типа события"""
    emoji_map = {
        'INTERNAL_ACCESS_LOST': '🚫',
        'STORIES_PERMISSION_DENIED': '📸',
        'STATS_ACCESS_DENIED': '📊',
        'CLIENT_DISABLED': '⚠️',
        'CLIENT_BANNED': '🔴',
    }
    return emoji_map.get(event_type, '🚨')


def _get_manual_steps(alert: SupportAlert) -> str:
    """Генерирует инструкции для ручного исправления"""
    if alert.manual_steps:
        return alert.manual_steps
    
    steps = {
        'INTERNAL_ACCESS_LOST': f"""1. Проверьте, что клиент {alert.client_alias or alert.client_id} добавлен в канал {alert.channel_username or alert.channel_id}
2. Убедитесь, что клиент не был удален администратором
3. Попробуйте выполнить "Check Health" для клиента в админ-панели
4. Если не помогло - выполните Reset и добавьте клиента заново""",
        
        'STORIES_PERMISSION_DENIED': f"""1. Откройте канал {alert.channel_username or alert.channel_id} в Telegram
2. Найдите клиента {alert.client_alias or alert.client_id} в списке администраторов
3. Выдайте права: "Управление историями", "Публикация историй", "Удаление историй"
4. Выполните "Check Health" для клиента в админ-панели""",
        
        'STATS_ACCESS_DENIED': f"""1. Проверьте настройки приватности канала {alert.channel_username or alert.channel_id}
2. Убедитесь, что external клиент {alert.client_alias or alert.client_id} подписан на канал
3. Проверьте, что статистика канала доступна администраторам
4. Если канал приватный - добавьте клиента как участника""",
        
        'CLIENT_DISABLED': f"""1. Проверьте статус клиента {alert.client_alias or alert.client_id} в админ-панели
2. Посмотрите код ошибки: {alert.error_code or 'N/A'}
3. Если AUTH_KEY_UNREGISTERED - клиент разлогинен, нужна повторная авторизация
4. Если USER_DEACTIVATED - аккаунт заблокирован, замените клиента
5. Попробуйте выполнить "Check Health" или добавьте новую сессию""",
        
        'CLIENT_BANNED': f"""1. Клиент {alert.client_alias or alert.client_id} заблокирован Telegram
2. Проверьте статус аккаунта
3. Замените клиента на новый
4. Удалите старый клиент из базы данных""",
    }
    
    return steps.get(alert.event_type, "Обратитесь к документации или разработчику")


def _format_alert_message(alert: SupportAlert) -> str:
    """Форматирует сообщение алерта"""
    emoji = _get_event_emoji(alert.event_type)
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    # Заголовок
    message = f"{emoji} <b>{alert.event_type}</b>\n\n"
    
    # Информация о клиенте
    if alert.client_id or alert.client_alias or alert.pool_type:
        message += "📋 <b>Клиент:</b>\n"
        if alert.client_id:
            message += f"  • ID: <code>{alert.client_id}</code>\n"
        if alert.client_alias:
            message += f"  • Alias: <code>{alert.client_alias}</code>\n"
        if alert.pool_type:
            message += f"  • Pool: <code>{alert.pool_type}</code>\n"
        message += "\n"
    
    # Информация о канале
    if alert.channel_id or alert.channel_username:
        message += "📢 <b>Канал:</b>\n"
        if alert.channel_id:
            message += f"  • ID: <code>{alert.channel_id}</code>\n"
        if alert.channel_username:
            message += f"  • Username: @{alert.channel_username}\n"
        if alert.is_our_channel is not None:
            message += f"  • Наш канал: {'✅ Да' if alert.is_our_channel else '❌ Нет'}\n"
        message += "\n"
    
    # Информация о задаче
    if alert.task_id or alert.task_type:
        message += "📝 <b>Задача:</b>\n"
        if alert.task_id:
            message += f"  • ID: <code>{alert.task_id}</code>\n"
        if alert.task_type:
            message += f"  • Type: <code>{alert.task_type}</code>\n"
        message += "\n"
    
    # Ошибка
    if alert.error_code or alert.error_text:
        message += "❌ <b>Ошибка:</b>\n"
        if alert.error_code:
            message += f"  • Код: <code>{alert.error_code}</code>\n"
        if alert.error_text:
            message += f"  • Текст: {alert.error_text}\n"
        message += "\n"
    
    # Инструкции
    manual_steps = _get_manual_steps(alert)
    message += f"🔧 <b>Действия:</b>\n{manual_steps}\n\n"
    
    # Время
    message += f"⏰ {timestamp}"
    
    return message


async def send_support_alert(bot: Bot, alert: SupportAlert) -> None:
    """
    Отправляет алерт в служебный канал поддержки.
    
    Args:
        bot: Экземпляр aiogram Bot
        alert: Структура алерта
    """
    # Проверка на спам
    if not _should_send_alert(alert):
        logger.info(f"Алерт {alert.event_type} для {alert.client_id} пропущен (spam protection)")
        return
    
    # Форматирование сообщения
    message = _format_alert_message(alert)
    
    # Отправка
    try:
        await bot.send_message(
            chat_id=SUPPORT_CHANNEL_ID,
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"Отправлен алерт поддержки: {alert.event_type}")
    except Exception as e:
        # Логируем ошибку, но не падаем
        logger.error(f"Не удалось отправить алерт поддержки: {e}", exc_info=True)
