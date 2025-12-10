import logging
import re
import html
from datetime import datetime, timedelta

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.channel.model import Channel
from main_bot.database.published_post.model import PublishedPost
from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.handlers.user.posting.menu import show_content
from main_bot.keyboards import keyboards
from main_bot.utils.functions import answer_post
from main_bot.utils.lang.language import text
from main_bot.utils.error_handler import safe_handler


logger = logging.getLogger(__name__)


async def get_days_with_posts(channel_chat_id: int, year: int, month: int) -> set:
    """
    Получает множество дней месяца, в которые есть посты (включая удаленные).
    
    Args:
        channel_chat_id: ID канала
        year: Год
        month: Месяц
        
    Returns:
        set: Множество дней (int) с постами
    """
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    month_start = datetime(year, month, 1)
    month_end = datetime(year, month, last_day, 23, 59, 59)
    
    # Получаем все посты (запланированные и опубликованные)
    all_month_posts = await db.get_posts(channel_chat_id, only_scheduled=False)
    
    days_with_posts = set()
    for post in all_month_posts:
        post_date = datetime.fromtimestamp(
            post.send_time if hasattr(post, 'send_time') and post.send_time 
            else post.created_timestamp
        )
        if month_start <= post_date <= month_end:
            days_with_posts.add(post_date.day)
    
    return days_with_posts



async def generate_post_info_text(post_obj, is_published: bool = False) -> str:
    """
    Генерирует текст информации о посте для меню управления.
    
    Args:
        post_obj: Объект Post или PublishedPost
        is_published: Флаг того, что пост уже опубликован
    """
    try:
        author = await db.get_user(post_obj.admin_id)
        author_name = f"<a href='tg://user?id={author.id}'>{author.first_name}</a>" if author else "Неизвестно"
    except:
        author_name = "Неизвестно"

    
    channels_text = ""
    # Получаем список каналов
    if is_published:
        # Для опубликованного поста - ищем все связанные публикации по post_id
        # PublishedPost.post_id хранит ID родительского поста (или уникальный ID группы)
        published_posts = await db.get_published_posts_by_post_id(post_obj.post_id)
        
        channels_text = "<blockquote>Пост опубликован в:\n"
        for p in published_posts:
            channel = await db.get_channel_by_chat_id(p.chat_id)
            if channel:
                # Получаем кол-во подписчиков для display (если есть в базе)
                subs = getattr(channel, 'subscribers_count', '???')
                
                # Построение ссылки на канал (нет username в БД, поэтому просто title)
                # Если в будущем добавим username в БД, раскомментируем
                # url = f"https://t.me/{channel.username}" if getattr(channel, 'username', None) else ""
                url = ""
                title_link = f"<a href='{url}'>{channel.title}</a>" if url else channel.title
                
                channels_text += f"📢 {title_link} (<code>{p.chat_id}</code>)\n"
        channels_text += "</blockquote>"
        
        # Основной блок Published
        # Ссылка на пост (берем первый попавшийся или текущий)
        # Приватная ссылка: t.me/c/CHANNEL_ID/MSG_ID (нужно убрать -100)
        chat_id_str = str(post_obj.chat_id).replace('-100', '')
        post_link = f"https://t.me/c/{chat_id_str}/{post_obj.message_id}"

        # Если бы был username, могли бы сделать публичную ссылку
        # ch = await db.get_channel_by_chat_id(post_obj.chat_id)
        # if ch and getattr(ch, 'username', None):
        #      post_link = f"https://t.me/{ch.username}/{post_obj.message_id}"

        date_str = datetime.fromtimestamp(post_obj.created_timestamp).strftime("%d %B %Y г. в %H:%M")
        if getattr(post_obj, 'status', 'active') == 'deleted':
             deleted_at = getattr(post_obj, 'deleted_at', None)
             del_time = datetime.fromtimestamp(deleted_at).strftime("%d %B %Y г. в %H:%M") if deleted_at else "Неизвестно"
             created_str = datetime.fromtimestamp(post_obj.created_timestamp).strftime("%d %B %Y г. в %H:%M")
             
             return (
                f"<b>Статус: 🗑 Удален</b>\n"
                f"📅 Создан: {created_str}\n"
                f"🗑 Удален: {del_time}\n"
                f"{channels_text}"
             )
        else:
             status_line = "<b>Статус: 👀 Опубликован</b>"
             link_line = f"Ссылка: {post_link}\n"
        
             return (
                f"{status_line}\n"
                f"{link_line}"
                f"Дата: {date_str}\n"
                f"Автор: {author_name}\n\n"
                f"{channels_text}"
             )

    else:
        # Post (Scheduled or Deleted)
        status = getattr(post_obj, 'status', 'active')
        
        if status == 'deleted':
            # DELETED REPORT
            deleted_at = getattr(post_obj, 'deleted_at', None)
            deleted_str = datetime.fromtimestamp(deleted_at).strftime("%d %B %Y г. в %H:%M") if deleted_at else "Неизвестно"
            
            # Получаем каналы куда планировалось/было
            channels_text = "<blockquote>Пост должен был быть в:\n"
            for chat_id in post_obj.chat_ids:
                channel = await db.get_channel_by_chat_id(chat_id)
                if channel:
                    channels_text += f"📢 {channel.title}\n"
            channels_text += "</blockquote>"
            
            return (
                f"<b>Отчёт об удалении поста</b>\n"
                f"Удален: {deleted_str}\n"
                f"Автор: {author_name}\n\n"
                f"{channels_text}\n"
                f"🗑 Таймер удаления: {int(post_obj.delete_time/3600) if post_obj.delete_time else 'Нет'} ч\n"
            )
            
        else:
            # SCHEDULED
            date_str = datetime.fromtimestamp(post_obj.send_time).strftime("%d %B %Y г. в %H:%M")
            
            channels_text = "<blockquote>Пост будет скопирован в:\n"
            for chat_id in post_obj.chat_ids:
                channel = await db.get_channel_by_chat_id(chat_id)
                if channel:
                     # Построение ссылки
                    url = "" # Нет username
                    title_link = f"<a href='{url}'>{channel.title}</a>" if url else channel.title
                    
                    subs = "???" 
                    channels_text += f"📢 {title_link} ({subs} 👥)\n"
            channels_text += "</blockquote>"
            
            return (
                f"<b>Статус: 🕔 Ожидает публикации</b>\n"
                f"Дата: {date_str}\n"
                f"Автор: {author_name}\n\n"
                f"{channels_text}"
            )


