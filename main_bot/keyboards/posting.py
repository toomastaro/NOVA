"""
Клавиатуры для постинга сообщений в каналы и контент-плана.
"""
from datetime import datetime
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.database.bot_post.model import BotPost
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from main_bot.database.story.model import Story
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import Hide, React, MessageOptions, StoryOptions
from main_bot.keyboards.base import _parse_button


class InlinePosting(InlineKeyboardBuilder):
    """Клавиатуры для постинга в каналы"""
    
    @classmethod
    def posting_menu(cls):
        kb = cls()

        kb.button(
            text=text('posting:create_post'),
            callback_data='MenuPosting|create_post'
        )
        kb.button(
            text=text('posting:channels'),
            callback_data='MenuPosting|channels'
        )
        kb.button(
            text=text('posting:content_plan'),
            callback_data='MenuPosting|content_plan'
        )
        kb.button(
            text=text('back:button'),
            callback_data='MenuPosting|back'
        )

        kb.adjust(1, 1, 1, 1)
        return kb.as_markup()

    @classmethod
    def manage_post(cls, post: Post, show_more: bool = False, is_edit: bool = False):
        kb = cls()
        hide = Hide(hide=post.hide) if post.hide else None
        reactions = React(rows=post.reaction.get("rows")) if post.reaction else None
        options = MessageOptions(**post.message_options)

        if hide:
            for row_hide in hide.hide:
                kb.row(
                    InlineKeyboardButton(
                        text=row_hide.button_name,
                        callback_data="..."
                    )
                )

        if post.buttons:
            for row in post.buttons.split('\n'):
                buttons = []
                for button in row.split('|'):
                    btn_text, btn_url = _parse_button(button)
                    if btn_url:  # Только если есть URL
                        buttons.append(InlineKeyboardButton(text=btn_text, url=btn_url))
                if buttons:
                    kb.row(*buttons)

        if reactions:
            for row in reactions.rows:
                buttons = []
                for react in row.reactions:
                    buttons.append(
                        InlineKeyboardButton(
                            text=react.react,
                            callback_data="..."
                        )
                    )
                kb.row(*buttons)

        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:{}:desc:button".format("edit" if options.text or options.caption else "add")),
                callback_data=f'ManagePost|text|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:{}:media:button".format(
                    "edit" if options.photo or options.video or options.animation else "add")
                ),
                callback_data=f'ManagePost|media|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:add:url_buttons:button"),
                callback_data=f'ManagePost|buttons|{post.id}'
            )
        )


        if not show_more:
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:show_more:button"),
                    callback_data=f'ManagePost|show_more|{post.id}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:hide:button").format(
                        "✅" if hide else "❌"
                    ),
                    callback_data=f'ManagePost|hide|{post.id}'
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:has_spoiler:button").format(
                        "✅" if options.has_spoiler else "❌"
                    ),
                    callback_data=f'ManagePost|has_spoiler|{post.id}'
                ),
                InlineKeyboardButton(
                    text=text("manage:post:media_above:button").format(
                        "✅" if options.show_caption_above_media else "❌"
                    ),
                    callback_data=f'ManagePost|media_above|{post.id}'
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:pin:button").format(
                        "✅" if post.pin_time else "❌"
                    ),
                    callback_data=f'ManagePost|pin_time|{post.id}'
                ),
                InlineKeyboardButton(
                    text=text("manage:post:react:button").format(
                        "✅" if reactions else "❌"
                    ),
                    callback_data=f'ManagePost|reaction|{post.id}'
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:notification:button").format(
                        "🔔" if not options.disable_notification else "🔕"
                    ),
                    callback_data=f'ManagePost|notification|{post.id}'
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:hide_more:button"),
                    callback_data=f'ManagePost|show_more|{post.id}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'ManagePost|cancel|{post.id}'
            ),
            InlineKeyboardButton(
                text=text("{}:button".format("save" if is_edit else "next")),
                callback_data=f'ManagePost|next|{post.id}'
            )
        )

        return kb.as_markup()

    @classmethod
    def post_kb(cls, post: Post | PublishedPost | BotPost, is_bot: bool = False):
        kb = cls()

        if post.buttons:
            for row in post.buttons.split('\n'):
                buttons = []
                for button in row.split('|'):
                    btn_text, btn_url = _parse_button(button)
                    if btn_url:  # Только если есть URL
                        buttons.append(InlineKeyboardButton(text=btn_text, url=btn_url))
                if buttons:
                    kb.row(*buttons)

        if not is_bot:
            hide = Hide(hide=post.hide) if post.hide else None
            reactions = React(rows=post.reaction.get("rows")) if post.reaction else None

            if hide:
                for row_hide in hide.hide:
                    kb.row(
                        InlineKeyboardButton(
                            text=row_hide.button_name,
                            callback_data="ClickHide|{}".format(row_hide.id)
                        )
                    )

            if reactions:
                for row in reactions.rows:
                    buttons = []
                    for react in row.reactions:
                        buttons.append(
                            InlineKeyboardButton(
                                text=react.react if not len(react.users) else f"{react.react} {len(react.users)}",
                                callback_data="ClickReact|{}".format(react.id)
                            )
                        )
                    kb.row(*buttons)

        return kb.as_markup()

    @classmethod
    def param_cancel(cls, param: str, data: str = "ParamCancel"):
        kb = cls()

        kb.button(
            text=text('manage:post:delete:param:{}:button'.format(param)),
            callback_data=F"{data}|delete"
        )
        kb.button(
            text=text('back:button'),
            callback_data=F"{data}|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def param_hide(cls, post: Post):
        kb = cls()
        hide = Hide(hide=post.hide) if post.hide else None

        if hide:
            for hide in hide.hide:
                kb.row(
                    InlineKeyboardButton(
                        text=hide.button_name,
                        callback_data='...'
                    )
                )

        kb.button(
            text=text('manage:post:add:param:hide:button'),
            callback_data=F"ParamHide|add"
        )
        kb.button(
            text=text('manage:post:delete:param:hide:button'),
            callback_data=F"ParamCancel|delete"
        )
        kb.button(
            text=text('back:button'),
            callback_data=F"ParamCancel|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def param_hide_back(cls, data: str = "BackButtonHide"):
        kb = cls()

        kb.button(
            text=text('manage:post:back_step:param:hide:button'),
            callback_data=f"{data}|step"
        )
        kb.button(
            text=text('back:button'),
            callback_data=F"{data}|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def finish_params(cls, obj: Post | Story, data: str = "FinishPostParams"):
        kb = cls()

        if isinstance(obj, Post):
            delete_time = obj.delete_time
        else:
            options = StoryOptions(**obj.story_options)
            delete_time = options.period

        kb.button(
            text=text("manage:post:report:button").format(
                "✅" if obj.report else "❌"
            ),
            callback_data=f"{data}|report"
        )

        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(delete_time / 3600)} ч."  # type: ignore
                if delete_time else text("manage:post:del_time:not")
            ),
            callback_data=f"{data}|delete_time"
        )

        if isinstance(obj, Post):
            kb.button(
                text=text("manage:post:add:cpm:button").format(
                    f"{obj.cpm_price}₽" if obj.cpm_price else "❌"
                ),
                callback_data=f"{data}|cpm_price"
            )

        kb.button(
            text=text("manage:post:send_time:button"),
            callback_data=f"{data}|send_time"
        )
        kb.button(
            text=text("manage:post:public:button"),
            callback_data=f"{data}|public"
        )
        kb.button(
            text=text('back:button'),
            callback_data=F"{data}|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_delete_time(cls):
        kb = cls()

        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:delete:param:delete_time:button"),
                callback_data=f'GetDeleteTimePost|off'
            )
        )
        groups = [
            [1, 15, 30, 45],      # минуты
            [1, 2, 4, 6],      # часы
            [6, 8, 10, 12],    # часы
            [18, 24, 48, 72],  # часы
        ]
        
        # Первый ряд - минуты
        kb.row(*[
            InlineKeyboardButton(
                text=f'{m} мин.',
                callback_data=f'GetDeleteTimePost|{m * 60}'
            ) for m in groups[0]
        ])
        
        # Остальные ряды - часы
        for group in groups[1:]:
            kb.row(*[
                InlineKeyboardButton(
                    text=f'{h} ч.',
                    callback_data=f'GetDeleteTimePost|{h * 3600}'
                ) for h in group
            ])
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data=f'GetDeleteTimePost|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def accept_date(cls, data: str = "AcceptPost"):
        kb = cls()

        kb.button(
            text=text("manage:post:send_time:button"),
            callback_data=f"{data}|send_time"
        )
        kb.button(
            text=text("back:button"),
            callback_data=f"{data}|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def accept_public(cls, data: str = "AcceptPost"):
        kb = cls()

        kb.button(
            text=text("manage:post:public:button"),
            callback_data=f"{data}|public"
        )
        kb.button(
            text=text("back:button"),
            callback_data=f"{data}|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def create_finish(cls, data: str = "MenuPosting"):
        kb = cls()

        value = "posting"
        if data == "MenuStories":
            value = "stories"
        if data == "MenuBots":
            value = "bots"

        kb.button(
            text=text(f'{value}:create_post'),
            callback_data=f'{data}|create_post'
        )
        kb.button(
            text=text(f'{value}:content_plan'),
            callback_data=f'{data}|content_plan'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_remain_post(cls, post: Post, is_published: bool = False):
        kb = cls()

        # Check for deleted status
        is_deleted = getattr(post, 'status', 'active') == 'deleted'

        if is_deleted:
            deleted_at = getattr(post, 'deleted_at', None)
            del_time_str = datetime.fromtimestamp(deleted_at).strftime("%d.%m.%Y %H:%M") if deleted_at else "N/A"
            kb.button(
                text=f"🗑 Удален: {del_time_str}",
                callback_data="noop"
            )
            kb.button(
                text=text("back:button"),
                callback_data="ManageRemainPost|cancel"
            )
            kb.adjust(1)
            return kb.as_markup()

        if not is_published:
            kb.button(
                text=text("manage:post:send_time").format(
                    datetime.fromtimestamp(post.send_time).strftime("%d.%m.%Y %H:%M")
                ),
                callback_data="FinishPostParams|send_time"
            )
        
        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(post.delete_time / 3600)} ч."  # type: ignore
                if post.delete_time else text("manage:post:del_time:not")
            ),
            callback_data="FinishPostParams|delete_time"
        )
        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManageRemainPost|change"
        )
        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManageRemainPost|delete"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ManageRemainPost|cancel"
        )
        
        if not is_published:
            kb.button(
                text=text("manage:post:public:button"),
                callback_data="FinishPostParams|public"
            )

        kb.adjust(1, 1, 2)
        return kb.as_markup()

    @classmethod
    def manage_published_post(cls, post: PublishedPost):
        kb = cls()

        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManagePublishedPost|delete"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ManagePublishedPost|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()
