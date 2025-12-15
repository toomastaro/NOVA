"""
Клавиатуры для работы со сторис.
"""
from datetime import datetime
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.database.story.model import Story
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import StoryOptions


class InlineStories(InlineKeyboardBuilder):
    """Клавиатуры для сторис"""
    
    @classmethod
    def stories_menu(cls):
        kb = cls()

        kb.button(
            text=text('stories:create_post'),
            callback_data='MenuStories|create_post'
        )
        kb.button(
            text=text('stories:content_plan'),
            callback_data='MenuStories|content_plan'
        )
        kb.button(
            text=text('channels:add:button'),
            callback_data='ChoicePostChannel|add'
        )

        kb.adjust(1, 1, 1)
        return kb.as_markup()

    @classmethod
    def manage_story(cls, post: Story, is_edit: bool = False):
        kb = cls()
        options = StoryOptions(**post.story_options)

        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:{}:desc:button".format("edit" if options.caption else "add")),
                callback_data=f'ManageStory|text|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:edit:media:button"),
                callback_data=f'ManageStory|media|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:story:noforwards:button").format(
                    "✅" if options.noforwards else "❌"
                ),
                callback_data=f'ManageStory|noforwards|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:story:pinned:button").format(
                    "✅" if options.pinned else "❌"
                ),
                callback_data=f'ManageStory|pinned|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'ManageStory|cancel|{post.id}'
            ),
            InlineKeyboardButton(
                text=text("{}:button".format("save" if is_edit else "next")),
                callback_data=f'ManageStory|next|{post.id}'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_delete_time_story(cls):
        kb = cls()

        periods = [6, 12, 24, 48]

        row = []
        for period in periods:
            row.append(
                InlineKeyboardButton(
                    text=f"{period} ч.",
                    callback_data="GetDeleteTimeStories|{}".format(
                        period * 3600
                    )
                )
            )

        kb.row(*row)
        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data="GetDeleteTimeStories|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def manage_remain_story(cls, post: Story):
        kb = cls()
        options = StoryOptions(**post.story_options)

        kb.button(
            text=text("manage:post:send_time").format(
                datetime.fromtimestamp(post.send_time).strftime("%d.%m.%Y %H:%M")
            ),
            callback_data="FinishStoriesParams|send_time"
        )
        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(options.period / 3600)} ч."  # type: ignore
                if options.period else text("manage:post:del_time:not")
            ),
            callback_data="FinishStoriesParams|delete_time"
        )
        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManageRemainStories|change"
        )
        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManageRemainStories|delete"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ManageRemainStories|cancel"
        )
        kb.button(
            text=text("manage:post:public:button"),
            callback_data="FinishStoriesParams|public"
        )

        kb.adjust(1, 1, 2)
        return kb.as_markup()

    @classmethod
    def story_kb(cls, post: Story):
        return None