@safe_handler("Posting Choice Channel")
async def choice_channel(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] in ["next", "back"]:
        channels = await db.get_user_channels(
            user_id=call.from_user.id,
            sort_by="posting"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_object_content(
                channels=channels,
                remover=int(temp[2])
            )
        )

    if temp[1] == "cancel":
        await call.message.delete()
        return await start_posting(call.message)

    chat_id = int(temp[1])
    logger.info(f"User {call.from_user.id} selected channel {chat_id} for content view")
    channel = await db.get_channel_by_chat_id(chat_id)

    day = datetime.today()
    posts = await db.get_posts(channel.chat_id, day)
    day_values = (day.day, text("month").get(str(day.month)), day.year,)

    await state.update_data(
        channel=channel,
        day=day,
        day_values=day_values,
        show_more=False
    )

    await call.message.delete()
    
    # Получаем дни с постами за месяц для индикаторов на календаре
    days_with_posts = await get_days_with_posts(channel.chat_id, day.year, day.month)
    
    await call.message.answer(
        text("channel:content").format(
            *day_values,
            channel.title,
            text("no_content") if not posts else text("has_content").format(len(posts))
        ),
        reply_markup=keyboards.choice_row_content(
            posts=posts,
            day=day,
            days_with_posts=days_with_posts
        )
    )


