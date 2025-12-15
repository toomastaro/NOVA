import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def safe_handler(stage_info: str):
    """
    Decorator to wrap handlers with try-except block and error reporting.
    
    Args:
         stage_info: A short description of the handler/step.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {stage_info}: {e}", exc_info=True)
                # Telegram reporting disabled as per user request.
                pass

        return wrapper
    return decorator
