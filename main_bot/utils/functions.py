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

    # Если фото нет, возвращаем дефолтный emoji
    if not photo_bytes:
        return emoji_id

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
            logger.error(f"Ошибка создания стикера: {e}")

        try:
            os.remove(output_path)
        except:
            pass

    except Exception as e:
        logger.error(f"Ошибка обработки фото для emoji: {e}")

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
    # 1. Get active internal clients
    clients = await db.get_mt_clients_by_pool('internal')
    active_clients = [c for c in clients if c.is_active and c.status == 'ACTIVE']
    
    if not active_clients:
        logger.error("No active internal clients found")
        return {"error": "No Active Clients"}

    for client in active_clients:
        session_path = Path(client.session_path)
        if not session_path.exists():
            continue

        async with SessionManager(session_path) as manager:
            if not manager:
                continue
            
            # Получить user_id клиента
            me = await manager.me()
            if not me:
                logger.error(f"Failed to get user info for client {client.id}")
                continue
            
            logger.info(f"Client {client.id} (user_id={me.id}) ready for join")

            # Шаг 0: Проверить и снять бан если есть
            try:
                member_status = await main_bot_obj.get_chat_member(chat_id, me.id)
                from aiogram.enums import ChatMemberStatus
                
                if member_status.status in [ChatMemberStatus.BANNED, ChatMemberStatus.KICKED]:
                    logger.warning(f"Client {client.id} (user_id={me.id}) is banned in {chat_id}, unbanning...")
                    
                    # Снять бан
                    await main_bot_obj.unban_chat_member(chat_id, me.id, only_if_banned=True)
                    logger.info(f"Successfully unbanned client {client.id} (user_id={me.id}) in {chat_id}")
                    
                    # Подождать немного после снятия бана
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                # Если не удалось проверить статус - это нормально (клиент может еще не быть в канале)
                logger.debug(f"Could not check ban status for client {client.id} in {chat_id}: {e}")


            # Шаг 1: Попытка добавить клиента напрямую через InviteToChannelRequest
            # Это более надежный способ чем invite ссылки
            try:
                # Получить entity канала через MTProto
                channel_entity = await manager.client.get_entity(chat_id)
                
                # Добавить пользователя в канал
                from telethon.tl.functions.channels import InviteToChannelRequest
                await manager.client(InviteToChannelRequest(
                    channel=channel_entity,
                    users=[me]
                ))
                logger.info(f"Client {client.id} (user_id={me.id}) added to channel {chat_id} via InviteToChannelRequest")
                
            except Exception as e:
                error_str = str(e)
                logger.error(f"InviteToChannelRequest failed for client {client.id}: {e}")
                
                # Если прямое добавление не сработало, пробуем через invite ссылку
                # Это fallback для случаев когда бот не имеет прав на добавление
                try:
                    # Создаем ПОСТОЯННУЮ ссылку для клиента
                    chat_invite_link = await main_bot_obj.create_chat_invite_link(
                        chat_id=chat_id,
                        name=f"MTProto Client {client.id}",
                        creates_join_request=False
                        # БЕЗ member_limit - ссылка постоянная и многоразовая
                    )
                    logger.info(f"Created permanent fallback invite link for {chat_id}: {chat_invite_link.invite_link}")
                    
                    success_join = await manager.join(chat_invite_link.invite_link)
                    if not success_join:
                        logger.warning(f"Client {client.id} failed to join via invite link")
                        continue
                        
                except Exception as link_error:
                    logger.error(f"Fallback invite link also failed for client {client.id}: {link_error}")
                    
                    # Send alert for access loss
                    if "USER_NOT_PARTICIPANT" in error_str or "CHANNEL_PRIVATE" in error_str or "CHAT_ADMIN_REQUIRED" in error_str:
                        from main_bot.utils.support_log import send_support_alert, SupportAlert
                        channel = await db.get_channel_by_chat_id(chat_id)
                        
                        await send_support_alert(main_bot_obj, SupportAlert(
                            event_type='INTERNAL_ACCESS_LOST',
                            client_id=client.id,
                            client_alias=client.alias,
                            pool_type=client.pool_type,
                            channel_id=chat_id,
                            is_our_channel=True,
                            error_code=error_str.split('(')[0].strip() if '(' in error_str else error_str[:50],
                            error_text=f"Не удалось добавить клиента в канал: {error_str[:100]}"
                        ))
                    
                    continue


        # Шаг 3: Проверить, что клиент есть как подписчик
        try:
            member_status = await main_bot_obj.get_chat_member(chat_id, me.id)
            from aiogram.enums import ChatMemberStatus
            
            if member_status.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                logger.error(f"Client {client.id} (user_id={me.id}) is not a member of {chat_id}, status: {member_status.status}")
                continue
            
            logger.info(f"Verified: Client {client.id} is a member of {chat_id}")
        except Exception as e:
            logger.error(f"Error checking membership for client {client.id} in {chat_id}: {e}")
            continue

        # Шаг 4: Проверить права бота и промоутить клиента до администратора
        bot_rights_result = {"has_admin": False, "can_promote": False, "promoted": False, "reason": ""}
        
        try:
            # Сначала проверим права самого бота
            bot_info = await main_bot_obj.get_me()
            bot_member = await main_bot_obj.get_chat_member(chat_id, bot_info.id)
            
            from aiogram.enums import ChatMemberStatus
            
            # Логируем статус бота
            logger.info(f"🤖 Bot status in channel {chat_id}: {bot_member.status}")
            
            # Проверяем, является ли бот администратором с правами на промоут
            if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                bot_rights_result["reason"] = f"Bot is not administrator (status: {bot_member.status})"
                logger.error(f"❌ {bot_rights_result['reason']} in {chat_id}")
                logger.warning(f"Skipping promotion for client {client.id}, adding as regular member")
                
                # Добавляем клиента в БД как обычного участника без прав на stories
                await db.add_mt_client_channel(
                    client_id=client.id,
                    channel_id=chat_id,
                    is_member=True,
                    can_post_stories=False,  # Нет прав администратора
                    can_view_stats=True
                )
                
                await db.update_channel_by_chat_id(
                    chat_id=chat_id,
                    session_path=str(session_path)
                )
                
                return {"success": True, "bot_rights": bot_rights_result, "session_path": str(session_path)}
            
            bot_rights_result["has_admin"] = True
            
            # Проверяем права бота на промоут
            if not bot_member.can_promote_members:
                bot_rights_result["reason"] = "Bot lacks can_promote_members permission"
                logger.error(f"❌ {bot_rights_result['reason']} in {chat_id}")
                logger.warning(f"Skipping promotion for client {client.id}, adding as regular member")
                
                # Добавляем клиента в БД как обычного участника
                await db.add_mt_client_channel(
                    client_id=client.id,
                    channel_id=chat_id,
                    is_member=True,
                    can_post_stories=False,
                    can_view_stats=True
                )
                
                await db.update_channel_by_chat_id(
                    chat_id=chat_id,
                    session_path=str(session_path)
                )
                
                return {"success": True, "bot_rights": bot_rights_result, "session_path": str(session_path)}
            
            bot_rights_result["can_promote"] = True
            logger.info(f"✅ Bot has admin rights with can_promote_members in {chat_id}")
            
            # Бот имеет права, промоутим клиента
            promote = await main_bot_obj.promote_chat_member(
                chat_id=chat_id,
                user_id=me.id,
                can_edit_stories=True,
                can_post_stories=True,
                can_delete_stories=True
            )
            logger.info(f"Promoted client {client.id} (user_id={me.id}) to admin in {chat_id}")
        except Exception as e:
            logger.error(f"Error promoting client {client.id} in {chat_id}: {e}")
            continue

        if not promote:
            logger.error(f"Failed to promote client {client.id} in {chat_id}")
            continue
        
        # Шаг 5: Финальная проверка - клиент подписчик, админ, с правами на stories
        try:
            final_check = await main_bot_obj.get_chat_member(chat_id, me.id)
            from aiogram.enums import ChatMemberStatus
            
            # Проверка 1: Является подписчиком
            if final_check.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                logger.error(f"Final check failed: Client {client.id} is not admin, status: {final_check.status}")
                continue
            
            # Проверка 2: Есть права администратора на stories
            if final_check.status == ChatMemberStatus.ADMINISTRATOR:
                if not (final_check.can_post_stories and final_check.can_edit_stories and final_check.can_delete_stories):
                    logger.error(f"Final check failed: Client {client.id} missing story permissions")
                    continue
            
            logger.info(f"✓ Final verification passed for client {client.id}: member + admin + story rights")
        except Exception as e:
            logger.error(f"Error in final verification for client {client.id}: {e}")
            continue

        # Все проверки пройдены успешно
        if True:
            bot_rights_result["promoted"] = True
            bot_rights_result["reason"] = "Successfully promoted to administrator"
            logger.info(f"✅ Successfully promoted client {client.id} to administrator in {chat_id}")
            
            # Create/Update MtClientChannel
            await db.add_mt_client_channel(
                client_id=client.id,
                channel_id=chat_id,
                is_member=True,
                can_post_stories=True,  # Подтверждено финальной проверкой
                can_view_stats=True  # Assuming if we joined we can view stats
            )
            
            # Update legacy channel field for backward compatibility if needed, 
            # but we are moving away from it. 
            # However, existing code might still rely on it until fully refactored.
            await db.update_channel_by_chat_id(
                chat_id=chat_id,
                session_path=str(session_path)
            )
            
            return {"success": True, "bot_rights": bot_rights_result, "session_path": str(session_path)}

    return {"error": "Try Later"}


