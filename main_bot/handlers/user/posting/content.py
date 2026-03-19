import logging
from datetime import datetime, timedelta

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from main_bot.database.published_post.model import PublishedPost
from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.handlers.user.posting.menu import show_content
from main_bot.keyboards import keyboards
from main_bot.utils.functions import answer_post
from main_bot.utils.cpm_utils import generate_cpm_report
from main_bot.utils.lang.language import text
from main_bot.handlers.user.common_content import serialize_channel
from utils.error_handler import safe_handler


logger = logging.getLogger(__name__)


def serialize_post(post):
    """
    Сериализует объект поста в словарь для хранения в состоянии FSM.

    Аргументы:
        post: Объект Post или PublishedPost.

    Возвращает:
        Словарь с данными поста или None, если пост не передан.
    """
    if not post:
        return None
    data = {
        "id": post.id,
        "post_id": getattr(post, "post_id", None),
        "chat_id": getattr(
            post,
            "chat_id",
            post.chat_ids[0] if getattr(post, "chat_ids", None) else None,
        ),
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
        "buttons": getattr(post, "buttons", None),
        "hide": getattr(post, "hide", None),
        "reaction": getattr(post, "reaction", None),
        "pin_time": getattr(post, "pin_time", None),
        "unpin_time": getattr(post, "unpin_time", None),
        "report": getattr(post, "report", False),
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
            else text("unknown_author")
        )
    except Exception:
        author_name = text("unknown_author")

    channels_text = ""
    if is_published:
        published_posts = await db.published_post.get_published_posts_by_post_id(
            post_obj.post_id
        )

        channels_inner = ""
        for p in published_posts:
            channel = await db.channel.get_channel_by_chat_id(p.chat_id)
            if channel:
                title_link = channel.title
                channels_inner += f"📺 {title_link}\n"

        channels_text = text("post_report_target_channels").format(channels_inner)

        chat_id_str = str(post_obj.chat_id).replace("-100", "")
        post_link = f"https://t.me/c/{chat_id_str}/{post_obj.message_id}"

        date_str = datetime.fromtimestamp(post_obj.created_timestamp).strftime(
            "%d.%m.%Y %H:%M"
        )
        if getattr(post_obj, "status", "active") == "deleted":
            deleted_at = getattr(post_obj, "deleted_at", None)
            del_time = (
                datetime.fromtimestamp(deleted_at).strftime("%d.%m.%Y %H:%M")
                if deleted_at
                else text("unknown")
            )
            created_str = datetime.fromtimestamp(post_obj.created_timestamp).strftime(
                "%d.%m.%Y %H:%M"
            )

            return (
                f"{text('status_deleted')}\n"
                f"{text('post_info_created').format(created_str)}\n"
                f"{text('post_info_deleted').format(del_time)}\n\n"
                f"{channels_text}"
            )
        else:
            status_line = text("status_published")
            link_line = text("post_info_link").format(post_link)

            return f"{status_line}\n{link_line}\n{text('post_info_date').format(date_str)}\n\n{channels_text}"

    else:
        status = getattr(post_obj, "status", "active")

        if status == "deleted":
            deleted_at = getattr(post_obj, "deleted_at", None)
            deleted_str = (
                datetime.fromtimestamp(deleted_at).strftime("%d.%m.%Y %H:%M")
                if deleted_at
                else text("unknown")
            )

            channels_inner = ""
            for chat_id in post_obj.get("chat_ids", []):
                channel = await db.channel.get_channel_by_chat_id(chat_id)
                if channel:
                    channels_inner += f"📺 {channel.title}\n"

            channels_text = text("post_report_target_channels_deleted").format(
                channels_inner
            )

            return (
                f"{text('post_report_deleted_title')}\n"
                f"{text('post_info_deleted').format(deleted_str)}\n"
                f"{text('post_report_author').format(author_name)}\n\n"
                f"{channels_text}\n"
                f"{text('post_report_delete_timer').format(int(post_obj.delete_time / 3600) if post_obj.delete_time else text('post_report_delete_timer_none'))}\n"
            )

        else:
            date_str = datetime.fromtimestamp(post_obj.send_time).strftime(
                "%d.%m.%Y %H:%M"
            )

            channels_inner = ""
            for chat_id in post_obj.chat_ids:
                channel = await db.channel.get_channel_by_chat_id(chat_id)
                if channel:
                    url = ""
                    title_link = (
                        f"<a href='{url}'>{channel.title}</a>" if url else channel.title
                    )
                    channels_inner += f"📺 {title_link}\n"

            channels_text = text("post_report_target_channels_pending").format(
                channels_inner
            )

            return (
                f"{text('status_pending')}\n"
                f"{text('post_info_date').format(date_str)}\n\n"
                f"{channels_text}"
            )


