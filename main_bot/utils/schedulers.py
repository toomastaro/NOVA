import asyncio
import os
import re
import time
from pathlib import Path

from aiogram import Bot, types
from httpx import AsyncClient

from instance_bot import bot
from hello_bot.database.db import Database
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.story.model import Story
from main_bot.database.types import Status
from main_bot.database.user_bot.model import UserBot
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.functions import set_channel_session, get_path, get_path_video
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import MessageOptions, StoryOptions, MessageOptionsHello
from main_bot.utils.session_manager import SessionManager


async def send(post: Post):
    message_options = MessageOptions(**post.message_options)

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

    options = message_options.model_dump()
    if message_options.text:
        options.pop("photo")
        options.pop("video")
        options.pop("animation")
        options.pop("show_caption_above_media")
        options.pop("has_spoiler")
        options.pop("caption")
    elif message_options.photo:
        options.pop("video")
        options.pop("animation")
        options.pop("text")
        options.pop("disable_web_page_preview")
    elif message_options.video:
        options.pop("photo")
        options.pop("animation")
        options.pop("text")
        options.pop("disable_web_page_preview")

    # animation
    else:
        options.pop("photo")
        options.pop("video")
        options.pop("text")
        options.pop("disable_web_page_preview")

    error_send = []
    success_send = []

    for chat_id in post.chat_ids:
        channel = await db.get_channel_by_chat_id(chat_id)
        if not channel.subscribe:
            continue

        options['chat_id'] = chat_id

        try:
            post_message = await cor(
                **options,
                reply_markup=keyboards.post_kb(
                    post=post
                )
            )
            await asyncio.sleep(0.25)
        except Exception as e:
            print(e)
            error_send.append({"chat_id": chat_id, "error": str(e)})
            continue

        if post.pin_time:
            await post_message.pin(message_options.disable_notification)

        current_time = int(time.time())
        success_send.append(
            {
                "post_id": post.id,
                "chat_id": chat_id,
                "message_id": post_message.message_id,
                "admin_id": post.admin_id,
                "reaction": post.reaction or None,
                "hide": post.hide or None,
                "buttons": post.buttons or None,
                "unpin_time": post.pin_time + current_time if post.pin_time else None,
                "delete_time": post.delete_time + current_time if post.delete_time else None,
                "report": post.report,
                "cpm_price": post.cpm_price
            }
        )

    if success_send:
        await db.add_many_published_post(
            posts=success_send
        )

    await db.clear_posts(
        post_ids=[post.id]
    )

    if not post.report:
        return

    objects = await db.get_user_channels(
        user_id=post.admin_id,
        from_array=post.chat_ids
    )
    success_str = "\n".join(
        text("resource_title").format(
            obj.emoji_id,
            obj.title
        ) for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in success_send[:10]]
    )
    error_str = "\n".join(
        text("resource_title").format(
            obj.emoji_id,
            obj.title
        ) + " \n{}".format(
            "".join(
                row.get("error")
                for row in error_send[:10]
                if row.get("chat_id") == obj.chat_id
            )
        ) for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in error_send[:10]]
    )

    if success_send and error_send:
        message_text = text("success_error:post:public").format(
            success_str,
            error_str,
        )
    elif success_send:
        message_text = text("manage:post:success:public").format(
            success_str,
        )
    elif error_send:
        message_text = text("error:post:public").format(
            error_str,
        )
    else:
        message_text = "Unknown Post Notification Message"

    try:
        await bot.send_message(
            chat_id=post.admin_id,
            text=message_text
        )
    except Exception as e:
        print(e)


async def send_posts():
    posts = await db.get_post_for_send()

    for post in posts:
        asyncio.create_task(send(post))


async def unpin_posts():
    posts = await db.get_posts_for_unpin()

    for post in posts:
        try:
            await bot.unpin_chat_message(
                chat_id=post.chat_id,
                message_id=post.message_id
            )
        except Exception as e:
            print(e)


