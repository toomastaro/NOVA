import logging
import re
from datetime import datetime, timedelta

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.published_post.model import PublishedPost
from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.handlers.user.posting.menu import show_content
from main_bot.keyboards import keyboards
from main_bot.utils.functions import answer_post
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler


logger = logging.getLogger(__name__)


def serialize_channel(channel):
    if not channel:
        return None
    return {
        "id": channel.id,
        "chat_id": channel.chat_id,
        "title": channel.title,
        "username": getattr(channel, "username", None),
        "subscribers_count": getattr(channel, "subscribers_count", 0),
        "posting": getattr(channel, "posting", False),
    }


def serialize_post(post):
    if not post:
        return None
    data = {
        "id": post.id,
        "post_id": getattr(post, "post_id", None),
        "chat_id": getattr(post, "chat_id", post.chat_ids[0] if getattr(post, "chat_ids", None) else None),
        "message_id": getattr(post, "message_id", None),
        "created_timestamp": post.created_timestamp,
        "send_time": getattr(post, "send_time", None),
        "delete_time": getattr(post, "delete_time", None),
        "admin_id": post.admin_id,
        "status": getattr(post, "status", "active"),
        "deleted_at": getattr(post, "deleted_at", None),
        "chat_ids": getattr(post, "chat_ids", []),
        "message_options": getattr(post, "message_options", {}),
        "cpm_price": getattr(post, "cpm_price", 0),
        "views_24h": getattr(post, "views_24h", 0),
        "views_48h": getattr(post, "views_48h", 0),
        "views_72h": getattr(post, "views_72h", 0),
        # Поля клавиатуры
        "buttons": getattr(post, "buttons", None),
        "hide": getattr(post, "hide", None),
        "reaction": getattr(post, "reaction", None),
        "pin_time": getattr(post, "pin_time", None),
        "unpin_time": getattr(post, "unpin_time", None),
        "report": getattr(post, "report", False),  # По умолчанию False
        "is_published": isinstance(post, PublishedPost),
    }
    return data


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
    all_month_posts = await db.post.get_posts(channel_chat_id, only_scheduled=False)

    days_with_posts = set()
    for post in all_month_posts:
        post_date = datetime.fromtimestamp(
            post.send_time
            if hasattr(post, "send_time") and post.send_time
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
        author = await db.user.get_user(post_obj.admin_id)
        author_name = (
            f"<a href='tg://user?id={author.id}'>{author.first_name}</a>"
            if author
            else "Неизвестно"
        )
    except Exception:
        author_name = "Неизвестно"

    channels_text = ""
    # Получаем список каналов
    if is_published:
        # Для опубликованного поста - ищем все связанные публикации по post_id
        # PublishedPost.post_id хранит ID родительского поста (или уникальный ID группы)
        published_posts = await db.published_post.get_published_posts_by_post_id(
            post_obj.post_id
        )

        channels_text = "<blockquote>Пост опубликован в:\n"
        for p in published_posts:
            channel = await db.channel.get_channel_by_chat_id(p.chat_id)
            if channel:
                # Получаем кол-во подписчиков для display (если есть в базе)
                _ = getattr(channel, "subscribers_count", "???")

                # Построение ссылки на канал (нет username в БД, поэтому просто title)
                # Если в будущем добавим username в БД, раскомментируем
                # url = f"https://t.me/{channel.username}" if getattr(channel, 'username', None) else ""
                url = ""
                title_link = (
                    f"<a href='{url}'>{channel.title}</a>" if url else channel.title
                )

                channels_text += f"📺 {title_link}\n"
        channels_text += "</blockquote>"

        # Основной блок Published
        # Ссылка на пост (берем первый попавшийся или текущий)
        # Приватная ссылка: t.me/c/CHANNEL_ID/MSG_ID (нужно убрать -100)
        chat_id_str = str(post_obj.chat_id).replace("-100", "")
        post_link = f"https://t.me/c/{chat_id_str}/{post_obj.message_id}"

        # Если бы был username, могли бы сделать публичную ссылку
        # ch = await db.channel.get_channel_by_chat_id(post_obj.chat_id)
        # if ch and getattr(ch, 'username', None):
        #      post_link = f"https://t.me/{ch.username}/{post_obj.message_id}"

        date_str = datetime.fromtimestamp(post_obj.created_timestamp).strftime(
            "%d %B %Y г. в %H:%M"
        )
        if getattr(post_obj, "status", "active") == "deleted":
            deleted_at = getattr(post_obj, "deleted_at", None)
            del_time = (
                datetime.fromtimestamp(deleted_at).strftime("%d %B %Y г. в %H:%M")
                if deleted_at
                else "Неизвестно"
            )
            created_str = datetime.fromtimestamp(post_obj.created_timestamp).strftime(
                "%d %B %Y г. в %H:%M"
            )

            return (
                f"<b>Статус: 🗑 Удален</b>\n"
                f"📅 Создан: {created_str}\n"
                f"🗑 Удален: {del_time}\n\n"
                f"{channels_text}"
            )
        else:
            status_line = "<b>Статус: 👀 Опубликован</b>"
            link_line = f"Ссылка: {post_link}\n"

            return (
                f"{status_line}\n"
                f"{link_line}"
                f"Дата: {date_str}\n\n"
                f"{channels_text}"
            )

    else:
        # Пост (Запланирован или Удален)
        status = getattr(post_obj, "status", "active")

        if status == "deleted":
            # ОТЧЕТ ОБ УДАЛЕНИИ
            deleted_at = getattr(post_obj, "deleted_at", None)
            deleted_str = (
                datetime.fromtimestamp(deleted_at).strftime("%d %B %Y г. в %H:%M")
                if deleted_at
                else "Неизвестно"
            )

            # Получаем каналы куда планировалось/было
            channels_text = "<blockquote>Пост должен был быть в:\n"
            for chat_id in post_obj.get("chat_ids", []):
                channel = await db.channel.get_channel_by_chat_id(chat_id)
                if channel:
                    channels_text += f"📺 {channel.title}\n"
            channels_text += "</blockquote>"

            return (
                f"<b>Отчёт об удалении поста</b>\n"
                f"Удален: {deleted_str}\n"
                f"Автор: {author_name}\n\n"
                f"{channels_text}\n"
                f"🗑 Таймер удаления: {int(post_obj.delete_time/3600) if post_obj.delete_time else 'Нет'} ч\n"
            )

        else:
            # ЗАПЛАНИРОВАН
            date_str = datetime.fromtimestamp(post_obj.send_time).strftime(
                "%d %B %Y г. в %H:%M"
            )

            channels_text = "<blockquote>Пост будет скопирован в:\n"
            for chat_id in post_obj.chat_ids:
                channel = await db.channel.get_channel_by_chat_id(chat_id)
                if channel:
                    # Построение ссылки
                    url = ""  # Нет username
                    title_link = (
                        f"<a href='{url}'>{channel.title}</a>" if url else channel.title
                    )

                    channels_text += f"📺 {title_link}\n"
            channels_text += "</blockquote>"

            return (
                f"<b>Статус: 🕔 Ожидает публикации</b>\n"
                f"Дата: {date_str}\n\n"
                f"{channels_text}"
            )


@safe_handler("Постинг: выбор канала")
async def choice_channel(call: types.CallbackQuery, state: FSMContext):
    """Выбор канала для просмотра контент-плана."""
    temp = call.data.split("|")

    if temp[1] in ["next", "back"]:
        channels = await db.channel.get_user_channels(
            user_id=call.from_user.id, sort_by="posting"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_object_content(
                channels=channels, remover=int(temp[2])
            )
        )

    if temp[1] == "cancel":
        await call.message.delete()
        return await start_posting(call.message)

    chat_id = int(temp[1])
    logger.info(
        f"Пользователь {call.from_user.id} выбрал канал {chat_id} для просмотра контента"
    )
    channel = await db.channel.get_channel_by_chat_id(chat_id)

    day = datetime.today()
    posts = await db.post.get_posts(channel.chat_id, day)
    day_values = (
        day.day,
        text("month").get(str(day.month)),
        day.year,
    )

    await state.update_data(
        channel=serialize_channel(channel),
        day=day.isoformat(),
        day_values=day_values,
        show_more=False,
    )

    await call.message.delete()

    # Получаем дни с постами за месяц для индикаторов на календаре
    days_with_posts = await get_days_with_posts(channel.chat_id, day.year, day.month)

    await call.message.answer(
        text("channel:content").format(
            *day_values,
            channel.title,
            text("no_content") if not posts else text("has_content").format(len(posts)),
        ),
        reply_markup=keyboards.choice_row_content(
            posts=posts, day=day, days_with_posts=days_with_posts
        ),
    )


@safe_handler("Постинг: выбор строки контента")
async def choice_row_content(call: types.CallbackQuery, state: FSMContext):
    """Навигация по контент-плану (выбор дня, поста)."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        logger.warning(
            f"Нет данных состояния для пользователя {call.from_user.id} в choice_row_content"
        )
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_content(call.message)

    channel_data = data.get("channel")
    show_more: bool = data.get("show_more")
    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else (day_str or datetime.today())
    )

    if temp[1] in [
        "next_day",
        "next_month",
        "back_day",
        "back_month",
        "choice_day",
        "show_more",
    ]:
        if temp[1] == "choice_day":
            day = datetime.strptime(temp[2], "%Y-%m-%d")
        elif temp[1] == "show_more":
            show_more = not show_more
        else:
            day = day - timedelta(days=int(temp[2]))

        posts = await db.post.get_posts(channel_data["chat_id"], day)
        day_values = (
            day.day,
            text("month").get(str(day.month)),
            day.year,
        )

        await state.update_data(
            day=day.isoformat(), day_values=day_values, show_more=show_more
        )

        # Получаем дни с постами за месяц для индикаторов
        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )

        return await call.message.edit_text(
            text("channel:content").format(
                channel_data["title"],
                *day_values,
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                days_with_posts=days_with_posts,
            ),
        )

    if temp[1] == "show_all":
        posts = await db.post.get_posts(channel_data["chat_id"], only_scheduled=True)
        return await call.message.edit_text(
            text("channel:show_all:content").format(
                channel_data["title"],
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_time_objects(objects=posts),
        )

    if temp[1] == "...":
        return await call.answer()

    # Обработка PublishedPost
    if call.data.startswith("ContentPublishedPost"):
        post_id = int(temp[1])
        logger.info(
            f"Пользователь {call.from_user.id} просматривает опубликованный пост {post_id}"
        )
        post = await db.published_post.get_published_post_by_id(post_id)

        # Подготовка значений даты
        dt = datetime.fromtimestamp(post.created_timestamp)
        send_date_values = (
            dt.day,
            text("month").get(str(dt.month)),
            dt.year,
        )

        await state.update_data(
            post=serialize_post(post),
            send_date_values=send_date_values,
            is_edit=True,
            is_published=True,
        )

        post_message = await answer_post(call.message, state, from_edit=True)
        if post_message:
            await state.update_data(
                post_message=post_message.model_dump(mode="json"),
            )

            await call.message.delete()

            # New Text Generation
            info_text = await generate_post_info_text(post, is_published=True)

            await call.message.answer(
                info_text, reply_markup=keyboards.manage_published_post(post=post)
            )
            return

    post_id = int(temp[1])
    post = await db.post.get_post(post_id)
    send_date = datetime.fromtimestamp(post.send_time)
    send_date_values = (
        send_date.day,
        text("month").get(str(send_date.month)),
        send_date.year,
    )
    await state.update_data(
        post=serialize_post(post),
        send_date_values=send_date_values,
        is_edit=True,
        is_published=False,  # Explicitly set false
    )

    post_message = await answer_post(call.message, state, from_edit=True)
    await state.update_data(
        post_message=post_message.model_dump(mode="json"),
    )

    await call.message.delete()

    # Генерация нового текста
    info_text = await generate_post_info_text(post, is_published=False)

    await call.message.answer(
        info_text, reply_markup=keyboards.manage_remain_post(post=post)
    )


@safe_handler("Постинг: выбор времени")
async def choice_time_objects(call: types.CallbackQuery, state: FSMContext):
    """Просмотр списка запланированных постов."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    channel_data = data.get("channel")

    if temp[1] in ["next", "back"]:
        posts = await db.post.get_posts(channel_data["chat_id"])
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_time_objects(objects=posts)
        )

    show_more: bool = data.get("show_more")
    day: datetime = data.get("day")

    if temp[1] == "cancel":
        day_str = data.get("day")
        day = (
            datetime.fromisoformat(day_str)
            if isinstance(day_str, str)
            else (day_str or datetime.today())
        )

        posts = await db.post.get_posts(channel_data["chat_id"], day)
        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )
        return await call.message.edit_text(
            text("channel:content").format(
                channel_data["title"],
                *data.get("day_values"),
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                days_with_posts=days_with_posts,
            ),
        )