@safe_handler("Постинг: выбор канала для контента")
async def choice_channel(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик выбора канала для просмотра контент-плана.

    Аргументы:
        call: Callback-запрос от пользователя.
        state: Контекст состояния FSM.
    """
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
    """
    Обработчик навигации по контент-плану (выбор дня, поста).

    Аргументы:
        call: Callback-запрос от пользователя.
        state: Контекст состояния FSM.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        logger.warning(
            f"Нет данных состояния для пользователя {call.from_user.id} в choice_row_content"
        )
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    if temp[1] == "cancel":
        return await show_content(call.message, state)

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

        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )

        try:
            return await call.message.edit_text(
                text("channel:content").format(
                    *day_values,
                    channel_data["title"],
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
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                logger.debug("Игнорирование ошибки: сообщение не изменено")
                return await call.answer()
            raise e

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

    if call.data.startswith("ContentPublishedPost"):
        post_id = int(temp[1])
        logger.info(
            f"Пользователь {call.from_user.id} просматривает опубликованный пост {post_id}"
        )
        post = await db.published_post.get_published_post_by_id(post_id)

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
                post_message={"message_id": post_message.message_id},
            )

            await call.message.delete()

            info_text = await generate_post_info_text(post, is_published=True)

            await call.message.answer(
                info_text, reply_markup=keyboards.manage_published_post(post=post, user_id=call.from_user.id)
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
        is_published=False,
    )

    post_message = await answer_post(call.message, state, from_edit=True)
    await state.update_data(
        post_message={"message_id": post_message.message_id},
    )

    await call.message.delete()

    info_text = await generate_post_info_text(post, is_published=False)

    await call.message.answer(
        info_text, reply_markup=keyboards.manage_remain_post(post=post, user_id=call.from_user.id)
    )


@safe_handler("Постинг: выбор времени")
async def choice_time_objects(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик просмотра списка запланированных постов.

    Аргументы:
        call: Callback-запрос от пользователя.
        state: Контекст состояния FSM.
    """
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
                *data.get("day_values"),
                channel_data["title"],
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
    """
    Обработчик управления запланированным (или черновиком) постом.

    Аргументы:
        call: Callback-запрос от пользователя.
        state: Контекст состояния FSM.
    """
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
        # Проверяем, есть ли channel_data (редактирование из контент-плана)
        # или это создание нового поста
        if not channel_data:
            # Создание нового поста - возвращаемся к финальным параметрам
            logger.info(
                f"Пользователь {call.from_user.id} вернулся назад при создании поста (CPM не выбран)"
            )

            post = data.get("post")
            chosen = data.get("chosen", [])

            display_objects = await db.channel.get_user_channels(
                user_id=call.from_user.id, from_array=chosen
            )

            channels_list = (
                "<blockquote expandable>"
                + "\n".join(
                    text("resource_title").format(obj.title) for obj in display_objects
                )
                + "</blockquote>"
                if chosen
                else ""
            )

            await call.message.delete()
            return await call.message.answer(
                text("manage:post:finish_params").format(len(chosen), channels_list),
                reply_markup=keyboards.finish_params(obj=post, user_id=call.from_user.id),
                parse_mode="HTML",
            )

        # Редактирование из контент-плана - возвращаемся к списку постов
        posts = await db.post.get_posts(channel_data["chat_id"], day)

        post_message = data.get("post_message")
        try:
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
        except TelegramBadRequest:
            pass

        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )
        return await call.message.edit_text(
            text("channel:content").format(
                *data.get("day_values"),
                channel_data["title"],
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
    """
    Обработчик подтверждения удаления поста.

    Аргументы:
        call: Callback-запрос от пользователя.
        state: Контекст состояния FSM.
    """
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
        info_text = await generate_post_info_text(
            post, is_published=data.get("is_published")
        )

        return await call.message.edit_text(
            info_text,
            reply_markup=keyboards.manage_remain_post(
                post=post, is_published=data.get("is_published"), user_id=call.from_user.id
            ),
        )

    if temp[1] == "accept":
        await db.post.delete_post(post["id"])
        posts = await db.post.get_posts(channel_data["chat_id"], day)

        post_message = data.get("post_message")
        try:
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
        except TelegramBadRequest:
            pass

        days_with_posts = await get_days_with_posts(
            channel_data["chat_id"], day.year, day.month
        )
        return await call.message.edit_text(
            text("channel:content").format(
                *day_values,
                channel_data["title"],
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
    """
    Обработчик управления уже опубликованным постом (отчеты, удаление).

    Аргументы:
        call: Callback-запрос от пользователя.
        state: Контекст состояния FSM.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    from main_bot.keyboards.posting import ensure_obj

    post = ensure_obj(data.get("post"))

    if temp[1] == "cpm_report":
        user = await db.user.get_user(post.admin_id)
        related_posts = await db.published_post.get_published_posts_by_post_id(
            post.post_id
        )
        if not related_posts:
            related_posts = [post]

        # Используем общую утилиту для генерации отчета
        report_text = await generate_cpm_report(
            user=user,
            post_id=post.post_id,
            related_posts=related_posts,
            bot=call.bot
        )

        if not report_text:
            return await call.answer(text("no_content"))

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

    if temp[1] == "test_report":
        user = await db.user.get_user(post.admin_id)
        related_posts = await db.published_post.get_published_posts_by_post_id(
            post.post_id
        )
        if not related_posts:
            related_posts = [post]

        # Используем общую утилиту для генерации отчета
        report_text = "🧪 <b>ТЕСТОВЫЙ ОТЧЕТ (ИМИТАЦИЯ ШЕДУЛЕРА)</b>\n\n"
        report_text += await generate_cpm_report(
            user=user,
            post_id=post.post_id,
            related_posts=related_posts,
            bot=call.bot
        )

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
        try:
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
        except TelegramBadRequest:
            pass

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

        await state.update_data(param="cpm_price")

        await call.message.delete()
        message_text = text("manage:post:new:cpm_price")

        input_msg = await call.message.answer(
            message_text, reply_markup=keyboards.param_cpm_input(param="cpm_price")
        )
        from main_bot.states.user import Posting

        await state.set_state(Posting.input_value)
        await state.update_data(input_msg_id=input_msg.message_id)
        return


@safe_handler("Постинг: удаление опубликованного")
async def accept_delete_published_post(call: types.CallbackQuery, state: FSMContext):
    """
    Обработчик подтверждения удаления опубликованного поста (удаление из каналов и БД).

    Аргументы:
        call: Callback-запрос от пользователя.
        state: Контекст состояния FSM.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        logger.warning(
            f"Нет данных состояния для пользователя {call.from_user.id} в accept_delete_published_post"
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
        info_text = await generate_post_info_text(post, is_published=True)

        return await call.message.edit_text(
            info_text, reply_markup=keyboards.manage_published_post(post=post)
        )

    if temp[1] == "accept":
        logger.info(
            f"Пользователь {call.from_user.id} удаляет опубликованный пост {post['id']} (message_id: {post.get('message_id')}) и все связанные публикации"
        )

        parent_id = post.get("post_id") or post.get("id")
        related_posts = await db.published_post.get_published_posts_by_post_id(
            parent_id
        )

        ids_to_delete = []
        for p in related_posts:
            ids_to_delete.append(p.id)
            try:
                await call.bot.delete_message(p.chat_id, p.message_id)
            except TelegramBadRequest as e:
                if (
                    "message to delete not found" in e.message.lower()
                    or "message can't be deleted" in e.message.lower()
                ):
                    logger.warning(
                        f"Сообщение {p.message_id} в {p.chat_id} уже удалено или недоступно для удаления."
                    )
                else:
                    logger.error(
                        f"Ошибка API при удалении сообщения {p.message_id} из {p.chat_id}: {e}"
                    )
            except Exception as e:
                logger.error(
                    f"Непредвиденная ошибка при удалении сообщения {p.message_id} из {p.chat_id}: {e}",
                    exc_info=True,
                )

        if ids_to_delete:
            await db.published_post.soft_delete_published_posts(ids_to_delete)

        try:
            await db.post.delete_post(post["id"])
        except Exception as e:
            logger.error(
                f"Ошибка при окончательном удалении родительского поста {post['id']}: {e}"
            )

        posts = await db.post.get_posts(channel_data["chat_id"], day)

        post_message = data.get("post_message")
        try:
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
        except TelegramBadRequest:
            pass

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
    """
    Создает и настраивает роутер для обработчиков контента.

    Возвращает:
        Router: Настроенный роутер с зарегистрированными обработчиками.
    """
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