async def delete_posts():
    db_posts = await db.get_posts_for_delete()

    row_ids = []
    posts = {}
    for post in db_posts:
        channel = await db.get_channel_by_chat_id(post.chat_id)

        if channel.session_path:
            session_path = Path(channel.session_path)
        else:
            session_path = await set_channel_session(post.chat_id)
            if isinstance(session_path, dict):
                session_path = None

        if post.cpm_price and session_path:
            async with SessionManager(session_path) as session:
                if session:
                    views = await session.get_views(post.chat_id, [post.message_id])
                else:
                    views = None
        else:
            views = None

        if post.post_id not in posts:
            posts[post.post_id] = []

        messages = posts[post.post_id]
        messages.append({
            "channel": channel,
            "views": sum([i.views for i in views.views]) if views else 0,
            "admin_id": post.admin_id,
            "cpm_price": post.cpm_price
        })
        posts[post.post_id] = messages

        try:
            await bot.delete_message(post.chat_id, post.message_id)
        except Exception as e:
            print(e)

            try:
                await bot.send_message(
                    chat_id=post.admin_id,
                    text=text("error:post:delete").format(
                        post.message_id,
                        channel.emoji_id,
                        channel.title
                    )
                )
            except Exception as e:
                print(e)

        row_ids.append(post.id)

    for post_id, message_objects in posts.items():
        cpm_price = message_objects[0]["cpm_price"]
        if not cpm_price:
            continue

        async with AsyncClient() as client:
            res = await client.get('https://api.coinbase.com/v2/prices/USD-RUB/spot')
            usd_rate = float(res.json().get('data').get('amount'))

        admin_id = message_objects[0]["admin_id"]
        total_views = sum(obj["views"] for obj in message_objects)
        rub_price = round(float(cpm_price * float(total_views / 1000)), 2)
        channels_text = "\n".join(
            text("resource_title").format(obj["channel"].emoji_id, obj["channel"].title) + f" - 👀 {obj['views']}"
            for obj in message_objects
        )

        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text("cpm:report").format(
                    post_id,
                    channels_text,
                    cpm_price,
                    total_views,
                    rub_price,
                    round(rub_price / usd_rate, 2),
                    round(usd_rate, 2),
                )
            )
        except Exception as e:
            print(e)

    await db.delete_published_posts(
        row_ids=row_ids
    )


async def send_story(story: Story):
    options = StoryOptions(**story.story_options)

    if options.photo:
        options.photo = options.photo.file_id
    if options.video:
        options.video = options.video.file_id

    error_send = []
    success_send = []

    for chat_id in story.chat_ids:
        channel = await db.get_channel_by_chat_id(chat_id)
        if not channel.subscribe:
            continue

        if channel.session_path:
            session_path = Path(channel.session_path)
        else:
            session_path = await set_channel_session(chat_id)

        print(session_path)
        if isinstance(session_path, dict):
            session_path['chat_id'] = chat_id
            error_send.append(session_path)
            continue

        manager = SessionManager(session_path)
        await manager.init_client()

        if not manager.client:
            await db.update_channel_by_chat_id(
                chat_id=chat_id,
                session_path=None
            )
            error_send.append({"chat_id": chat_id, "error": "Session Error"})
            continue

        input_file = None
        if options.video:
            input_file = "main_bot/utils/temp/{}".format(
                (await bot.get_file(options.video)).file_path.split('/')[-1]
            )

        media_bytes = await bot.download(
            file=options.video or options.photo,
            destination=input_file
        )

        if options.photo:
            filepath = get_path(media_bytes, chat_id)
        else:
            filepath = get_path_video(input_file, chat_id)

        if options.caption:
            caption = options.caption
            options.caption = caption.replace(
                '<tg-emoji emoji-id', '<emoji id'
            ).replace(
                '</tg-emoji>', '</emoji>'
            )

        try:
            await manager.send_story(
                chat_id=chat_id,
                filepath=filepath,
                options=options
            )
            success_send.append({"chat_id": chat_id})
        except Exception as e:
            print(e)
        finally:
            try:
                os.remove(filepath)
                await manager.close()
            except Exception as e:
                print(e)

    await db.clear_story(
        post_ids=[story.id]
    )

    if not story.report:
        return

    objects = await db.get_user_channels(
        user_id=story.admin_id,
        from_array=story.chat_ids
    )
    success_str = "\n".join(
        text("resource_title").format(
            obj.emoji_id,
            obj.title
        ) for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in success_send[:10]]
    )
    error_str = "\n".join(
        text("resource_title").format(
            obj.emoji_id,
            obj.title
        ) + " \n{}".format(
            "".join(
                row.get("error")
                for row in error_send[:10]
                if row.get("chat_id") == obj.chat_id
            )
        ) for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in error_send[:10]]
    )

    if success_send and error_send:
        message_text = text("success_error:story:public").format(
            success_str,
            error_str,
        )
    elif success_send:
        message_text = text("manage:story:success:public").format(
            success_str,
        )
    elif error_send:
        message_text = text("error:story:public").format(
            error_str,
        )
    else:
        message_text = "Unknown Story Notification Message"

    try:
        await bot.send_message(
            chat_id=story.admin_id,
            text=message_text
        )
    except Exception as e:
        print(e)


