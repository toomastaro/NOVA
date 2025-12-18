"""
Утилитарные функции общего назначения.

Содержит функции для работы с изображениями и стикерами (создание эмодзи).
"""

import os
import random
import string
import logging

from aiogram import types
from PIL import Image, ImageDraw, ImageFilter

from instance_bot import bot

logger = logging.getLogger(__name__)


async def create_emoji(user_id: int, photo_bytes=None) -> str:
    """
    Создает кастомный эмодзи из фото пользователя (ОТКЛЮЧЕНО).
    """
    return "5393222813345663485"
