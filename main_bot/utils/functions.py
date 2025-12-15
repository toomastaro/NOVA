"""
УСТАРЕЛО: Этот файл устарел и будет удален в будущих версиях.

Все функции перенесены в тематические модули:
- main_bot.utils.file_utils - обработка файлов (изображения, видео)
- main_bot.utils.text_utils - работа с текстом
- main_bot.utils.message_utils - работа с сообщениями и превью
- main_bot.utils.tg_utils - Telegram API

Этот файл содержит только реэкспорты для обратной совместимости.
Пожалуйста, обновите импорты на прямые импорты из новых модулей.
"""

# Реэкспорты для обратной совместимости
from main_bot.utils.file_utils import (
    get_mode,
    get_color,
    get_path,
    get_path_video
)

from main_bot.utils.text_utils import (
    get_protect_tag
)

from main_bot.utils.message_utils import (
    answer_bot_post,
    answer_post,
    answer_story,
    answer_message_bot,
    answer_message
)

from main_bot.utils.tg_utils import (
    create_emoji,
    get_editors,
    set_channel_session,
    background_join_channel
)

# Дубликаты функций из schedulers/bots.py (УСТАРЕЛО)
# Эти функции уже есть в main_bot.utils.schedulers.bots
# Оставлены для обратной совместимости, но рекомендуется использовать из schedulers.bots
from main_bot.utils.schedulers.bots import (
    send_bot_messages,
    process_bot
)

__all__ = [
    # file_utils (утилиты файлов)
    'get_mode',
    'get_color',
    'get_path',
    'get_path_video',
    
    # text_utils (утилиты текста)
    'get_protect_tag',
    
    # message_utils (утилиты сообщений)
    'answer_bot_post',
    'answer_post',
    'answer_story',
    'answer_message_bot',
    'answer_message',
    
    # tg_utils (утилиты телеграм)
    'create_emoji',
    'get_editors',
    'set_channel_session',
    'background_join_channel',
    
    # Устарело (из schedulers.bots)
    'send_bot_messages',
    'process_bot',
]
