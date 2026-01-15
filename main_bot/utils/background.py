"""
Менеджер фоновых задач.

Обеспечивает хранение сильных ссылок на запущенные задачи asyncio,
чтобы предотвратить их удаление сборщиком мусора до завершения.
Согласно документации Python 3.11+, это критично для стабильности фоновых процессов.
"""

import asyncio
import logging
from typing import Coroutine, Set

logger = logging.getLogger(__name__)

# Хранилище ссылок на активные задачи
_background_tasks: Set[asyncio.Task] = set()


def run_background_task(coro: Coroutine, name: str = None) -> asyncio.Task:
    """
    Запускает корутину в фоне и сохраняет ссылку на задачу.
    
    Аргументы:
        coro (Coroutine): Корутина для выполнения.
        name (str): Опциональное имя задачи для логирования.
        
    Возвращает:
        asyncio.Task: Объект созданной задачи.
    """
    task = asyncio.create_task(coro, name=name)
    
    # Добавляем в набор для удержания ссылки
    _background_tasks.add(task)
    
    # Автоматическое удаление из набора после завершения
    task.add_done_callback(_background_tasks.discard)
    
    if name:
        logger.debug(f"Запущена фоновая задача: {name}")
        
    return task
