"""
Модуль создания stories - главная точка входа.

Этот модуль содержит регистрацию всех хендлеров для сценария создания stories.
Логика разбита на отдельные модули по шагам FSM.
"""
from aiogram import Router, F

from main_bot.states.user import Stories

# Импорты из модулей с логикой шагов
from .media_step import get_message, cancel_message, manage_post, cancel_value, get_value
from .schedule_step import choice_channels, finish_params, choice_delete_time, cancel_send_time, get_send_time
from .save_step import accept


def get_router():
    """
    Регистрация всех хендлеров для сценария создания stories.
    
    Returns:
        Router: Роутер с зарегистрированными хендлерами
    """
    router = Router()
    
    # Ввод медиа для stories
    router.message.register(get_message, Stories.input_message, F.photo | F.video)
    router.callback_query.register(cancel_message, F.data.split("|")[0] == "InputStoryCancel")
    
    # Управление stories
    router.callback_query.register(manage_post, F.data.split("|")[0] == "ManageStory")
    
    # Редактирование параметров
    router.callback_query.register(cancel_value, F.data.split("|")[0] == "ParamCancelStories")
    router.message.register(get_value, Stories.input_value, F.photo | F.video)
    
    # Выбор каналов
    router.callback_query.register(choice_channels, F.data.split("|")[0] == "ChoiceStoriesChannels")
    
    # Финальные параметры и расписание
    router.callback_query.register(finish_params, F.data.split("|")[0] == "FinishStoriesParams")
    router.callback_query.register(choice_delete_time, F.data.split("|")[0] == "GetDeleteTimeStories")
    router.callback_query.register(cancel_send_time, F.data.split("|")[0] == "BackSendTimeStories")
    router.message.register(get_send_time, Stories.input_send_time, F.text)
    
    # Подтверждение и сохранение
    router.callback_query.register(accept, F.data.split("|")[0] == "AcceptStories")
    
    return router


__all__ = ['get_router']
