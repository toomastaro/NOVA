from aiogram import types, Bot

from hello_bot.utils.schemas import MessageOptions, Protect


def get_protect_tag(protect: Protect):
    if protect.arab and protect.china:
        protect_tag = "all"
    elif protect.arab:
        protect_tag = "arab"
    elif protect.china:
        protect_tag = "china"
    else:
        protect_tag = ""

    return protect_tag


async def answer_message_bot(bot: Bot, chat_id: int, message_options: MessageOptions, reply):
    if message_options.text:
        cor = bot.send_message
    elif message_options.photo:
        cor = bot.send_photo
        message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = bot.send_video
        message_options.video = message_options.video.file_id
    else:
        cor = bot.send_animation
        message_options.animation = message_options.animation.file_id

    dump = message_options.model_dump()
    dump['chat_id'] = chat_id

    if message_options.text:
        dump.pop("photo")
        dump.pop("video")
        dump.pop("animation")
        dump.pop("caption")
    elif message_options.photo:
        dump.pop("video")
        dump.pop("animation")
        dump.pop("text")
        dump.pop("disable_web_page_preview")
    elif message_options.video:
        dump.pop("photo")
        dump.pop("animation")
        dump.pop("text")
        dump.pop("disable_web_page_preview")
    # animation
    else:
        dump.pop("photo")
        dump.pop("video")
        dump.pop("text")
        dump.pop("disable_web_page_preview")

    try:
        post_message = await cor(
            **dump,
            reply_markup=reply
        )
    except Exception as e:
        return print(e)

    return post_message


async def answer_message(message: types.Message, message_options: MessageOptions):
    if message_options.text:
        cor = message.answer
    elif message_options.photo:
        cor = message.answer_photo
        message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = message.answer_video
        message_options.video = message_options.video.file_id
    else:
        cor = message.answer_animation
        message_options.animation = message_options.animation.file_id

    post_message = await cor(
        **message_options.model_dump(),
    )

    return post_message