@safe_handler("Posting Choice Row Content")
async def choice_row_content(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        logger.warning(f"No state data found for user {call.from_user.id} in choice_row_content")
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_content(call.message)

    channel: Channel = data.get("channel")
    show_more: bool = data.get("show_more")
    day: datetime = data.get("day") or datetime.today()

    if temp[1] in ['next_day', 'next_month', 'back_day', 'back_month', "choice_day", "show_more"]:
        if temp[1] == "choice_day":
            day = datetime.strptime(temp[2], '%Y-%m-%d')
        elif temp[1] == "show_more":
            show_more = not show_more
        else:
            day = day - timedelta(days=int(temp[2]))

        posts = await db.get_posts(channel.chat_id, day)
        day_values = (day.day, text("month").get(str(day.month)), day.year,)

        await state.update_data(
            day=day,
            day_values=day_values,
            show_more=show_more
        )
        
        # Получаем дни с постами за месяц для индикаторов
        days_with_posts = await get_days_with_posts(channel.chat_id, day.year, day.month)

        return await call.message.edit_text(
            text("channel:content").format(
                channel.title,
                *day_values,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                days_with_posts=days_with_posts
            )
        )

    if temp[1] == "show_all":
        posts = await db.get_posts(channel.chat_id, only_scheduled=True)
        return await call.message.edit_text(
            text("channel:show_all:content").format(
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_time_objects(
                objects=posts
            )
        )

    if temp[1] == "...":
        return await call.answer()
    
    
    # Handle PublishedPost
    if call.data.startswith("ContentPublishedPost"):
        post_id = int(temp[1])
        logger.info(f"User {call.from_user.id} viewing published post {post_id}")
        post = await db.get_published_post_by_id(post_id)
        
        await state.update_data(
            post=post,
            send_date_values=datetime.fromtimestamp(post.created_timestamp).timetuple(), # Mock/Simplification
            is_edit=True, 
            is_published=True 
        )

        post_message = await answer_post(call.message, state, from_edit=True)
        await state.update_data(
            post_message=post_message,
        )

        await call.message.delete()
        
        # New Text Generation
        info_text = await generate_post_info_text(post, is_published=True)
        
        await call.message.answer(
            info_text,
            reply_markup=keyboards.manage_published_post(
                post=post
            )
        )
        return

    post_id = int(temp[1])
    post = await db.get_post(post_id)
    send_date = datetime.fromtimestamp(post.send_time)
    send_date_values = (send_date.day, text("month").get(str(send_date.month)), send_date.year,)
    await state.update_data(
        post=post,
        send_date_values=send_date_values,
        is_edit=True,
        is_published=False # Explicitly set false
    )

    post_message = await answer_post(call.message, state, from_edit=True)
    await state.update_data(
        post_message=post_message,
    )

    await call.message.delete()
    
    # New Text Generation
    info_text = await generate_post_info_text(post, is_published=False)
    
    await call.message.answer(
        info_text,
        reply_markup=keyboards.manage_remain_post(
            post=post
        )
    )


@safe_handler("Posting Choice Time Objects")
async def choice_time_objects(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    channel: Channel = data.get("channel")

    if temp[1] in ["next", "back"]:
        posts = await db.get_posts(channel.chat_id)
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_time_objects(
                objects=posts
            )
        )

    show_more: bool = data.get("show_more")
    day: datetime = data.get("day")

    if temp[1] == "cancel":
        posts = await db.get_posts(channel.chat_id, day)
        days_with_posts = await get_days_with_posts(channel.chat_id, day.year, day.month)
        return await call.message.edit_text(
            text("channel:content").format(
                channel.title,
                *data.get("day_values"),
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                days_with_posts=days_with_posts
            )
        )


@safe_handler("Posting Manage Remain Post")
async def manage_remain_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    channel = data.get("channel")
    day = data.get("day")

    if temp[1] == "cancel":
        posts = await db.get_posts(channel.chat_id, day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(call.message.chat.id, post_message.message_id)
        
        days_with_posts = await get_days_with_posts(channel.chat_id, day.year, day.month)
        return await call.message.edit_text(
            text("channel:content").format(
                channel.title,
                *data.get("day_values"),
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                days_with_posts=days_with_posts
            )
        )

    if temp[1] == "delete":
        callback_data = "AcceptDeletePublishedPost" if data.get("is_published") else "AcceptDeletePost"
        await call.message.edit_text(
            text("accept:delete:post"),
            reply_markup=keyboards.accept_delete_row_content(data=callback_data)
        )
        return

    if temp[1] == "change":
        await call.message.delete()
        post_message = data.get("post_message")
        reply_markup = keyboards.manage_post(
            post=data.get('post'),
            is_edit=data.get('is_edit')
        )
        
        if isinstance(post_message, types.Message):
            await post_message.edit_reply_markup(reply_markup=reply_markup)
        else:
            # It's a MessageId object (from copyMessage)
            await call.bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=post_message.message_id,
                reply_markup=reply_markup
            )
        return


@safe_handler("Posting Accept Delete Row Content")
async def accept_delete_row_content(call: types.CallbackQuery, state: FSMContext):
    # ... logic existing ...
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    day = data.get("day")
    day_values = data.get("day_values")
    send_date_values = data.get("send_date_values")
    channel = data.get("channel")
    post = data.get("post")

    if temp[1] == "cancel":
        # New Text Generation
        info_text = await generate_post_info_text(post, is_published=data.get("is_published"))
        
        return await call.message.edit_text(
            info_text,
            reply_markup=keyboards.manage_remain_post(
                post=post,
                is_published=data.get("is_published")
            )
        )

    if temp[1] == "accept":
        await db.delete_post(post.id)
        posts = await db.get_posts(channel.chat_id, day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(call.message.chat.id, post_message.message_id)

        days_with_posts = await get_days_with_posts(channel.chat_id, day.year, day.month)
        return await call.message.edit_text(
            text("channel:content").format(
                channel.title,
                *day_values,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                days_with_posts=days_with_posts
            )
        )


@safe_handler("Posting Manage Published Post")
async def manage_published_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post = data.get('post')

    if temp[1] == "cpm_report":
        import html
        from main_bot.utils.report_signature import get_report_signatures
        
        # Fetch related posts
        related_posts = await db.get_published_posts_by_post_id(post.post_id)
        if not related_posts:
            related_posts = [post]

        total_views = 0
        channels_info = []

        # Calculate views from history (since post is deleted)
        for p in related_posts:
            v_hist = max(p.views_24h or 0, p.views_48h or 0, p.views_72h or 0)
            views = v_hist
            
            total_views += views
            channel = await db.get_channel_by_chat_id(p.chat_id)
            channels_info.append(f"{html.escape(channel.title)} - 👀 {views}")

        # Calculate Price
        cpm_price = post.cpm_price or 0
        rub_price = round(float(cpm_price * float(total_views / 1000)), 2)
        
        # Get Rate
        user = await db.get_user(post.admin_id)
        usd_rate = 1.0
        exch_update = "N/A"
        
        # Determine Rate ID (Use User's preference or Default to 0=CryptoBot)
        rate_id = 0
        if user and user.default_exchange_rate_id is not None:
             rate_id = user.default_exchange_rate_id
             
        exchange_rate = await db.get_exchange_rate(rate_id)
        if exchange_rate and exchange_rate.rate > 0:
            usd_rate = exchange_rate.rate
            exch_update = exchange_rate.last_update.strftime("%H:%M %d.%m.%Y") if exchange_rate.last_update else "N/A"

        # Format Text
        channels_text_inner = "\n".join(text("resource_title").format(c) for c in channels_info)
        channels_text = f"<blockquote expandable>{channels_text_inner}</blockquote>"
        
        # Extract Text Preview
        opts = post.message_options or {}
        raw_text = opts.get('text') or opts.get('caption') or "Без текста"
        # Strip HTML tags to prevent broken tags in preview
        clean_text = re.sub(r'<[^>]+>', '', raw_text)
        preview_text_raw = clean_text[:15] + "..." if len(clean_text) > 15 else clean_text
        preview_text = html.escape(preview_text_raw)
        
        # Using basic cpm:report format
        report_text = text("cpm:report").format(
            preview_text,
            channels_text,
            cpm_price,
            total_views,
            rub_price,
            round(rub_price / usd_rate, 2),
            round(usd_rate, 2),
            exch_update
        )
        
        # Signature
        report_text += await get_report_signatures(user, 'cpm', call.bot)
        
        # Keyboard with Back button to Post Details
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(
            text=text("back:button"),
            callback_data=f"ContentPublishedPost|{post.id}"
        )
        
        await call.message.edit_text(report_text, reply_markup=kb.as_markup(), link_preview_options=types.LinkPreviewOptions(is_disabled=True))
        return

    if temp[1] == "cancel":
        day = data.get('day')
        posts = await db.get_posts(data.get("channel").chat_id, day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(call.message.chat.id, post_message.message_id)
        
        # FIX: return to content list should look right
        days_with_posts = await get_days_with_posts(data.get("channel").chat_id, day.year, day.month)
        
        return await call.message.edit_text(
            text("channel:content").format(
                data.get("channel").title,
                *data.get("day_values"),
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                days_with_posts=days_with_posts
            )
        )

    if temp[1] == "delete":
        await call.message.edit_text(
            text("accept:delete:post"),
            reply_markup=keyboards.accept_delete_row_content(
                data="AcceptDeletePublishedPost"
            )
        )
        return
        
    if temp[1] == "change":
        await call.message.delete()
        post_message = data.get("post_message")
        reply_markup = keyboards.manage_post(
            post=post,
            is_edit=True
        )
        
        if isinstance(post_message, types.Message):
            await post_message.edit_reply_markup(reply_markup=reply_markup)
        else:
            await call.bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=post_message.message_id,
                reply_markup=reply_markup
            )
        return
        
    if temp[1] == "timer":
         # Open choice delete time
        return await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time()
        )
        
    if temp[1] == "cpm":
        if not post.delete_time:
            return await call.answer(text("error_cpm_without_timer"), show_alert=True)
            
        await state.update_data(param='cpm_price') # Reuse existing logic name if possible
        
        await call.message.delete()
        message_text = text("manage:post:new:cpm_price")
        
        input_msg = await call.message.answer(
            message_text,
            reply_markup=keyboards.param_cancel(
                param='cpm_price'
            )
        )
        from main_bot.states.user import Posting
        await state.set_state(Posting.input_value)
        await state.update_data(
            input_msg_id=input_msg.message_id
        )
        return
        

@safe_handler("Posting Accept Delete Published Post")
async def accept_delete_published_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        logger.warning(f"No state data found for user {call.from_user.id} in accept_delete_published_post")
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    day = data.get("day")
    day_values = data.get("day_values")
    # send_date_values = data.get("send_date_values")
    channel = data.get("channel")
    post = data.get("post")

    if temp[1] == "cancel":
        # New Text Generation
        info_text = await generate_post_info_text(post, is_published=True)
        
        return await call.message.edit_text(
            info_text,
            reply_markup=keyboards.manage_published_post(
                post=post
            )
        )

    if temp[1] == "accept":
         # ... existing delete logic ...
        logger.info(f"User {call.from_user.id} deleting published post {post.id} (message_id: {post.message_id}) and all related posts")
        
        # Fetch all related published posts
        related_posts = await db.get_published_posts_by_post_id(post.post_id)
        
        # Delete from Telegram for all channels
        ids_to_delete = []
        for p in related_posts:
            ids_to_delete.append(p.id)
            try:
                await call.bot.delete_message(p.chat_id, p.message_id)
            except Exception as e:
                logger.error(f"Error deleting message {p.message_id} from {p.chat_id}: {e}", exc_info=True)

        # Soft Delete all from DB
        if ids_to_delete:
            await db.soft_delete_published_posts(ids_to_delete)
        
        posts = await db.get_posts(channel.chat_id, day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(call.message.chat.id, post_message.message_id)
        
        days_with_posts = await get_days_with_posts(channel.chat_id, day.year, day.month)
        return await call.message.edit_text(
            text("channel:content").format(
                channel.title,
                *day_values,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                days_with_posts=days_with_posts
            )
        )


def hand_add():
    router = Router()
    router.callback_query.register(choice_channel, F.data.split("|")[0] == "ChoiceObjectContentPost")
    router.callback_query.register(choice_row_content, F.data.split("|")[0].in_({"ContentPost", "ContentPublishedPost"}))
    router.callback_query.register(choice_time_objects, F.data.split("|")[0] == "ChoiceTimeObjectContentPost")
    router.callback_query.register(manage_remain_post, F.data.split("|")[0] == "ManageRemainPost")
    router.callback_query.register(manage_published_post, F.data.split("|")[0] == "ManagePublishedPost")
    router.callback_query.register(accept_delete_row_content, F.data.split("|")[0] == "AcceptDeletePost")
    router.callback_query.register(accept_delete_published_post, F.data.split("|")[0] == "AcceptDeletePublishedPost")
    return router