async def send_stories():
    stories = await db.get_story_for_send()

    for story in stories:
        asyncio.create_task(send_story(story))


async def delete_bot_posts(user_bot: UserBot, message_ids: list[dict]):
    async with BotManager(user_bot.token) as bot_manager:
        validate = await bot_manager.validate_token()
        if not validate:
            return
        status = await bot_manager.status()
        if not status:
            return

        for message in message_ids:
            try:
                await bot_manager.bot.delete_message(**message)
            except Exception as e:
                print(e)


async def start_delete_bot_posts():
    bot_posts = await db.get_bot_posts_for_clear_messages()

    for bot_post in bot_posts:
        if (bot_post.delete_time + bot_post.start_timestamp) > time.time():
            continue

        messages = bot_post.message_ids
        if not messages:
            continue

        for bot_id in list(messages.keys()):
            user_bot = await db.get_bot_by_id(int(bot_id))
            asyncio.create_task(delete_bot_posts(user_bot, messages[bot_id]["message_ids"]))


async def send_bot_messages(other_bot: Bot, bot_post: BotPost, users, filepath):
    message_options = MessageOptionsHello(**bot_post.message)

    if message_options.text:
        cor = other_bot.send_message
    elif message_options.photo:
        cor = other_bot.send_photo
        message_options.photo = types.FSInputFile(filepath)
    elif message_options.video:
        cor = other_bot.send_video
        message_options.video = types.FSInputFile(filepath)
    else:
        cor = other_bot.send_animation
        message_options.animation = types.FSInputFile(filepath)

    options = message_options.model_dump()

    try:
        options.pop("show_caption_above_media")
        options.pop("disable_web_page_preview")
        options.pop("has_spoiler")
    except KeyError:
        pass

    if message_options.text:
        options.pop("photo")
        options.pop("video")
        options.pop("animation")
        options.pop("caption")
    elif message_options.photo:
        options.pop("video")
        options.pop("animation")
        options.pop("text")
    elif message_options.video:
        options.pop("photo")
        options.pop("animation")
        options.pop("text")

    # animation
    else:
        options.pop("photo")
        options.pop("video")
        options.pop("text")

    success = 0
    message_ids = []

    for user in users:
        try:
            options["chat_id"] = user
            if bot_post.text_with_name:
                get_user = await other_bot.get_chat(user)
                added_text = f"{get_user.username or get_user.first_name}\n\n"

                if message_options.text:
                    options["text"] = added_text + message_options.text
                if message_options.caption:
                    options["caption"] = added_text + message_options.caption

            message = await cor(**options)
            message_ids.append({"message_id": message.message_id, "chat_id": user})
            success += 1
        except Exception as e:
            print(e)

        await asyncio.sleep(0.25)

    return {other_bot.id: {"success": success, "message_ids": message_ids}}


async def process_bot(user_bot: UserBot, bot_post: BotPost, users, filepath):
    async with BotManager(user_bot.token) as bot_manager:
        validate = await bot_manager.validate_token()

        if not validate:
            raise Exception("TOKEN")
        status = await bot_manager.status()
        if not status:
            raise Exception("STATUS")

        return await send_bot_messages(
            other_bot=bot_manager.bot,
            bot_post=bot_post,
            users=users,
            filepath=filepath
        )


