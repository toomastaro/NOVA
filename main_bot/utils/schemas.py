from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from pydantic import BaseModel


class Media(BaseModel):
    file_id: str


class MessageOptions(BaseModel):
    animation: Media | str | None = None
    video: Media | str | None = None
    photo: Media | str | None = None
    show_caption_above_media: bool | None = None
    caption: str | None = None
    text: str | None = None
    has_spoiler: bool = False
    disable_web_page_preview: bool = True
    disable_notification: bool = False
    parse_mode: str | None = None  # HTML, Markdown, MarkdownV2


class StoryOptions(BaseModel):
    video: Media | str | None = None
    photo: Media | str | None = None
    caption: str | None = None
    noforwards: bool | None = False
    pinned: bool | None = False
    period: int | None = 86400


class HideRow(BaseModel):
    id: int
    button_name: str
    for_member: str
    not_member: str


class Hide(BaseModel):
    hide: list[HideRow]


class ReactRowInner(BaseModel):
    id: int
    react: str
    users: list[int]


class ReactRow(BaseModel):
    id: int
    reactions: list[ReactRowInner]


class React(BaseModel):
    rows: list[ReactRow]


class MessageOptionsCaptcha(BaseModel):
    animation: Media | str | None = None
    video: Media | str | None = None
    photo: Media | str | None = None
    caption: str | None = None
    text: str | None = None
    reply_markup: ReplyKeyboardMarkup | None = None
    resize_markup: bool | None = True


class CaptchaObj(BaseModel):
    id: int
    channel_id: int
    message: MessageOptionsCaptcha | None = None
    delay: int

    class Config:
        from_attributes = True


class MessageOptionsHello(BaseModel):
    animation: Media | str | None = None
    video: Media | str | None = None
    photo: Media | str | None = None
    caption: str | None = None
    text: str | None = None
    reply_markup: InlineKeyboardMarkup | None = None


class HelloAnswer(BaseModel):
    id: int
    channel_id: int
    message: MessageOptionsHello | None = None
    delay: int = 0
    text_with_name: bool = False
    is_active: bool = True

    class Config:
        from_attributes = True


class ByeAnswer(BaseModel):
    message: MessageOptionsHello | None = None
    active: bool = False


class Answer(BaseModel):
    message: MessageOptionsHello
    key: str
    id: str


class Protect(BaseModel):
    china: bool = True
    arab: bool = True
