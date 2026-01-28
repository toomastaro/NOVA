"""
Pydantic схемы для валидации данных и типов API.

Содержит модели для:
- Опций сообщений и сторис
- Кнопок (скрытие, реакции)
- Приветствий и капчи
"""

from typing import Optional, List

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from pydantic import BaseModel


class Media(BaseModel):
    file_id: str


class MessageOptions(BaseModel):
    animation: Optional[Media | str] = None
    video: Optional[Media | str] = None
    photo: Optional[Media | str] = None
    show_caption_above_media: Optional[bool] = None
    caption: Optional[str] = None
    text: Optional[str] = None
    html_text: Optional[str] = None # Унифицированный HTML контент
    media_value: Optional[str] = None # file_id или URL
    media_type: Optional[str] = None # photo, video, animation, text
    is_invisible: bool = False # Флаг метода Invisible Link
    has_spoiler: bool = False
    disable_web_page_preview: bool = True
    disable_notification: bool = False
    buttons: Optional[dict | str | list] = None
    reaction: Optional[dict] = None


class StoryOptions(BaseModel):
    video: Optional[Media | str] = None
    photo: Optional[Media | str] = None
    caption: Optional[str] = None
    noforwards: Optional[bool] = False
    pinned: Optional[bool] = False
    period: Optional[int] = 86400


class HideRow(BaseModel):
    id: int
    button_name: str
    for_member: str
    not_member: str


class Hide(BaseModel):
    hide: List[HideRow]


class ReactRowInner(BaseModel):
    id: int
    react: str
    users: List[int]


class ReactRow(BaseModel):
    id: int
    reactions: List[ReactRowInner]


class React(BaseModel):
    rows: List[ReactRow]


class MessageOptionsCaptcha(BaseModel):
    animation: Optional[Media | str] = None
    video: Optional[Media | str] = None
    photo: Optional[Media | str] = None
    caption: Optional[str] = None
    text: Optional[str] = None
    reply_markup: Optional[ReplyKeyboardMarkup] = None
    resize_markup: Optional[bool] = True


class CaptchaObj(BaseModel):
    id: int
    channel_id: int
    message: Optional[MessageOptionsCaptcha] = None
    delay: int
    start_delay: int = 0

    class Config:
        from_attributes = True


class MessageOptionsHello(BaseModel):
    animation: Optional[Media | str] = None
    video: Optional[Media | str] = None
    photo: Optional[Media | str] = None
    caption: Optional[str] = None
    text: Optional[str] = None
    reply_markup: Optional[InlineKeyboardMarkup] = None
    disable_web_page_preview: bool = True


class HelloAnswer(BaseModel):
    id: int
    channel_id: int
    message: Optional[MessageOptionsHello] = None
    delay: int = 0
    text_with_name: bool = False
    is_active: bool = True

    class Config:
        from_attributes = True


class ByeAnswer(BaseModel):
    message: Optional[MessageOptionsHello] = None
    active: bool = False


class Answer(BaseModel):
    message: MessageOptionsHello
    key: str
    id: str


class Protect(BaseModel):
    china: bool = True
    arab: bool = True
