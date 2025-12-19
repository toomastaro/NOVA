import asyncio
from typing import Dict, Tuple

class CaptchaEventManager:
    """
    Менеджер событий для уведомления о прохождении капчи.
    Позволяет избежать постоянного опроса (polling) базы данных.
    """
    def __init__(self):
        # Ключ: (schema, user_id)
        self._events: Dict[Tuple[str, int], asyncio.Event] = {}

    def _get_key(self, schema: str, user_id: int) -> Tuple[str, int]:
        return (schema, user_id)

    def get_event(self, schema: str, user_id: int) -> asyncio.Event:
        """Получает или создает событие для конкретного пользователя в схеме."""
        key = self._get_key(schema, user_id)
        if key not in self._events:
            self._events[key] = asyncio.Event()
        return self._events[key]

    def notify(self, schema: str, user_id: int):
        """Уведомляет (устанавливает событие), что пользователь прошел капчу."""
        key = self._get_key(schema, user_id)
        if key in self._events:
            self._events[key].set()
            # Удаляем событие из памяти после уведомления, 
            # так как оно больше не нужно (одноразовый сигнал)
            # Примечание: если несколько задач ждут одно событие, 
            # они все проснутся при .set()
            del self._events[key]

    async def wait_for(self, schema: str, user_id: int, timeout: float = None) -> bool:
        """
        Ожидает прохождения капчи.
        
        Returns:
            bool: True если событие произошло, False если вышел таймаут.
        """
        event = self.get_event(schema, user_id)
        try:
            if timeout:
                await asyncio.wait_for(event.wait(), timeout=timeout)
                return True
            else:
                await event.wait()
                return True
        except asyncio.TimeoutError:
            return False

# Глобальный экземпляр менеджера
event_manager = CaptchaEventManager()