async def send_bot_post(bot_post: BotPost):
    users_count = 0
    semaphore = asyncio.Semaphore(5)

    async def process_semaphore(*args):
        async with semaphore:
            return await process_bot(*args)

    message_options = MessageOptionsHello(**bot_post.message)
    attrs = ["photo", "video", "animation"]
    file_id = next(
        (getattr(message_options, attr).file_id for attr in attrs if getattr(message_options, attr)),
        None
    )

    filepath = None
    if file_id:
        get_file = await bot.get_file(file_id)
        filepath = "main_bot/utils/temp/mail_{}".format(
            get_file.file_path.split("/")[-1]
        )

    tasks = []
    user_bot_objects = []

    for chat_id in bot_post.chat_ids:
        channel = await db.get_channel_by_chat_id(chat_id)
        if not channel.subscribe:
            continue

        channel_settings = await db.get_channel_bot_setting(
            chat_id=channel.chat_id
        )
        user_bot = await db.get_bot_by_id(
            row_id=channel_settings.bot_id
        )

        other_db = Database()
        other_db.schema = user_bot.schema

        users = await other_db.get_users(channel.chat_id)
        users_count += len(users)

        tasks.append(
            process_semaphore(user_bot, bot_post, users, filepath)
        )
        user_bot_objects.append(channel)

    success_count = 0
    message_ids = {}

    start_timestamp = int(time.time())
    if tasks:
        if file_id and filepath:
            await bot.download(file_id, filepath)

        result = await asyncio.gather(*tasks, return_exceptions=True)
        for i in result:
            if not isinstance(i, dict):
                continue

            # {key: {key: value, key: value}}
            bot_id = list(i.keys())[0]
            success_count += i[bot_id].get("success", 0)
            message_ids.update(i)

    end_timestamp = int(time.time())
    if file_id and filepath:
        try:
            os.remove(filepath)
        except Exception as e:
            print(e)

    if bot_post.report:
        message_text = message_options.text or message_options.caption

        if message_text:
            message_text = message_text.replace('tg-emoji emoji-id', '').replace('</tg-emoji>', '')
            message_text = re.sub(r'<[^>]+>', '', message_text)
        else:
            message_text = "Медиа"

        try:
            await bot.send_message(
                chat_id=bot_post.admin_id,
                text=text("success_bot_post").format(
                    message_text,
                    len(bot_post.chat_ids),
                    "\n".join(
                        text("resource_title").format(
                            obj.emoji_id,
                            obj.title
                        ) for obj in user_bot_objects[:10]
                    ),
                    success_count
                )
            )
        except Exception as e:
            print(e)

    await db.update_bot_post(
        post_id=bot_post.id,
        success_send=success_count,
        error_send=users_count - success_count,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        status=Status.FINISH,
        message_ids=message_ids or None
    )


async def send_bot_posts():
    posts = await db.get_bot_post_for_send()
    if not posts:
        return

    tasks = []
    for post in posts:
        asyncio.create_task(send_bot_post(post))

    await asyncio.gather(*tasks, return_exceptions=True)


def get_sub_status(expire_time: int) -> tuple[str | None, int | None]:
    if not expire_time:
        return None, None

    delta = expire_time - time.time()

    if 86400 * 2 < delta < 86400 * 3:
        return "expire_3d", 3
    elif 0 < delta < 86400:
        return "expire_1d", 1
    elif delta < 0:
        return "expired", 0
    return None, None


async def check_subscriptions():
    for channel in await db.get_active_channels():
        for field, text_prefix in [
            ("subscribe", "post"),
        ]:
            expire_time = getattr(channel, field)
            status, days = get_sub_status(expire_time)
            if not status:
                continue

            if status == "expired":
                msg = text(f"expire_off_sub").format(channel.emoji_id, channel.title)
                await db.update_channel_by_id(channel.id, **{field: None})
            else:
                msg = text(f"expire_sub").format(
                    channel.emoji_id,
                    channel.title,
                    days,
                    time.strftime("%d.%m.%Y", time.localtime(expire_time)),
                )

            try:
                await bot.send_message(channel.admin_id, msg)
            except Exception as e:
                print(f"[{text_prefix.upper()}_NOTIFY] {channel.title}: {e}")