@safe_handler("Постинг: управление остатком постов")
async def manage_remain_post(call: types.CallbackQuery, state: FSMContext):
    """Управление запланированным (или черновиком) постом."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    channel_data = data.get("channel")
    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else datetime.today()
    )

    if temp[1] == "cancel":
        posts = await db.post.get_posts(channel_data["chat_id"], day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        elif post_message:  # Проверка существования перед использованием
            await call.bot.delete_message(
                call.message.chat.id,
                (
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else post_message.message_id
                ),
            )

        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )
        return await call.message.edit_text(
            text("channel:content").format(
                channel_data["title"],
                *data.get("day_values"),
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts, day=day, days_with_posts=days_with_posts
            ),
        )

    if temp[1] == "delete":
        callback_data = (
            "AcceptDeletePublishedPost"
            if data.get("is_published")
            else "AcceptDeletePost"
        )
        await call.message.edit_text(
            text("accept:delete:post"),
            reply_markup=keyboards.accept_delete_row_content(data=callback_data),
        )
        return

    if temp[1] == "change":
        await call.message.delete()
        post_message = data.get("post_message")

        post_message = data.get("post_message")

        # Нужен объект для клавиатуры, data['post'] сейчас dict
        # Клавиатура вероятно ожидает объект.
        # Quick fix: передаем dict, проверяем клавиатуру.

        reply_markup = keyboards.manage_post(
            post=data.get("post"), is_edit=data.get("is_edit")
        )

        if isinstance(post_message, types.Message):
            await post_message.edit_reply_markup(reply_markup=reply_markup)
        elif post_message:
            await call.bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=(
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else post_message.message_id
                ),
                reply_markup=reply_markup,
            )
        return


@safe_handler("Постинг: подтверждение удаления контента")
async def accept_delete_row_content(call: types.CallbackQuery, state: FSMContext):
    """Подтверждение удаления поста."""
    # ... logic existing ...
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else (day_str or datetime.today())
    )
    day_values = data.get("day_values")
    # send_date_values = data.get("send_date_values")
    channel_data = data.get("channel")
    post = data.get("post")

    if temp[1] == "cancel":
        # Генерация нового текста
        info_text = await generate_post_info_text(
            post, is_published=data.get("is_published")
        )

        return await call.message.edit_text(
            info_text,
            reply_markup=keyboards.manage_remain_post(
                post=post, is_published=data.get("is_published")
            ),
        )

    if temp[1] == "accept":
        await db.post.delete_post(post["id"])
        posts = await db.post.get_posts(channel_data["chat_id"], day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        elif post_message:
            await call.bot.delete_message(
                call.message.chat.id,
                (
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else post_message.message_id
                ),
            )

        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )
        return await call.message.edit_text(
            text("channel:content").format(
                channel_data["title"],
                *day_values,
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts, day=day, days_with_posts=days_with_posts
            ),
        )


@safe_handler("Постинг: управление опубликованными")
async def manage_published_post(call: types.CallbackQuery, state: FSMContext):
    """Управление уже опубликованным постом (отчеты, удаление)."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post = data.get("post")

    if temp[1] == "cpm_report":
        import html
        from types import SimpleNamespace
        from main_bot.utils.report_signature import get_report_signatures

        # Ensure post is an object for attribute access
        if isinstance(post, dict):
            post = SimpleNamespace(**post)

        # Fetch related posts
        related_posts = await db.published_post.get_published_posts_by_post_id(
            post.post_id
        )
        if not related_posts:
            related_posts = [post]

        total_views = 0
        channels_info = []

        # Calculate views from history (since post is deleted)
        for p in related_posts:
            v_hist = max(p.views_24h or 0, p.views_48h or 0, p.views_72h or 0)
            views = v_hist

            total_views += views
            channel = await db.channel.get_channel_by_chat_id(p.chat_id)
            channels_info.append(f"{html.escape(channel.title)} - 👀 {views}")

        # Calculate Price
        cpm_price = post.cpm_price or 0
        rub_price = round(float(cpm_price * float(total_views / 1000)), 2)

        # Get Rate
        user = await db.user.get_user(post.admin_id)
        usd_rate = 1.0
        exch_update = "N/A"

        # Determine Rate ID (Use User's preference or Default to 0=CryptoBot)
        rate_id = 0
        if user and user.default_exchange_rate_id is not None:
            rate_id = user.default_exchange_rate_id

        exchange_rate = await db.exchange_rate.get_exchange_rate(rate_id)
        if exchange_rate and exchange_rate.rate > 0:
            usd_rate = exchange_rate.rate
            exch_update = (
                exchange_rate.last_update.strftime("%H:%M %d.%m.%Y")
                if exchange_rate.last_update
                else "N/A"
            )

        # Format Text
        channels_text_inner = "\n".join(
            text("resource_title").format(c) for c in channels_info
        )
        channels_text = f"<blockquote expandable>{channels_text_inner}</blockquote>"

        # Получение превью текста
        opts = post.message_options or {}
        raw_text = opts.get("text") or opts.get("caption") or "Без текста"
        # Очистка HTML тегов
        clean_text = re.sub(r"<[^>]+>", "", raw_text)
        preview_text_raw = (
            clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
        )
        preview_text = f"«{html.escape(preview_text_raw)}»"

        # Использование формата отчета CPM
        report_text = text("cpm:report").format(
            preview_text,
            channels_text,
            cpm_price,
            total_views,
            rub_price,
            round(rub_price / usd_rate, 2),
            round(usd_rate, 2),
            exch_update,
        )

        # Подпись
        report_text += await get_report_signatures(user, "cpm", call.bot)

        # Клавиатура с кнопкой Назад к деталям поста
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        kb = InlineKeyboardBuilder()
        kb.button(
            text=text("back:button"), callback_data=f"ContentPublishedPost|{post.id}"
        )

        await call.message.edit_text(
            report_text,
            reply_markup=kb.as_markup(),
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
        return

    if temp[1] == "cancel":
        from datetime import datetime
        day = data.get("day")
        if isinstance(day, str):
            day = datetime.fromisoformat(day)
            
        channel_data = data.get("channel")
        posts = await db.post.get_posts(channel_data["chat_id"], day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(
                call.message.chat.id,
                (
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else post_message.message_id
                ),
            )

        # Возврат к списку контента
        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )

        return await call.message.edit_text(
            text("channel:content").format(
                channel_data["title"],
                *data.get("day_values"),
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts, day=day, days_with_posts=days_with_posts
            ),
        )

    if temp[1] == "delete":
        await call.message.edit_text(
            text("accept:delete:post"),
            reply_markup=keyboards.accept_delete_row_content(
                data="AcceptDeletePublishedPost"
            ),
        )
        return

    if temp[1] == "change":
        await call.message.delete()
        post_message = data.get("post_message")
        reply_markup = keyboards.manage_post(post=post, is_edit=True)

        if isinstance(post_message, types.Message):
            await post_message.edit_reply_markup(reply_markup=reply_markup)
        else:
            await call.bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=(
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else post_message.message_id
                ),
                reply_markup=reply_markup,
            )
        return

    if temp[1] == "timer":
        # Open choice delete time
        return await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time(),
        )

    if temp[1] == "cpm":
        if not post.delete_time:
            return await call.answer(text("error_cpm_without_timer"), show_alert=True)

        await state.update_data(
            param="cpm_price"
        )  # Reuse existing logic name if possible

        await call.message.delete()
        message_text = text("manage:post:new:cpm_price")

        input_msg = await call.message.answer(
            message_text, reply_markup=keyboards.param_cancel(param="cpm_price")
        )
        from main_bot.states.user import Posting

        await state.set_state(Posting.input_value)
        await state.update_data(input_msg_id=input_msg.message_id)
        return