async def background_join_channel(chat_id: int, user_id: int = None):
    """
    Попытка добавить клиента в канал в фоне с ретраями.
    Делает 3 попытки с экспоненциальной задержкой.
    Отправляет уведомление пользователю о результате выдачи прав администратора.
    """
    import asyncio
    
    for attempt in range(3):
        try:
            # Используем существующую логику set_channel_session
            res = await set_channel_session(chat_id)
            
            # Проверяем успех (теперь возвращает dict с bot_rights или dict с ошибкой)
            if isinstance(res, dict) and res.get("success"):
                logger.info(f"Успешно добавлен клиент в канал {chat_id} на попытке {attempt+1}")
                
                # Отправить уведомление пользователю о правах бота
                if user_id:
                    bot_rights = res.get("bot_rights", {})
                    
                    if bot_rights.get("promoted"):
                        message = (
                            "✅ <b>Права администратора успешно выданы!</b>\n\n"
                            "MTProto-клиент добавлен в канал с правами администратора.\n"
                            "Теперь доступна публикация stories."
                        )
                    elif bot_rights.get("has_admin") and not bot_rights.get("can_promote"):
                        message = (
                            "⚠️ <b>Права администратора частично выданы</b>\n\n"
                            f"<b>Причина:</b> {bot_rights.get('reason', 'Неизвестно')}\n\n"
                            "MTProto-клиент добавлен как обычный участник.\n"
                            "Для публикации stories дайте боту права 'Добавление администраторов' в канале."
                        )
                    else:
                        message = (
                            "❌ <b>Права администратора не выданы</b>\n\n"
                            f"<b>Причина:</b> {bot_rights.get('reason', 'Неизвестно')}\n\n"
                            "MTProto-клиент добавлен как обычный участник.\n"
                            "Для полной функциональности дайте боту права администратора в канале."
                        )
                    
                    try:
                        await main_bot_obj.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send notification to user {user_id}: {e}")
                
                return
            
            # Если вернулась ошибка
            logger.warning(f"Попытка {attempt+1} добавления клиента в канал {chat_id} неудачна: {res}")
            
        except Exception as e:
            logger.error(f"Ошибка при фоновом добавлении клиента в канал {chat_id}: {e}")
            
        # Ждем перед следующей попыткой (экспоненциально)
        if attempt < 2:  # Не ждем после последней попытки
            await asyncio.sleep(5 * (attempt + 1))
    
    # Если все попытки исчерпаны - алерт уже будет отправлен внутри set_channel_session
    logger.error(f"Все попытки добавления клиента в канал {chat_id} исчерпаны")


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
