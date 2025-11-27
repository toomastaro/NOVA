from pydantic import BaseModel


class Media(BaseModel):
    file_id: str


class MessageOptions(BaseModel):
    animation: Media | str | None = None
    video: Media | str | None = None
    photo: Media | str | None = None
    caption: str | None = None
    text: str | None = None


class HelloAnswer(BaseModel):
    message: MessageOptions | None = None
    active: bool = False


class ByeAnswer(BaseModel):
    message: MessageOptions | None = None
    active: bool = False


class Answer(BaseModel):
    message: MessageOptions
    key: str
    id: str


class Protect(BaseModel):
    china: bool = True
    arab: bool = True