@safe_handler("Постинг: удаление опубликованного")
async def accept_delete_published_post(call: types.CallbackQuery, state: FSMContext):
    """Подтверждение удаления опубликованного поста (удаление из каналов и БД)."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        logger.warning(
            f"No state data found for user {call.from_user.id} in accept_delete_published_post"
        )
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else (day_str or datetime.today())
    )
    day_values = data.get("day_values")
    # send_date_values = data.get("send_date_values")
    channel_data = data.get("channel")
    post = data.get("post")

    if temp[1] == "cancel":
        # New Text Generation
        info_text = await generate_post_info_text(post, is_published=True)

        return await call.message.edit_text(
            info_text, reply_markup=keyboards.manage_published_post(post=post)
        )

    if temp[1] == "accept":
        await db.post.delete_post(post["id"])
        logger.info(
            f"User {call.from_user.id} deleting published post {post['id']} (message_id: {post.get('message_id')}) and all related posts"
        )

        # Fetch all related published posts
        related_posts = await db.published_post.get_published_posts_by_post_id(
            post["id"]
        )

        # Delete from Telegram for all channels
        ids_to_delete = []
        for p in related_posts:
            ids_to_delete.append(p.id)
            try:
                await call.bot.delete_message(p.chat_id, p.message_id)
            except Exception as e:
                logger.error(
                    f"Error deleting message {p.message_id} from {p.chat_id}: {e}",
                    exc_info=True,
                )

        # Soft Delete all from DB
        if ids_to_delete:
            await db.published_post.soft_delete_published_posts(ids_to_delete)

        posts = await db.post.get_posts(channel_data["chat_id"], day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        elif post_message:
            await call.bot.delete_message(
                call.message.chat.id,
                (
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else post_message.message_id
                ),
            )

        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )
        return await call.message.edit_text(
            text("channel:content").format(
                channel_data["title"],
                *day_values,
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts, day=day, days_with_posts=days_with_posts
            ),
        )


def get_router():
    router = Router()
    router.callback_query.register(
        choice_channel, F.data.split("|")[0] == "ChoiceObjectContentPost"
    )
    router.callback_query.register(
        choice_row_content,
        F.data.split("|")[0].in_({"ContentPost", "ContentPublishedPost"}),
    )
    router.callback_query.register(
        choice_time_objects, F.data.split("|")[0] == "ChoiceTimeObjectContentPost"
    )
    router.callback_query.register(
        manage_remain_post, F.data.split("|")[0] == "ManageRemainPost"
    )
    router.callback_query.register(
        manage_published_post, F.data.split("|")[0] == "ManagePublishedPost"
    )
    router.callback_query.register(
        accept_delete_row_content, F.data.split("|")[0] == "AcceptDeletePost"
    )
    router.callback_query.register(
        accept_delete_published_post,
        F.data.split("|")[0] == "AcceptDeletePublishedPost",
    )
    return router
