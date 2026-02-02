"""
Модуль создания поста - главная точка входа.

Этот модуль содержит регистрацию всех хендлеров для сценария создания поста.
Логика разбита на отдельные модули по шагам FSM.
"""

from aiogram import Router, F

from main_bot.states.user import Posting, AddHide

# Импорты из модулей с логикой шагов
from .text_step import get_message, cancel_message
from .media_step import manage_post, cancel_value, get_value
from .links_step import (
    add_hide_value,
    back_input_button_name,
    get_button_name,
    get_not_member_text,
    get_for_member_text,
    click_hide,
    click_react,
)

from .choose_folder import choice_channels
from .schedule_step import (
    finish_params,
    choice_delete_time,
    cancel_send_time,
    get_send_time,
    choice_publication_date,
    choice_publication_time,
)
from .save_step import accept


def get_router():
    """
    Регистрация всех хендлеров для сценария создания поста.

    Returns:
        Router: Роутер с зарегистрированными хендлерами
    """
    router = Router()

    # Ввод сообщения
    router.message.register(
        get_message, Posting.input_message, F.text | F.photo | F.video | F.animation
    )
    router.callback_query.register(
        cancel_message, F.data.split("|")[0] == "InputPostCancel"
    )

    # Управление постом
    router.callback_query.register(manage_post, F.data.split("|")[0] == "ManagePost")

    # Редактирование параметров
    router.callback_query.register(cancel_value, F.data.split("|")[0] == "ParamCancel")
    router.message.register(
        get_value, Posting.input_value, F.text | F.photo | F.video | F.animation
    )

    # Hide кнопки
    router.callback_query.register(add_hide_value, F.data.split("|")[0] == "ParamHide")
    router.callback_query.register(
        back_input_button_name, F.data.split("|")[0] == "BackButtonHide"
    )
    router.message.register(get_button_name, AddHide.button_name, F.text)
    router.message.register(get_not_member_text, AddHide.not_member_text, F.text)
    router.message.register(get_for_member_text, AddHide.for_member_text, F.text)

    # Выбор каналов
    router.callback_query.register(
        choice_channels, F.data.split("|")[0] == "ChoicePostChannels"
    )

    # Финальные параметры и расписание
    router.callback_query.register(
        finish_params, F.data.split("|")[0] == "FinishPostParams"
    )
    router.callback_query.register(
        choice_delete_time, F.data.split("|")[0] == "GetDeleteTimePost"
    )
    router.callback_query.register(
        cancel_send_time, F.data.split("|")[0] == "BackSendTimePost"
    )
    router.message.register(get_send_time, Posting.input_send_time, F.text)

    # Календарь
    router.callback_query.register(
        choice_publication_date, F.data.split("|")[0] == "ChoicePublicationDate"
    )
    router.callback_query.register(
        choice_publication_time, F.data.split("|")[0] == "ChoicePublicationTime"
    )

    # Подтверждение и сохранение
    router.callback_query.register(accept, F.data.split("|")[0] == "AcceptPost")

    # Клики на кнопках
    router.callback_query.register(click_hide, F.data.split("|")[0] == "ClickHide")
    router.callback_query.register(click_react, F.data.split("|")[0] == "ClickReact")

    return router


__all__ = ["get_router"]
