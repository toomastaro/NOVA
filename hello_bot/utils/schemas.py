from typing import Optional

from pydantic import BaseModel


class Media(BaseModel):
    file_id: str


class MessageOptions(BaseModel):
    animation: Optional[Media | str] = None
    video: Optional[Media | str] = None
    photo: Optional[Media | str] = None
    caption: Optional[str] = None
    text: Optional[str] = None


class HelloAnswer(BaseModel):
    message: Optional[MessageOptions] = None
    active: bool = False


class ByeAnswer(BaseModel):
    message: Optional[MessageOptions] = None
    active: bool = False


class Answer(BaseModel):
    message: MessageOptions
    key: str
    id: str


class Protect(BaseModel):
    china: bool = True
    arab: bool = True
