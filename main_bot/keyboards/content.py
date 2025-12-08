"""
Клавиатуры для выбора каналов, контент-плана и управления объектами.
"""
import re
from calendar import monthrange, monthcalendar
from datetime import datetime
from typing import List

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.database.bot_post.model import BotPost
from main_bot.database.channel.model import Channel
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from main_bot.database.story.model import Story
from main_bot.database.user_bot.model import UserBot
from main_bot.database.user_folder.model import UserFolder
from main_bot.database.types import Status
from main_bot.utils.lang.language import text


class InlineContent(InlineKeyboardBuilder):
    """Клавиатуры для выбора каналов, контент-плана и управления объектами"""
    
    @classmethod
    def channels(cls, channels: List[Channel], data: str = "ChoicePostChannel", remover: int = 0):
        kb = cls()
        count_rows = 3

        for a, idx in enumerate(range(remover, len(channels))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=channels[idx].title,
                        callback_data=f'{data}|{channels[idx].chat_id}|{remover}'
                    )
                )

        kb.adjust(1)

        if len(channels) <= count_rows:
            pass

        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('channels:add:button'),
                callback_data=f'{data}|add'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'{data}|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def add_channel(cls, bot_username: str, data: str = "BackAddChannelPost"):
        kb = cls()

        kb.button(
            text=text('channels:add:button'),
            url=f't.me/{bot_username}?startchannel&admin=change_info+post_messages+edit_messages+delete_messages+post_stories+edit_stories+delete_stories+promote_members+invite_users'
        )
        kb.button(
            text=text('back:button'),
            callback_data=f'{data}|cancel'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_channel(cls, data: str = "ManageChannelPost"):
        kb = cls()

        kb.button(
            text=text('channel:delete:button'),
            callback_data=f"{data}|delete"
        )
        kb.button(
            text=text('back:button'),
            callback_data=f"{data}|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_objects(
            cls,
            resources: List[Channel],
            chosen: List[int],
            folders: List[UserFolder],
            chosen_folders: List[int] = [],
            data: str = "ChoicePostChannels",
            remover: int = 0,
    ):
        kb = cls()
        count_rows = 7

        objects = []
        objects.extend(folders)
        objects.extend(resources)

        for a, idx in enumerate(range(remover, len(objects))):
            if a < count_rows:
                if isinstance(objects[idx], Channel):
                    resource_id = objects[idx].chat_id
                    resource_type = "channel"
                    button_text = f'{"🔹" if resource_id in chosen else ""} {objects[idx].title}'
                else:
                    # Folder
                    resource_id = objects[idx].id
                    resource_type = "folder"
                    button_text = f'{"🔹" if resource_id in chosen_folders else "📁"} {objects[idx].title}'

                kb.add(
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f'{data}|{resource_id}|{remover}|{resource_type}'
                    )
                )

        kb.adjust(1)

        if len(objects) <= count_rows:
            pass

        elif len(objects) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(objects):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )

        # Show "Select All" only if there are channels (resources)
        if resources:
            kb.row(
                InlineKeyboardButton(
                    text=text('chosen:cancel_all')
                    if all(r.chat_id in chosen for r in resources)
                    else text('chosen:choice_all'),
                    callback_data=f'{data}|choice_all|{remover}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'{data}|cancel'
            ),
            InlineKeyboardButton(
                text=text('next:button'),
                callback_data=f'{data}|next_step'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_object_content(
            cls,
            channels: List[Channel | UserBot],
            data: str = "ChoiceObjectContentPost",
            remover: int = 0
    ):
        kb = cls()
        count_rows = 6

        for a, idx in enumerate(range(remover, len(channels))):
            if isinstance(channels[idx], Channel):
                resource_id = channels[idx].chat_id
            else:
                resource_id = channels[idx].id

            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=channels[idx].title,
                        callback_data=f'{data}|{resource_id}'
                    )
                )

        kb.adjust(2)

        if len(channels) <= count_rows:
            pass

        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'{data}|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_row_content(
            cls,
            posts: List[Post | Story | BotPost],
            day: datetime,
            show_more: bool = False,
            data: str = "ContentPost",
            days_with_posts: set = None  # Множество дней (int), в которые есть посты
    ):
        kb = cls()

        for post in posts:
            emoji = "⏳"

            if isinstance(post, Post):
                options = post.message_options
                message_text = options.get("text") or options.get("caption")
                callback = f"{data}|{post.id}"
            elif isinstance(post, PublishedPost):
                options = post.message_options
                message_text = options.get("text") or options.get("caption")
                
                if getattr(post, 'status', 'active') == 'deleted':
                    emoji = "🗑"
                else:
                    emoji = "✅"

                callback = f"ContentPublishedPost|{post.id}"
            elif isinstance(post, BotPost):
                options = post.message
                message_text = options.get("text") or options.get("caption")
                emoji = "⏳" if post.status == Status.PENDING else "✅"
                callback = f"{data}|{post.id}"
            else:
                options = post.story_options
                message_text = options.get("caption")
                callback = f"{data}|{post.id}"

            if message_text:
                message_text = message_text.replace('tg-emoji emoji-id', '').replace('</tg-emoji>', '')
                message_text = re.sub(r'<[^>]+>', '', message_text)

            kb.row(
                InlineKeyboardButton(
                    text="{} | {} | {}".format(
                        datetime.fromtimestamp(post.send_time or post.start_timestamp).strftime(
                            "%H:%M"
                        ),
                        emoji,
                        message_text or "Медиа"
                    ),
                    callback_data=callback
                )
            )

        if not show_more:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back_day|1'
                ),
                InlineKeyboardButton(
                    text=f'{day.day} {text("month").get(str(day.month))}',
                    callback_data=f'{data}|...'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next_day|-1'
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("expand:content:button"),
                    callback_data=f'{data}|show_more'
                )
            )

        else:
            kb.row(
                InlineKeyboardButton(
                    text=text("short:content:button"),
                    callback_data=f'{data}|show_more'
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back_month|{monthrange(day.year, day.month)[1]}'
                ),
                InlineKeyboardButton(
                    text=f'{text("other_month").get(str(day.month))} {day.year}',
                    callback_data=f'{data}|...'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next_month|{-monthrange(day.year, day.month)[1]}'
                )
            )

            month = monthcalendar(day.year, day.month)
            for week_idx, week in enumerate(month):
                days = []
                for day_idx, week_day in enumerate(week):
                    if week_day == 0:
                        # Определяем дату из соседнего месяца
                        if week_idx == 0:
                            # Первая неделя - дни из предыдущего месяца
                            prev_month = day.month - 1 if day.month > 1 else 12
                            prev_year = day.year if day.month > 1 else day.year - 1
                            prev_month_days = monthrange(prev_year, prev_month)[1]
                            actual_day = prev_month_days - (6 - day_idx)
                            date_str = f'{prev_year}-{prev_month}-{actual_day}'
                        else:
                            # Последняя неделя - дни из следующего месяца
                            next_month = day.month + 1 if day.month < 12 else 1
                            next_year = day.year if day.month < 12 else day.year + 1
                            # Считаем сколько нулей уже было в этой неделе
                            zeros_before = sum(1 for d in week[:day_idx] if d == 0)
                            actual_day = zeros_before + 1
                            date_str = f'{next_year}-{next_month}-{actual_day}'
                        
                        days.append(
                            InlineKeyboardButton(
                                text=str(actual_day),
                                callback_data=f'{data}|choice_day|{date_str}'
                            )
                        )
                    else:
                        # Проверяем, есть ли посты в этот день
                        has_posts = days_with_posts and week_day in days_with_posts
                        day_text = str(week_day) if week_day != day.day else '🔸'
                        if has_posts and week_day != day.day:
                            day_text = f'{week_day}🔵'  # Добавляем синий круг для дней с постами
                        
                        days.append(
                            InlineKeyboardButton(
                                text=day_text,
                                callback_data=f'{data}|choice_day|{day.year}-{day.month}-{week_day}'
                            )
                        )
                kb.row(*days)

            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back_day|1'
                ),
                InlineKeyboardButton(
                    text=f'{day.day} {text("month").get(str(day.month))}',
                    callback_data=f'{data}|...'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next_day|-1'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("show_all:content{}:button".format(
                    ":story" if data == "ContentStories" else ""
                )),
                callback_data=f'{data}|show_all'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data=f'{data}|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_time_objects(
            cls,
            objects: List[Post | Story | BotPost],
            data: str = "ChoiceTimeObjectContentPost",
            remover: int = 0
    ):
        kb = cls()
        count_rows = 8

        for a, idx in enumerate(range(remover, len(objects))):
            if a < count_rows:
                emoji = "⏳"

                if isinstance(objects[idx], Post):
                    options = objects[idx].message_options
                    message_text = options.get("text") or options.get("caption")
                    obj_data = "ContentPost"
                elif isinstance(objects[idx], PublishedPost):
                    message_text = "Опубликовано"
                    obj_data = "ContentPublishedPost"
                    emoji = "✅"
                elif isinstance(objects[idx], BotPost):
                    options = objects[idx].message
                    message_text = options.get("text") or options.get("caption")
                    obj_data = "ContentBotPost"
                    emoji = "⏳" if objects[idx].status == Status.PENDING else "✅"
                else:
                    options = objects[idx].story_options
                    message_text = options.get("caption")
                    obj_data = "ContentStories"

                if message_text:
                    message_text = message_text.replace('tg-emoji emoji-id', '').replace('</tg-emoji>', '')
                    message_text = re.sub(r'<[^>]+>', '', message_text)

                kb.row(
                    InlineKeyboardButton(
                        text="{} | {} | {}".format(
                            datetime.fromtimestamp(getattr(objects[idx], "send_time")).strftime(
                                "%H:%M"
                            ),
                            emoji,
                            message_text or "Медиа"
                        ),
                        callback_data="{}|{}".format(
                            obj_data,
                            objects[idx].id
                        )
                    )
                )

        kb.adjust(1)

        if len(objects) <= count_rows:
            pass

        elif len(objects) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(objects):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{data}|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'{data}|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def accept_delete_row_content(cls, data: str = "AcceptDeletePost"):
        kb = cls()

        kb.button(
            text=text("manage:post:delete:button"),
            callback_data=f"{data}|accept"
        )
        kb.button(
            text=text("back:button"),
            callback_data=f"{data}|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()
