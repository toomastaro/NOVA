"""
Модуль инициализации процесса создания постов для ботов.

Реализует:
- Агрегацию роутеров для всех шагов создания поста (выбор, контент, настройки, расписание)
- Регистрацию обработчиков (handlers) для FSM процесса
"""

from aiogram import Router, F

from main_bot.states.user import Bots

# Импорты из модулей с логикой шагов
from .bot_step import choice_bots
from .media_step import (
    get_message,
    cancel_message,
    manage_post,
    cancel_value,
    get_value,
)
from .schedule_step import (
    finish_params,
    choice_delete_time,
    send_time_inline,
    get_send_time,
    back_send_time,
)
from .save_step import accept


def get_router() -> Router:
    """
    Создание и регистрация роутера для сценария создания постов.
    
    Возвращает:
        Router: Роутер с подключенными хендлерами для всех этапов создания поста.
    """
    router = Router()

    # Выбор ботов
    router.callback_query.register(
        choice_bots, F.data.split("|")[0] == "ChoicePostBots"
    )

    # Ввод сообщения для ботов
    router.message.register(
        get_message, Bots.input_message, F.text | F.photo | F.video | F.animation
    )
    router.callback_query.register(
        cancel_message, F.data.split("|")[0] == "InputBotPostCancel"
    )

    # Управление постом для ботов
    router.callback_query.register(manage_post, F.data.split("|")[0] == "ManageBotPost")

    # Редактирование параметров
    router.callback_query.register(cancel_value, F.data.split("|")[0] == "ParamCancel")
    router.message.register(
        get_value, Bots.input_value, F.text | F.photo | F.video | F.animation
    )

    # Финальные параметры и расписание
    router.callback_query.register(
        finish_params, F.data.split("|")[0] == "FinishBotPostParams"
    )
    router.callback_query.register(
        choice_delete_time, F.data.split("|")[0] == "GetDeleteTimeBotPost"
    )
    router.callback_query.register(
        send_time_inline, F.data.split("|")[0] == "SendTimeBotPost"
    )
    router.callback_query.register(
        back_send_time, F.data.split("|")[0] == "BackSendTimeBots"
    )
    router.message.register(get_send_time, Bots.input_send_time, F.text)

    # Подтверждение и сохранение
    router.callback_query.register(accept, F.data.split("|")[0] == "AcceptBotPost")

    return router


__all__ = ["get_router"]
