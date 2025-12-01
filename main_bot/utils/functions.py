import math
import os
import random
import string
from pathlib import Path

import ffmpeg
from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from PIL import Image, ImageDraw, ImageFilter

from instance_bot import bot as main_bot_obj
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.story.model import Story
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.schemas import MessageOptions, StoryOptions, Protect, MessageOptionsHello, MessageOptionsCaptcha
from main_bot.utils.session_manager import SessionManager
from config import Config
import logging

logger = logging.getLogger(__name__)


async def create_emoji(user_id: int, photo_bytes=None):
    emoji_id = '5393222813345663485'

    if not photo_bytes:
        photo_bytes = 'main_bot/utils/no_photo.jpg'

    try:
        with Image.open(photo_bytes) as img:
            new_image = img.resize((100, 100))
            mask = Image.new("L", new_image.size)
            draw = ImageDraw.Draw(mask)
            draw.ellipse(
                xy=(4, 4, new_image.size[0] - 4, new_image.size[1] - 4),
                fill=255
            )
            mask = mask.filter(ImageFilter.GaussianBlur(2))

            output_path = f"main_bot/utils/temp/{user_id}.png"
            result = new_image.copy()
            result.putalpha(mask)
            result.save(output_path)

            set_id = ''.join(random.sample(string.ascii_letters, k=10)) + '_by_' + (await main_bot_obj.get_me()).username

        try:
            await main_bot_obj.create_new_sticker_set(
                user_id=user_id,
                name=set_id,
                title='NovaTGEmoji',
                stickers=[
                    types.InputSticker(
                        sticker=types.FSInputFile(
                            path=output_path
                        ),
                        format='static',
                        emoji_list=['🤩']
                    )
                ],
                sticker_format='static',
                sticker_type='custom_emoji'
            )
            r = await main_bot_obj.get_sticker_set(set_id)
            await main_bot_obj.session.close()
            emoji_id = r.stickers[0].custom_emoji_id
        except Exception as e:
            print(e)

        os.remove(output_path)

    except Exception as e:
        print(e)

    return emoji_id


async def get_editors(call: types.CallbackQuery, chat_id: int):
    editors = []

    try:
        admins = await call.bot.get_chat_administrators(chat_id)
        for admin in admins:
            if admin.user.is_bot:
                continue

            row = await db.get_channel_admin_row(chat_id, admin.user.id)
            if not row:
                continue

            if not isinstance(admin, types.ChatMemberOwner):
                rights = {
                    admin.can_post_messages,
                    admin.can_edit_messages,
                    admin.can_delete_messages,
                    admin.can_post_stories,
                    admin.can_edit_stories,
                    admin.can_delete_stories
                }
                if False in rights:
                    continue

            editors.append(admin)
    except Exception as e:
        print(e)
        editors.append("Не удалось обнаружить")

    return "\n".join(
        "@{}".format(i.user.username)
        if i.user.username else i.user.full_name
        for i in editors
    ) + "\n"


async def answer_bot_post(message: types.Message, state: FSMContext, from_edit: bool = False):
    data = await state.get_data()

    post: BotPost = data.get('post')
    is_edit: bool = data.get('is_edit')
    message_options = MessageOptionsHello(**post.message)

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

    if not from_edit:
        reply_markup = keyboards.manage_bot_post(
            post=post,
            is_edit=is_edit
        )
        message_options.reply_markup = reply_markup

    post_message = await cor(
        **message_options.model_dump(),
        parse_mode='HTML'
    )

    return post_message


