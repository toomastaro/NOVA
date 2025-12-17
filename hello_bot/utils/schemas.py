from typing import Optional

from pydantic import BaseModel


class Media(BaseModel):
    """Модель медиафайла."""

    file_id: str


class MessageOptions(BaseModel):
    """Опции сообщения (текст, медиа)."""

    animation: Optional[Media | str] = None
    video: Optional[Media | str] = None
    photo: Optional[Media | str] = None
    caption: Optional[str] = None
    text: Optional[str] = None


class HelloAnswer(BaseModel):
    """Настройки приветственного сообщения."""

    message: Optional[MessageOptions] = None
    active: bool = False


class ByeAnswer(BaseModel):
    """Настройки прощального сообщения."""

    message: Optional[MessageOptions] = None
    active: bool = False


class Answer(BaseModel):
    """Модель ответа."""

    message: MessageOptions
    key: str
    id: str


class Protect(BaseModel):
    """Настройки защиты чата."""

    china: bool = True
    arab: bool = True