async def answer_post(message: types.Message, state: FSMContext, from_edit: bool = False):
    data = await state.get_data()

    post: Post = data.get('post')
    is_edit: bool = data.get('is_edit')
    message_options = MessageOptions(**post.message_options)

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

    if from_edit:
        reply_markup = keyboards.post_kb(
            post=post
        )
    else:
        reply_markup = keyboards.manage_post(
            post=post,
            show_more=data.get('show_more'),
            is_edit=is_edit
        )

    # Backup Preview Logic
    if post.backup_message_id and Config.BACKUP_CHAT_ID:
        try:
            post_message = await message.bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=Config.BACKUP_CHAT_ID,
                message_id=post.backup_message_id,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            logger.info(f"Preview for post {post.id} loaded from backup (msg {post.backup_message_id})")
            return post_message
        except Exception as e:
            logger.error(f"Failed to load preview from backup for post {post.id}: {e}", exc_info=True)
            # Fallback to local construction

    post_message = await cor(
        **message_options.model_dump(),
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    logger.info(f"Preview for post {post.id} generated locally")

    return post_message


async def answer_story(message: types.Message, state: FSMContext, from_edit: bool = False):
    data = await state.get_data()

    post: Story = data.get('post')
    is_edit: bool = data.get('is_edit')
    story_options = StoryOptions(**post.story_options)

    if story_options.photo:
        cor = message.answer_photo
        story_options.photo = story_options.photo.file_id
    else:
        cor = message.answer_video
        story_options.video = story_options.video.file_id

    if from_edit:
        reply_markup = None
    else:
        reply_markup = keyboards.manage_story(
            post=post,
            is_edit=is_edit
        )

    post_message = await cor(
        **story_options.model_dump(),
        reply_markup=reply_markup
    )

    return post_message


async def set_channel_session(chat_id: int):
    folder_path = 'main_bot/utils/sessions/'
    sessions = os.listdir(folder_path)
    chat_invite_link = await main_bot_obj.create_chat_invite_link(
        chat_id=chat_id,
        member_limit=15
    )

    for session in sessions:
        session_path = folder_path + session

        async with SessionManager(Path(session_path)) as manager:
            if not manager:
                continue

            success_join = await manager.join(
                invite_url=chat_invite_link.invite_link
            )
            if not success_join:
                continue

            can_send_stories = await manager.can_send_stories(
                chat_id=int(str(chat_id).replace("-100", ""))
            )
            if not can_send_stories:
                return {"error": "Stories Unavailable"}

            me = await manager.me()

        try:
            promote = await main_bot_obj.promote_chat_member(
                chat_id=chat_id,
                user_id=me[0].id,
                can_edit_stories=True,
                can_post_stories=True,
                can_delete_stories=True
            )
        except Exception as e:
            print(e)
            continue

        if promote:
            await db.update_channel_by_chat_id(
                chat_id=chat_id,
                session_path=session_path
            )
            return Path(session_path)

    return {"error": "Try Later"}


def get_mode(image: Image) -> str:
    if image.mode not in ['RGB', 'RGBA']:
        return 'RGB'
    return image.mode


def get_color(image: Image):
    mode = get_mode(image)
    if mode != image.mode:
        image = image.convert('RGB')

    red_total = 0
    green_total = 0
    blue_total = 0
    alpha_total = 0
    count = 0

    pixel = image.load()

    for i in range(image.width):
        for j in range(image.height):
            color = pixel[i, j]
            if len(color) == 4:
                red, green, blue, alpha = color
            else:
                [red, green, blue], alpha = color, 255

            red_total += red * red * alpha
            green_total += green * green * alpha
            blue_total += blue * blue * alpha
            alpha_total += alpha

            count += 1

    return (
        round(math.sqrt(red_total / alpha_total)),
        round(math.sqrt(green_total / alpha_total)),
        round(math.sqrt(blue_total / alpha_total)),
        round(alpha_total / count)
    )


def get_path(photo, chat_id):
    with Image.open(photo) as img:

        mask = Image.new("RGBA", (540, 960), get_color(img))

        if img.width < 540:
            img = img.resize((540, 960))
            img.thumbnail((540, 960))

        if img.width > 540:
            img.thumbnail((540, 960))

        height = int(960 / 2 - img.height / 2)

        mask.paste(
            img,
            (0, height),
            img.convert('RGBA')
        )

        path = str(chat_id) + '.png'
        mask.save(path)

        return path


def get_path_video(input_path: str, chat_id: int):
    base_name = f"{abs(chat_id)}"
    extension = input_path.split('.')[1]
    tmp_path = f"main_bot/utils/temp/{base_name}_tmp.{extension}"
    output_path = f"main_bot/utils/temp/{base_name}_final.{extension}"

    try:
        probe = ffmpeg.probe(input_path)
        stream = next((s for s in probe["streams"] if s.get("width")), None)
        if not stream:
            raise RuntimeError("Не удалось определить разрешение видео")

        width, height = stream["width"], stream["height"]
        if width >= height:
            (
                ffmpeg
                .input(input_path)
                .filter("scale", "iw", "2*trunc(iw*16/18)")
                .filter(
                    "boxblur",
                    "luma_radius=min(h\\,w)/5",
                    "luma_power=1",
                    "chroma_radius=min(cw\\,ch)/5",
                    "chroma_power=1"
                )
                .overlay(ffmpeg.input(input_path), x="(W-w)/2", y="(H-h)/2")
                .filter("setsar", 1)
                .output(tmp_path, loglevel="quiet", y=None)
                .run()
            )
        else:
            tmp_path = input_path

        (
            ffmpeg
            .input(tmp_path)
            .filter("scale", 540, 960)
            .output(output_path, loglevel="quiet", y=None)
            .run()
        )

        return output_path

    except Exception as e:
        print(f"Ошибка при обработке видео: {e.stderr}")
        return None
    finally:
        for f in (input_path, tmp_path):
            if os.path.exists(f) and f != output_path:
                try:
                    os.remove(f)
                except Exception as ex:
                    print(f"Не удалось удалить {f}: {ex}")


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


async def answer_message_bot(bot: Bot, chat_id: int, message_options: MessageOptionsHello | MessageOptionsCaptcha):
    if message_options.text:
        cor = bot.send_message
    elif message_options.photo:
        cor = bot.send_photo
    elif message_options.video:
        cor = bot.send_video
    else:
        cor = bot.send_animation

    attrs = ["photo", "video", "animation"]
    file_id = next(
        (getattr(message_options, attr).file_id for attr in attrs
         if getattr(message_options, attr)),
        None
    )

    try:
        filepath = None
        if file_id:
            get_file = await main_bot_obj.get_file(file_id)
            filepath = "main_bot/utils/temp/hello_message_media_{}".format(
                get_file.file_path.split("/")[-1]
            )
            await main_bot_obj.download(file_id, filepath)
    except Exception as e:
        return print(e)

    dump = message_options.model_dump()
    dump['chat_id'] = chat_id
    dump['parse_mode'] = 'HTML'

    if isinstance(message_options, MessageOptionsCaptcha):
        dump.pop("resize_markup")

    if message_options.text:
        dump.pop("photo")
        dump.pop("video")
        dump.pop("animation")
        dump.pop("caption")

    elif message_options.photo:
        if filepath:
            dump["photo"] = types.FSInputFile(filepath)

        dump.pop("video")
        dump.pop("animation")
        dump.pop("text")

    elif message_options.video:
        if filepath:
            dump["video"] = types.FSInputFile(filepath)

        dump.pop("photo")
        dump.pop("animation")
        dump.pop("text")
    # animation
    else:
        if filepath:
            dump["animation"] = types.FSInputFile(filepath)

        dump.pop("photo")
        dump.pop("video")
        dump.pop("text")

    try:
        post_message = await cor(**dump)
    except Exception as e:
        return print(e)

    try:
        os.remove(filepath)
    except Exception as e:
        print(e)

    return post_message


async def answer_message(message: types.Message, message_options: MessageOptionsHello | MessageOptionsCaptcha):
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
        parse_mode='HTML'
    )

    return post_message
