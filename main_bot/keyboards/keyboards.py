import re
from calendar import monthrange, monthcalendar
from datetime import datetime
from typing import List

from aiogram.types import InlineKeyboardButton, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from main_bot.database.bot_post.model import BotPost
from main_bot.database.channel.model import Channel
from main_bot.database.channel_bot_captcha.model import ChannelCaptcha
from main_bot.database.channel_bot_hello.model import ChannelHelloMessage
from main_bot.database.channel_bot_settings.model import ChannelBotSetting
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from main_bot.database.story.model import Story
from main_bot.database.types import FolderType, Status
from main_bot.database.user_bot.model import UserBot
from main_bot.database.user_folder.model import UserFolder
from main_bot.utils.lang.language import text
from config import Config
from main_bot.utils.schemas import Hide, React, MessageOptions, StoryOptions, HelloAnswer, Answer, Protect, ByeAnswer, \
    MessageOptionsCaptcha, CaptchaObj, MessageOptionsHello


class Reply:
    @classmethod
    def menu(cls):
        kb = ReplyKeyboardBuilder()

        kb.button(text=text('reply_menu:novastat'))
        kb.button(text=text('reply_menu:exchange_rate'))
        kb.button(text=text('reply_menu:posting'))
        kb.button(text=text('reply_menu:story'))
        kb.button(text=text('reply_menu:bots'))
        kb.button(text=text('reply_menu:support'))
        kb.button(text=text('reply_menu:profile'))

        if Config.ENABLE_AD_BUY_MODULE:
            kb.button(text="Рекламные креативы")
            kb.button(text="Рекламные закупы")

        kb.adjust(2, 2, 1, 2)
        return kb.as_markup(
            resize_keyboard=True,
        )
        

    @classmethod
    def captcha_kb(cls, buttons: str, resize: bool = True):
        kb = ReplyKeyboardBuilder()

        for row in buttons.split('\n'):
            buttons = [
                KeyboardButton(
                    text=button.strip(),
                ) for button in row.split('|')
            ]
            kb.row(*buttons)

        return kb.as_markup(
            resize_keyboard=resize
        )


class InlineExchangeRate(InlineKeyboardBuilder):
    @classmethod
    def set_exchange_rate(cls):
        kb = cls()

        kb.button(
            text=text('exchange_rate:start_exchange_rate:settings:button'),
            callback_data='MenuExchangeRate|settings'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choose_exchange_rate(cls, source_list, chosen_exchange_rate_id):
        kb = cls()
        for s in source_list:
            kb.button(
                text=f"{s.name}: {s.rate:.2f}₽{' ✅' if int(chosen_exchange_rate_id) == int(s.id) else ''}",
                callback_data=f'MenuExchangeRate|settings|choose_exchange_rate|{s.id}'
            )

        kb.button(
            text=text("exchange_rate:start_exchange_rate:settings:back:button"),
            callback_data=f'MenuExchangeRate|settings|back'
        )

        kb.adjust(*([1]*(len(source_list) + 1)))
        return kb.as_markup()


class InlinePosting(InlineKeyboardBuilder):
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

        kb.adjust(2, 1)
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
                buttons = [
                    InlineKeyboardButton(
                        text=button.split('—')[0].strip(),
                        url=button.split('—')[1].strip()
                    ) for button in row.split('|')
                ]
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
                buttons = [
                    InlineKeyboardButton(
                        text=button.split('—')[0].strip(),
                        url=button.split('—')[1].strip()
                    ) for button in row.split('|')
                ]
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

        if isinstance(obj, Post):
            kb.button(
                text=text("manage:post:add:cpm:button").format(
                    f"{obj.cpm_price}₽" if obj.cpm_price else "❌"
                ),
                callback_data=f"{data}|cpm_price"
            )

        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(delete_time / 3600)} ч."  # type: ignore
                if delete_time else text("manage:post:del_time:not")
            ),
            callback_data=f"{data}|delete_time"
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

        kb.adjust(1, 1, 2, 1)
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
            [1, 2, 3, 4],      # минуты
            [1, 2, 3, 4],      # часы
            [6, 8, 10, 12],    # часы
            [18, 24, 36, 48],  # часы
            [72, 96, 120, 144] # часы
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


class InlineStories(InlineKeyboardBuilder):
    @classmethod
    def stories_menu(cls):
        kb = cls()

        kb.button(
            text=text('stories:create_post'),
            callback_data='MenuStories|create_post'
        )
        kb.button(
            text=text('stories:channels'),
            callback_data='MenuStories|channels'
        )
        kb.button(
            text=text('stories:content_plan'),
            callback_data='MenuStories|content_plan'
        )

        kb.adjust(2, 1)
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


class InlineBots(InlineKeyboardBuilder):
    @classmethod
    def bots_menu(cls):
        kb = cls()

        kb.button(
            text=text('bots:create_post'),
            callback_data='MenuBots|create_post'
        )
        kb.button(
            text=text('bots:bots'),
            callback_data='MenuBots|bots'
        )
        kb.button(
            text=text('bots:content_plan'),
            callback_data='MenuBots|content_plan'
        )

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def choice_bots(cls, bots: List[UserBot], data: str = "ChoiceBots", remover: int = 0):
        kb = cls()
        count_rows = 3

        for a, idx in enumerate(range(remover, len(bots))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=bots[idx].title,
                        callback_data=f'{data}|{bots[idx].id}|{remover}'
                    )
                )

        kb.adjust(1)

        if len(bots) <= count_rows:
            pass

        elif len(bots) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{data}|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(bots):
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
                text=text('bots:add:button'),
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
    def manage_bot_post(cls, post: BotPost, is_edit: bool = False):
        kb = cls()
        options = MessageOptionsHello(**post.message)

        if options.reply_markup:
            for row in options.reply_markup.inline_keyboard:
                kb.row(*row)

        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:{}:desc:button".format("edit" if options.caption or options.text else "add")),
                callback_data=f'ManageBotPost|text|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:edit:media:button"),
                callback_data=f'ManageBotPost|media|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:add:url_buttons:button"),
                callback_data=f'ManageBotPost|buttons|{post.id}'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'ManageBotPost|cancel|{post.id}'
            ),
            InlineKeyboardButton(
                text=text("{}:button".format("save" if is_edit else "next")),
                callback_data=f'ManageBotPost|next|{post.id}'
            )
        )

        return kb.as_markup()

    @classmethod
    def finish_bot_post_params(cls, obj: BotPost, data: str = "FinishBotPostParams"):
        kb = cls()

        kb.button(
            text=text("manage:post:report:button").format(
                "✅" if obj.report else "❌"
            ),
            callback_data=f"{data}|report"
        )
        kb.button(
            text=text("manage_hello_msg:text_with_name:button").format(
                "✅" if obj.text_with_name else "❌"
            ),
            callback_data=f"{data}|text_with_name"
        )
        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(obj.delete_time / 3600)} ч."  # type: ignore
                if obj.delete_time else text("manage:post:del_time:not")
            ),
            callback_data=f"{data}|delete_time"
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

        kb.adjust(1, 1, 1, 2, 1)
        return kb.as_markup()

    @classmethod
    def choice_delete_time_bot_post(cls):
        kb = cls()

        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:delete:param:delete_time:button"),
                callback_data=f'GetDeleteTimeBotPost|off'
            )
        )
        groups = [
            [12, 24, 36, 40],
        ]
        for group in groups:
            kb.row(*[
                InlineKeyboardButton(
                    text=f'{h} ч.',
                    callback_data=f'GetDeleteTimeBotPost|{h * 3600}'
                ) for h in group
            ])

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data=f'GetDeleteTimeBotPost|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_send_time_bot_post(cls, day: datetime, data: str = "SendTimeBotPost"):
        kb = cls()

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
        for week in month:
            days = []
            for week_day in week:
                days.append(
                    InlineKeyboardButton(
                        text='...',
                        callback_data=f'{data}|...'
                    ) if week_day == 0 else InlineKeyboardButton(
                        text=str(week_day) if week_day != day.day else '🔸',
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
                text=text("back:button"),
                callback_data=f'{data}|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def manage_remain_bot_post(cls, post: BotPost):
        kb = cls()

        kb.button(
            text=text("manage:post:send_time").format(
                datetime.fromtimestamp(post.send_time).strftime("%d.%m.%Y %H:%M")
            ),
            callback_data="FinishBotPostParams|send_time"
        )
        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManageRemainBotPost|change"
        )
        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManageRemainBotPost|delete"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ManageRemainBotPost|cancel"
        )
        kb.button(
            text=text("manage:post:public:button"),
            callback_data="FinishBotPostParams|public"
        )

        kb.adjust(1, 2)
        return kb.as_markup()

    @classmethod
    def manage_bot(cls, user_bot: UserBot, status: bool):
        kb = cls()

        kb.button(
            text=text("manage:bot:manage"),
            callback_data="ManageBot|settings"
        )

        kb.button(
            text=text("manage:bot:{}_channel".format("add")),
            url="t.me/{}?startchannel&admin=change_info+post_messages+edit_messages+delete_messages+post_stories+edit_stories+delete_stories+promote_members+invite_users".format(user_bot.username)
        )
        kb.button(
            text=text("manage:bot:refresh_token"),
            callback_data="ManageBot|refresh_token"
        )
        kb.button(
            text=text("manage:bot:check_token"),
            callback_data="ManageBot|check_token"
        )
        kb.button(
            text=text("manage:bot:import_db"),
            callback_data="ManageBot|import_db"
        )
        kb.button(
            text=text("manage:bot:export_db"),
            callback_data="ManageBot|export_db"
        )
        kb.button(
            text=text("manage:bot:set_{}".format("off" if status else "on")),
            callback_data="ManageBot|status"
        )
        kb.button(
            text=text("manage:bot:delete"),
            callback_data="ManageBot|delete"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ManageBot|cancel"
        )

        kb.adjust(1, 1, 1, 1, 2, 1)
        return kb.as_markup()

    @classmethod
    def export_type(cls):
        kb = cls()

        kb.button(
            text=text("export:type:txt"),
            callback_data="ExportType|txt"
        )
        kb.button(
            text=text("export:type:csv"),
            callback_data="ExportType|csv"
        )
        kb.button(
            text=text("export:type:xlsx"),
            callback_data="ExportType|xlsx"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ExportType|cancel"
        )

        kb.adjust(1, 2, 1)
        return kb.as_markup()


class InlineBotSetting(InlineKeyboardBuilder):
    @classmethod
    def choice_cleaner_type(cls):
        kb = cls()

        kb.button(
            text=text("cleaner:application:button"),
            callback_data="ChoiceCleanerType|application"
        )
        kb.button(
            text=text("cleaner:ban:button"),
            callback_data="ChoiceCleanerType|ban"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ChoiceCleanerType|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_cloner_setting(cls, chosen):
        kb = cls()

        settings = {
            0: "Авто-прием",
            1: "Капча",
            2: "Приветствия",
            3: "Прощание",
        }

        for key, value in settings.items():
            if key in chosen:
                value = "✅ " + value

            kb.button(
                text=value,
                callback_data=f"ChoiceClonerSetting|{key}"
            )

        kb.adjust(1)

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data="ChoiceClonerSetting|cancel"
            ),
            InlineKeyboardButton(
                text=text("clone:start:button"),
                callback_data="ChoiceClonerSetting|clone"
            )
        )
        return kb.as_markup()

    @classmethod
    def choice_channel_for_cloner(cls, channels: List[Channel], chosen: list, remover: int = 0):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(channels))):
            if a < count_rows:

                button_text = channels[idx].title
                if channels[idx].chat_id in chosen:
                    button_text = "✅ " + button_text

                kb.add(
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f'ChoiceClonerTarget|{channels[idx].chat_id}|{remover}'
                    )
                )

        kb.adjust(2)

        if len(channels) <= count_rows:
            pass

        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceClonerTarget|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceClonerTarget|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceClonerTarget|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceClonerTarget|next|{remover + count_rows}'
                )
            )

        if channels:
            kb.row(
                InlineKeyboardButton(
                    text=text('chosen:cancel_all') if len(chosen) == len(channels) else text('chosen:choice_all'),
                    callback_data=f'ChoiceClonerTarget|choice_all|{remover}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'ChoiceClonerTarget|cancel'
            ),
            InlineKeyboardButton(
                text=text('next:button'),
                callback_data=f'ChoiceClonerTarget|next_step'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_channel_captcha(cls, channel_captcha_list: List[ChannelCaptcha], active_captcha: int, remover: int = 0):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(channel_captcha_list))):
            if a < count_rows:
                captcha_obj = CaptchaObj.from_orm(channel_captcha_list[idx])
                button_text = captcha_obj.message.text or captcha_obj.message.caption or "Медиа"
                setting_text = "Настроить"

                if active_captcha == channel_captcha_list[idx].id:
                    button_text = "✅ " + button_text
                    setting_text = setting_text + f" ⌛️ {captcha_obj.delay}"

                kb.row(
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f'ChoiceCaptcha|choice|{channel_captcha_list[idx].id}'
                    ),
                    InlineKeyboardButton(
                        text=setting_text,
                        callback_data=f'ChoiceCaptcha|change|{channel_captcha_list[idx].id}'
                    )
                )

        kb.adjust(2)

        if len(channel_captcha_list) <= count_rows:
            pass

        elif len(channel_captcha_list) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceCaptcha|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(channel_captcha_list):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceCaptcha|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceCaptcha|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceCaptcha|next|{remover + count_rows}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("add:button"),
                callback_data="ChoiceCaptcha|add"
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'ChoiceCaptcha|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def manage_captcha(cls, captcha: ChannelCaptcha):
        kb = cls()

        kb.button(
            text=text("application:delay:button").format(
                captcha.delay
            ),
            callback_data="ManageCaptcha|delay"
        )
        kb.button(
            text=text("change:button"),
            callback_data="ManageCaptcha|change"
        )
        kb.button(
            text=text("delete:button"),
            callback_data="ManageCaptcha|delete"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ManageCaptcha|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_captcha_delay(cls, current: int):
        kb = cls()

        variants = [
            (5, "5сек"),
            (10, "10 сек"),
            (20, "20 сек"),
            (30, "30 сек"),
            (40, "40 сек"),
            (50, "50 сек"),
            (60, "1 мин"),
            (90, "1.5 мин"),
            (120, "2 мин"),
            (150, "2.5 мин"),
            (180, "3 мин"),
            (240, "4 мин"),
            (0, "Без повтора"),
        ]

        for seconds, label in variants:
            if current == seconds:
                label = "✅ " + label

            kb.button(
                text=label,
                callback_data=f"ChoiceCaptchaDelay|{seconds}"
            )

        kb.adjust(3)
        kb.row(
            InlineKeyboardButton(text=text("back:button"), callback_data="ChoiceCaptchaDelay|cancel"),
        )

        return kb.as_markup()

    @classmethod
    def manage_captcha_post(cls, resize: bool = True):
        kb = cls()

        kb.button(
            text="Кнопки",
            callback_data="ManagePostCaptcha|reply_buttons"
        )
        kb.button(
            text="Широкие кнопки: {}".format(
                "✅" if not resize else "❌"
            ),
            callback_data="ManagePostCaptcha|resize"
        )
        kb.button(
            text=text("manage:hello:edit:desc:button"),
            callback_data="ManagePostCaptcha|message"
        )
        kb.button(
            text=text('back:button'),
            callback_data=f'ManagePostCaptcha|cancel'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_hello_message(cls, hello_message: ChannelHelloMessage):
        kb = cls()

        kb.button(
            text=text("on" if hello_message.is_active else "off"),
            callback_data="ManageHelloMessage|on"
        )
        kb.button(
            text=text("application:delay:button").format(
                hello_message.delay
            ),
            callback_data="ManageHelloMessage|delay"
        )
        kb.button(
            text=text("manage_hello_msg:text_with_name:button").format(
                "✅" if hello_message.text_with_name else "❌"
            ),
            callback_data="ManageHelloMessage|text_with_name"
        )
        kb.button(
            text=text("change:button"),
            callback_data="ManageHelloMessage|change"
        )
        kb.button(
            text=text("delete:button"),
            callback_data="ManageHelloMessage|delete"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ManageHelloMessage|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_hello_message_post(cls):
        kb = cls()

        kb.button(
            text=text("manage:post:add:url_buttons:button"),
            callback_data="ManagePostHelloMessage|url_buttons"
        )
        kb.button(
            text=text("manage:hello:edit:desc:button"),
            callback_data="ManagePostHelloMessage|message"
        )
        kb.button(
            text=text('back:button'),
            callback_data=f'ManagePostHelloMessage|cancel'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def hello_kb(cls, buttons: str):
        kb = cls()

        for row in buttons.split('\n'):
            buttons = [
                InlineKeyboardButton(
                    text=button.split('—')[0].strip(),
                    url=button.split('—')[1].strip()
                ) for button in row.split('|')
            ]
            kb.row(*buttons)

        return kb.as_markup()

    @classmethod
    def choice_invite_url(cls, invite_urls: List[str], remover: int = 0):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(invite_urls))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=invite_urls[idx],
                        callback_data=f'ChoiceInviteUrlApplication|{invite_urls[idx]}'
                    )
                )

        kb.adjust(1)

        if len(invite_urls) <= count_rows:
            pass

        elif len(invite_urls) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceInviteUrlApplication|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(invite_urls):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceInviteUrlApplication|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceInviteUrlApplication|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceInviteUrlApplication|next|{remover + count_rows}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'ChoiceInviteUrlApplication|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_channel_for_setting(cls, channels: List[Channel], data: str = "ChoiceBotSettingChannel", remover: int = 0):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(channels))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=channels[idx].title,
                        callback_data=f'{data}|{channels[idx].chat_id}'
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
    def add_channel(cls, bot_username: str, data: str = "BackAddChannel"):
        kb = cls()

        kb.button(
            text=text('add_channel:button'),
            url=f't.me/{bot_username}?startchannel&admin=change_info+post_messages+edit_messages+delete_messages+post_stories+edit_stories+delete_stories+promote_members+invite_users'
        )
        kb.button(
            text=text('add_channel_later:button'),
            callback_data=f'{data}|menu'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def bot_setting_menu(cls, channel_settings: ChannelBotSetting):
        kb = cls()

        bye = ByeAnswer(**channel_settings.bye)

        kb.button(
            text=text("bot_menu:application").format(
                "✅" if channel_settings.auto_approve else "❌"
            ),
            callback_data="BotSettingMenu|application"
        )
        kb.button(
            text=text("bot_menu:hello"),
            callback_data="BotSettingMenu|hello"
        )
        kb.button(
            text=text("bot_menu:captcha").format(
                "✅" if channel_settings.active_captcha_id else "❌"
            ),
            callback_data="BotSettingMenu|captcha"
        )
        kb.button(
            text=text("bot_menu:cloner"),
            callback_data="BotSettingMenu|clone"
        )
        kb.button(
            text=text("bot_menu:bye").format(
                "✅" if bye.active else "❌"
            ),
            callback_data="BotSettingMenu|bye"
        )
        kb.button(
            text=text("bot_menu:cleaner"),
            callback_data="BotSettingMenu|cleaner"
        )
        kb.button(
            text=text("bot_menu:update"),
            callback_data="BotSettingMenu|update"
        )
        kb.button(
            text=text("back:button"),
            callback_data="BotSettingMenu|back"
        )

        kb.adjust(1, 1, 2)
        return kb.as_markup()

    @classmethod
    def param_answers_back(cls, data: str = "BackAddAnswer"):
        kb = cls()

        kb.button(
            text=text('back:step'),
            callback_data=f"{data}|step"
        )
        kb.button(
            text=text('back:button'),
            callback_data=F"{data}|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_answer_user(cls, obj: HelloAnswer, data: str = "ManageHello"):
        kb = cls()

        kb.button(
            text=text("{}:button".format("on" if obj.active else "off")),
            callback_data=f"{data}|active"
        )
        kb.button(
            text=text("{}:button".format("add" if not obj.message else "delete")),
            callback_data=f"{data}|message"
        )
        kb.button(
            text=text("check:button"),
            callback_data=f"{data}|check"
        )
        kb.button(
            text=text("back:button"),
            callback_data=f"{data}|cancel"
        )

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def manage_hello_messages(cls, hello_messages: List[ChannelHelloMessage], remover: int = 0):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(hello_messages))):
            if a < count_rows:
                hello = HelloAnswer.from_orm(hello_messages[idx])

                button_text = "{} сообщение {} Задержка: {}".format(
                    a + 1,
                    "✅" if hello.is_active else "❌",
                    hello.delay
                )

                kb.add(
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f'ChoiceHelloMessage|{hello_messages[idx].id}|{a + 1}'
                    )
                )

        kb.adjust(1)

        if len(hello_messages) <= count_rows:
            pass

        elif len(hello_messages) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceHelloMessage|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(hello_messages):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceHelloMessage|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceHelloMessage|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceHelloMessage|next|{remover + count_rows}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("add:button"),
                callback_data="ChoiceHelloMessage|add"
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data=f'ChoiceHelloMessage|cancel'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_hello_message_delay(cls, current: int):
        kb = cls()

        variants = [
            (1, "После капчи"),
            (5, "5сек"),
            (10, "10 сек"),
            (20, "20 сек"),
            (30, "30 сек"),
            (40, "40 сек"),
            (50, "50 сек"),
            (60, "1 мин"),
            (90, "1.5 мин"),
            (120, "2 мин"),
            (150, "2.5 мин"),
            (180, "3 мин"),
            (240, "4 мин"),
            (0, "Без задержки"),
        ]

        for seconds, label in variants:
            if current == seconds:
                label = "✅ " + label

            kb.button(
                text=label,
                callback_data=f"ChoiceHelloMessageDelay|{seconds}"
            )

        kb.adjust(3)
        kb.row(
            InlineKeyboardButton(text=text("back:button"), callback_data="ChoiceHelloMessageDelay|cancel"),
        )

        return kb.as_markup()

    @classmethod
    def manage_application(cls, not_approve_count: int, auto_approve: bool, delay_approve: int):
        kb = cls()

        kb.button(
            text=text("application:count:button").format(
                not_approve_count
            ),
            callback_data="ManageApplication|..."
        )
        kb.button(
            text=text("application:approve:button").format(
                "✅" if auto_approve else "❌"
            ),
            callback_data="ManageApplication|auto_approve"
        )
        kb.button(
            text=text("application:manual_approve:button"),
            callback_data="ManageApplication|manual_approve"
        )

        variants_dict = {
            1: "После капчи",
            5: "5сек",
            15: "15сек",
            30: "30сек",
            60: "1мин",
            300: "5мин",
            1800: "30мин",
            3600: "1 час",
            21600: "6 часов",
            43200: "12 часов",
            86400: "1 день",
            172800: "2 дня",
            345600: "4 дня",
            0: "Без задержки",
        }

        kb.button(
            text=text("application:delay:button").format(
                variants_dict[delay_approve]
            ),
            callback_data="ManageApplication|delay"
        )
        kb.button(
            text=text("back:button"),
            callback_data=f"ManageApplication|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_application_delay(cls, current: int):
        kb = cls()

        variants = [
            (1, "После капчи"),
            (5, "5сек"),
            (15, "15сек"),
            (30, "30сек"),
            (60, "1мин"),
            (60 * 5, "5мин"),
            (60 * 30, "30мин"),
            (60 * 60, "1 час"),
            (60 * 60 * 6, "6 часов"),
            (60 * 60 * 12, "12 часов"),
            (60 * 60 * 24, "1 день"),
            (60 * 60 * 24 * 2, "2 дня"),
            (60 * 60 * 24 * 4, "4 дня"),
            (0, "Без задержки"),
        ]

        for seconds, label in variants:
            if current == seconds:
                label = "✅ " + label

            kb.button(
                text=label,
                callback_data=f"ChoiceApplicationDelay|{seconds}"
            )

        kb.adjust(3)
        kb.row(
            InlineKeyboardButton(text=text("back:button"), callback_data="ChoiceApplicationDelay|cancel"),
        )

        return kb.as_markup()

    @classmethod
    def choice_manual_approve(cls):
        kb = cls()

        kb.button(
            text=text("application:manual_approve:all"),
            callback_data="ChoiceManualApprove|all"
        )
        kb.button(
            text=text("application:manual_approve:part"),
            callback_data="ChoiceManualApprove|part"
        )
        kb.button(
            text=text("application:manual_approve:invite_url"),
            callback_data="ChoiceManualApprove|invite_url"
        )
        kb.button(
            text=text("back:button"),
            callback_data="ChoiceManualApprove|cancel"
        )

        kb.adjust(2, 1)
        return kb.as_markup()


class InlineProfile(InlineKeyboardBuilder):
    @classmethod
    def profile_menu(cls):
        kb = cls()

        kb.button(
            text=text('profile:balance'),
            callback_data='MenuProfile|balance'
        )
        kb.button(
            text=text('profile:subscribe'),
            callback_data='MenuProfile|subscribe'
        )
        kb.button(
            text=text('profile:referral'),
            callback_data='MenuProfile|referral'
        )
        kb.button(
            text=text('profile:settings'),
            callback_data='MenuProfile|settings'
        )

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def profile_balance(cls):
        kb = cls()

        kb.button(
            text=text('balance:top_up'),
            callback_data='Balance|top_up'
        )
        kb.button(
            text=text('back:button'),
            callback_data='Balance|back'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def profile_sub_choice(cls):
        kb = cls()

        # kb.button(
        #     text=text('subscribe:posting'),
        #     callback_data='Subscribe|posting'
        # )
        # kb.button(
        #     text=text('subscribe:stories'),
        #     callback_data='Subscribe|stories'
        # )
        # kb.button(
        #     text=text('subscribe:bots'),
        #     callback_data='Subscribe|bots'
        # )
        kb.button(
            text=text('subscribe:channels'),
            callback_data='Subscribe|channels'
        )
        kb.button(
            text=text('back:button'),
            callback_data='Subscribe|cancel'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def profile_setting(cls):
        kb = cls()

        kb.button(
            text=text('setting:timezone'),
            callback_data='Setting|timezone'
        )
        kb.button(
            text=text('setting:folders'),
            callback_data='Setting|folders'
        )
        kb.button(
            text=text('back:button'),
            callback_data='Setting|back'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_payment_method(cls, data: str, has_promo: bool = False, is_subscribe: bool = False):
        kb = cls()

        adjust = []
        if is_subscribe:
            kb.button(
                text=text('payment:method:align_sub'),
                callback_data=f'{data}|align_sub'
            )
            kb.button(
                text=text('payment:method:balance'),
                callback_data=f'{data}|balance'
            )
            adjust.extend([1, 1])

        if not has_promo:
            kb.button(
                text=text('payment:method:promo'),
                callback_data=f'{data}|promo'
            )
            adjust.append(1)

        kb.button(
            text=text('payment:method:stars'),
            callback_data=f'{data}|stars'
        )
        kb.button(
            text=text('payment:method:crypto_bot'),
            callback_data=f'{data}|crypto_bot'
        )
        kb.button(
            text=text('back:button'),
            callback_data=f'{data}|back'
        )

        adjust.extend([2, 1])
        kb.adjust(*adjust)
        return kb.as_markup()

    @classmethod
    def choice_period(cls, service: str):
        kb = cls()

        # === СТАРАЯ ЛОГИКА (закомментировано для отката) ===
        # tariffs = Config.TARIFFS.get(service)
        # for key in tariffs:
        #     kb.button(
        #         text=tariffs[key]['name'],
        #         callback_data='ChoiceSubscribePeriod|{}'.format(
        #             key
        #         )
        #     )

        # === НОВАЯ ЛОГИКА (один тариф) ===
        tariffs = Config.TARIFFS.get(service)
        # Берем тариф с ID 0 (единственный)
        kb.button(
            text=tariffs[0]['name'],
            callback_data='ChoiceSubscribePeriod|0'
        )

        kb.button(
            text=text('back:button'),
            callback_data='ChoiceSubscribePeriod|back'
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def align_sub(cls, sub_objects: List[Channel], chosen: List[Channel], remover: int = 0):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(sub_objects))):
            if a < count_rows:
                resource_id = sub_objects[idx].chat_id

                kb.add(
                    InlineKeyboardButton(
                        text=f'{"🔹" if resource_id in chosen else ""} {sub_objects[idx].title}',
                        callback_data=f'ChoiceResourceAlignSubscribe|{resource_id}|{remover}'
                    )
                )

        kb.adjust(2)

        if len(sub_objects) <= count_rows:
            pass

        elif len(sub_objects) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceResourceAlignSubscribe|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(sub_objects):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceResourceAlignSubscribe|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceResourceAlignSubscribe|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceResourceAlignSubscribe|next|{remover + count_rows}'
                )
            )

        if sub_objects:
            kb.row(
                InlineKeyboardButton(
                    text=text('chosen:cancel_all') if len(chosen) == len(sub_objects) else text('chosen:choice_all'),
                    callback_data=f'ChoiceResourceAlignSubscribe|choice_all|{remover}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data='ChoiceResourceAlignSubscribe|cancel'
            ),
            InlineKeyboardButton(
                text=text('save:button'),
                callback_data='ChoiceResourceAlignSubscribe|align'
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_object_subscribe(
            cls,
            resources: List[Channel | UserBot],
            chosen: List[Channel | UserBot],
            remover: int = 0
    ):
        kb = cls()
        count_rows = 6

        for a, idx in enumerate(range(remover, len(resources))):
            if a < count_rows:
                if isinstance(resources[idx], Channel):
                    resource_id = resources[idx].id
                else:
                    resource_id = resources[idx].id

                kb.add(
                    InlineKeyboardButton(
                        text=f'{"🔹" if resource_id in chosen else ""} {resources[idx].title}',
                        callback_data=f'ChoiceResourceSubscribe|{resource_id}|{remover}'
                    )
                )

        kb.adjust(2)

        if len(resources) <= count_rows:
            pass

        elif len(resources) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceResourceSubscribe|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(resources):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceResourceSubscribe|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceResourceSubscribe|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceResourceSubscribe|next|{remover + count_rows}'
                )
            )

        if resources:
            kb.row(
                InlineKeyboardButton(
                    text=text('chosen:cancel_all') if len(chosen) == len(resources) else text('chosen:choice_all'),
                    callback_data=f'ChoiceResourceSubscribe|choice_all|{remover}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data='ChoiceResourceSubscribe|cancel'
            ),
            InlineKeyboardButton(
                text=text('pay:button'),
                callback_data='ChoiceResourceSubscribe|pay'
            )
        )

        return kb.as_markup()

    @classmethod
    def folders(cls, folders: List[UserFolder], remover: int = 0):
        kb = cls()
        count_rows = 3

        for a, idx in enumerate(range(remover, len(folders))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=f'📁 {folders[idx].title}',
                        callback_data=f'ChoiceFolder|{folders[idx].id}|{remover}'
                    )
                )

        kb.adjust(1)

        if len(folders) <= count_rows:
            pass

        elif len(folders) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceFolder|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(folders):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceFolder|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceFolder|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceFolder|next|{remover + count_rows}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('folders:create:button'),
                callback_data='ChoiceFolder|create'
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data='ChoiceFolder|cancel'
            )
        )

        return kb.as_markup()

    # choice_type_folder removed

    @classmethod
    def choice_object_folders(
            cls,
            resources: List[Channel],
            chosen: List[int],
            remover: int = 0
    ):
        kb = cls()
        count_rows = 6

        for a, idx in enumerate(range(remover, len(resources))):
            if a < count_rows:
                resource_id = resources[idx].chat_id

                kb.add(
                    InlineKeyboardButton(
                        text=f'{"🔹" if resource_id in chosen else ""} {resources[idx].title}',
                        callback_data=f'ChoiceResourceFolder|{resource_id}|{remover}'
                    )
                )

        kb.adjust(2)

        if len(resources) <= count_rows:
            pass

        elif len(resources) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceResourceFolder|next|{remover + count_rows}'
                )
            )
        elif remover + count_rows >= len(resources):
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceResourceFolder|back|{remover - count_rows}'
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'ChoiceResourceFolder|back|{remover - count_rows}'
                ),
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'ChoiceResourceFolder|next|{remover + count_rows}'
                )
            )

        if resources:
            kb.row(
                InlineKeyboardButton(
                    text=text('chosen:cancel_all') if len(chosen) == len(resources) else text('chosen:choice_all'),
                    callback_data=f'ChoiceResourceFolder|choice_all|{remover}'
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text('back:button'),
                callback_data='ChoiceResourceFolder|cancel'
            ),
            InlineKeyboardButton(
                text=text('next:button'),
                callback_data='ChoiceResourceFolder|next_step'
            )
        )

        return kb.as_markup()

    @classmethod
    def manage_folder(cls):
        kb = cls()

        kb.button(
            text=text('manage:folder:content:button'),
            callback_data='ManageFolder|content'
        )
        kb.button(
            text=text('manage:folder:title:button'),
            callback_data='ManageFolder|title'
        )
        kb.button(
            text=text('manage:folder:remove:button'),
            callback_data='ManageFolder|remove'
        )
        kb.button(
            text=text('back:button'),
            callback_data='ManageFolder|back'
        )

        kb.adjust(1)
        return kb.as_markup()


class InlineAdmin(InlineKeyboardBuilder):
    @classmethod
    def admin(cls):
        kb = cls()

        kb.button(
            text="👤 Сессии",
            callback_data="Admin|session"
        )
        kb.button(
            text="📺 Каналы",
            callback_data="AdminChannels|list|0"
        )
        kb.button(
            text="📩 Рассылка",
            callback_data="Admin|mail"
        )
        kb.button(
            text="📊 Статистика сервиса",
            callback_data="Admin|stats"
        )
        kb.button(
            text="🎁 Создать промокод",
            callback_data="Admin|promo"
        )
        kb.button(
            text="🦋 Рекламные ссылки",
            callback_data="Admin|ads"
        )

        kb.adjust(2, 2, 1, 1)
        return kb.as_markup()

    @classmethod
    def admin_sessions(cls, clients: list = None, orphaned_sessions: list = None):
        kb = cls()

        if clients or orphaned_sessions:
            if orphaned_sessions:
                for session_file in orphaned_sessions:
                    # session_file is filename string
                    kb.button(
                        text=f"❓ {session_file}",
                        callback_data=f"AdminSession|add_orphan|{session_file}"
                    )

            if clients:
                for client in clients:
                    # client is MtClient object
                    status_emoji = "✅" if client.is_active else "🔴"
                    if client.status == 'RESETTING':
                        status_emoji = "🔄"
                    elif client.status == 'TEMP_BLOCKED':
                        status_emoji = "⏳"
                    
                    kb.button(
                        text=f"{status_emoji} {client.alias or client.id}",
                        callback_data=f"AdminSession|manage|{client.id}"
                    )
            kb.adjust(1)
            
            kb.row(
                InlineKeyboardButton(
                    text=text("back:button"),
                    callback_data="Admin|session"
                )
            )
        else:
            kb.button(
                text="Свои",
                callback_data="AdminSession|internal"
            )
            kb.button(
                text="Внешние",
                callback_data="AdminSession|external"
            )
            kb.button(
                text="🔍 Сканировать",
                callback_data="AdminSession|scan"
            )
            kb.button(
                text=text("add:button"),
                callback_data="AdminSession|add"
            )
            kb.button(
                text=text("back:button"),
                callback_data="Admin|back"
            )
            kb.adjust(2, 1, 1, 1)

        return kb.as_markup()

    @classmethod
    def admin_client_manage(cls, client_id: int):
        kb = cls()
        kb.button(text="🔄 Check Health / Activate", callback_data=f"AdminSession|check_health|{client_id}")
        kb.button(text="🔄 Reset Client", callback_data=f"AdminSession|reset_ask|{client_id}")
        kb.button(text=text("back:button"), callback_data="AdminSession|back_to_list")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_client_reset_confirm(cls, client_id: int):
        kb = cls()
        kb.button(text="⚠️ Confirm Reset", callback_data=f"AdminSession|reset_confirm|{client_id}")
        kb.button(text="Cancel", callback_data=f"AdminSession|manage|{client_id}")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_session_pool_select(cls):
        kb = cls()
        kb.button(text="Свой клиент (Internal)", callback_data="AdminSession|pool_select|internal")
        kb.button(text="Внешний (NovaStat)", callback_data="AdminSession|pool_select|external")
        kb.button(text=text("back:button"), callback_data="AdminSession|cancel")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_orphan_pool_select(cls, session_file: str):
        kb = cls()
        kb.button(text="Свой клиент (Internal)", callback_data=f"AdminSession|orphan_pool|internal|{session_file}")
        kb.button(text="Внешний (NovaStat)", callback_data=f"AdminSession|orphan_pool|external|{session_file}")
        kb.button(text=text("back:button"), callback_data="AdminSession|back_to_main")
        kb.adjust(1)
        return kb.as_markup()
    
    @classmethod
    def admin_channels_list(cls, channels: list, offset: int, total: int):
        """Клавиатура со списком каналов и пагинацией"""
        kb = cls()
        
        # Кнопки каналов
        for channel in channels:
            status_emoji = "✅" if channel.subscribe else "❌"
            kb.button(
                text=f"{status_emoji} {channel.title[:30]}",
                callback_data=f"AdminChannels|view|{channel.id}"
            )
        
        kb.adjust(1)
        
        # Навигация
        nav_buttons = []
        
        # Кнопка "Назад" (предыдущая страница)
        if offset > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"AdminChannels|list|{max(0, offset - 10)}"
            ))
        
        # Кнопка "Вперед" (следующая страница)
        if offset + 10 < total:
            nav_buttons.append(InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=f"AdminChannels|list|{offset + 10}"
            ))
        
        if nav_buttons:
            kb.row(*nav_buttons)
        
        # Кнопки действий
        kb.row(
            InlineKeyboardButton(text="🔍 Поиск", callback_data="AdminChannels|search")
        )
        kb.row(
            InlineKeyboardButton(text="◀️ В меню", callback_data="Admin|back")
        )
        
        return kb.as_markup()
    
    @classmethod
    def admin_channel_details(cls, channel_id: int):
        """Клавиатура для деталей канала"""
        kb = cls()
        
        kb.button(
            text="◀️ К списку",
            callback_data="AdminChannels|list|0"
        )
        
        kb.adjust(1)
        return kb.as_markup()



class Inline(
    InlineStories,
    InlinePosting,
    InlineBots,
    InlineBotSetting,
    InlineProfile,
    InlineAdmin,
):
    @classmethod
    def cancel(cls, data: str):
        kb = cls()

        kb.button(
            text=text('cancel'),
            callback_data=data
        )

        return kb.as_markup()

    @classmethod
    def back(cls, data: str):
        kb = cls()

        kb.button(
            text=text('back:button'),
            callback_data=data
        )

        return kb.as_markup()

    @classmethod
    def accept(cls, data: str):
        kb = cls()

        kb.button(
            text=text("delete:button"),
            callback_data=data + "|yes"
        )
        kb.button(
            text=text("back:button"),
            callback_data=data
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def wait_payment(cls, data: str, pay_url: str):
        kb = cls()

        kb.button(
            text=text('go_to_payment'),
            url=pay_url
        )
        kb.button(
            text=text('back:button'),
            callback_data=f'{data}'
        )

        kb.adjust(1)
        return kb.as_markup()

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
            callback_data="ChoicePostChannels|back|0"
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
            data: str = "ContentPost"
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
                    text="{} {} | {}".format(
                        emoji,
                        datetime.fromtimestamp(post.send_time or post.start_timestamp).strftime(
                            "%d.%m.%Y %H:%M"
                        ),
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
            for week in month:
                days = []
                for week_day in week:
                    days.append(
                        InlineKeyboardButton(
                            text='...',
                            callback_data='ContentPost|...'
                        ) if week_day == 0 else InlineKeyboardButton(
                            text=str(week_day) if week_day != day.day else '🔸',
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
                        text="{} {} | {}".format(
                            emoji,
                            datetime.fromtimestamp(getattr(objects[idx], "send_time")).strftime(
                                "%d.%m.%Y %H:%M"
                            ),
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



from main_bot.database.novastat.model import Collection, CollectionChannel


class InlineNovaStat(InlineKeyboardBuilder):
    @classmethod
    def main_menu(cls):
        kb = cls()
        kb.button(text="Настройки", callback_data="NovaStat|settings")
        kb.button(text="Сохранённые каналы", callback_data="NovaStat|collections")
        kb.button(text="Мои каналы (в разработке)", callback_data="NovaStat|my_channels")
        kb.button(text="Назад", callback_data="NovaStat|exit")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def settings(cls, current_depth: int):
        kb = cls()
        for i in range(3, 8):
            text_btn = f"{i} дня" if i < 5 else f"{i} дней"
            if i == current_depth:
                text_btn += " ✅"
            kb.button(text=text_btn, callback_data=f"NovaStat|set_depth|{i}")
        kb.button(text="Назад", callback_data="NovaStat|main")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def collections_list(cls, collections: List[Collection]):
        kb = cls()
        for col in collections:
            kb.button(text=f"{col.name}", callback_data=f"NovaStat|col_open|{col.id}")
        
        kb.button(text="Создать коллекцию", callback_data="NovaStat|col_create")
        kb.button(text="Назад", callback_data="NovaStat|main")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def collection_view(cls, collection: Collection, channels: List[CollectionChannel]):
        kb = cls()
        kb.button(text="Получить аналитику", callback_data=f"NovaStat|col_analyze|{collection.id}")
        kb.button(text="Добавить канал", callback_data=f"NovaStat|col_add_channel|{collection.id}")
        kb.button(text="Удалить канал", callback_data=f"NovaStat|col_del_channel_list|{collection.id}")
        kb.button(text="Переименовать", callback_data=f"NovaStat|col_rename|{collection.id}")
        kb.button(text="Удалить коллекцию", callback_data=f"NovaStat|col_delete|{collection.id}")
        kb.button(text="Назад", callback_data="NovaStat|collections")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def collection_channels_delete(cls, collection_id: int, channels: List[CollectionChannel]):
        kb = cls()
        for ch in channels:
            kb.button(text=f"❌ {ch.channel_identifier}", callback_data=f"NovaStat|col_del_channel|{collection_id}|{ch.id}")
        kb.button(text="Назад", callback_data=f"NovaStat|col_open|{collection_id}")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def analysis_result(cls):
        kb = cls()
        kb.button(text="Рассчитать цену рекламы", callback_data="NovaStat|calc_cpm_start")
        kb.button(text="Назад", callback_data="NovaStat|main")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def cpm_choice(cls):
        kb = cls()
        for cpm in range(100, 2100, 100):
            kb.button(text=str(cpm), callback_data=f"NovaStat|calc_cpm|{cpm}")
        kb.button(text="Назад", callback_data="NovaStat|main")
        kb.adjust(4)
        return kb.as_markup()

    @classmethod
    def cpm_result(cls):
        kb = cls()
        kb.button(text="Назад", callback_data="NovaStat|calc_cpm_start")
        return kb.as_markup()


class InlineAdCreative(InlineKeyboardBuilder):
    @classmethod
    def menu(cls):
        kb = cls()
        kb.button(text="Создать креатив", callback_data="AdCreative|create")
        kb.button(text="Список креативов", callback_data="AdCreative|list")
        kb.button(text="Назад", callback_data="AdCreative|back")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def creative_list(cls, creatives: list, page: int = 0):
        kb = cls()
        for creative in creatives:
            kb.button(
                text=f"{creative.name} ({len(creative.slots)} ссылок)",
                callback_data=f"AdCreative|view|{creative.id}"
            )
        kb.button(text="Назад", callback_data="AdCreative|menu")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def creative_view(cls, creative_id: int):
        kb = cls()
        kb.button(text="Создать закуп", callback_data=f"AdPurchase|create|{creative_id}")
        kb.button(text="🗑 Удалить", callback_data=f"AdCreative|delete|{creative_id}")
        kb.button(text="Назад", callback_data="AdCreative|list")
        kb.adjust(1)
        return kb.as_markup()


class InlineAdPurchase(InlineKeyboardBuilder):
    @classmethod
    def main_menu(cls):
        from config import Config
        kb = cls()
        kb.button(text="Создать закуп", callback_data="AdPurchase|create_menu")
        kb.button(text="Мои закупы", callback_data="AdPurchase|list")
        kb.button(text="🌍 Моя статистика", callback_data="AdPurchase|global_stats")
        kb.button(text="Назад", callback_data="delete") # Or close
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def creative_selection_menu(cls, creatives: list):
        kb = cls()
        for c in creatives:
            kb.button(text=f"Выбрать {c.name}", callback_data=f"AdPurchase|create|{c.id}")
        kb.button(text="Назад", callback_data="AdPurchase|menu")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def pricing_type_menu(cls):
        kb = cls()
        kb.button(text="По заявке (CPL)", callback_data="AdPurchase|pricing|CPL")
        kb.button(text="По подписке (CPS)", callback_data="AdPurchase|pricing|CPS")
        kb.button(text="Фикс (FIXED)", callback_data="AdPurchase|pricing|FIXED")
        kb.button(text="Назад", callback_data="AdPurchase|cancel")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def mapping_menu(cls, purchase_id: int, links_data: list):
        kb = cls()
        # links_data is list of dict: {slot_id, original_url, status_text, is_channel}
        for link in links_data:
            # Left button: URL (inactive/noop)
            kb.button(
                text=f"{link['original_url']}", 
                callback_data="noop"
            )
            # Right button: Status/Channel (clickable)
            kb.button(
                text=f"{link['status_text']}",
                callback_data=f"AdPurchase|map_link|{purchase_id}|{link['slot_id']}"
            )
        
        kb.button(text="⬅️ Назад", callback_data=f"AdPurchase|view|{purchase_id}")
        kb.button(text="✅ Сохранить мапинг", callback_data=f"AdPurchase|save_mapping|{purchase_id}")
        
        # Adjust: 2 columns for links, 2 columns for bottom buttons
        sizes = [2] * len(links_data) + [2]
        kb.adjust(*sizes)
        return kb.as_markup()

    @classmethod
    def link_actions_menu(cls, purchase_id: int, slot_id: int):
        kb = cls()
        kb.button(
            text="Выбрать канал",
            callback_data=f"AdPurchase|select_channel_list|{purchase_id}|{slot_id}"
        )
        kb.button(
            text="❌ Не трекать",
            callback_data=f"AdPurchase|set_external|{purchase_id}|{slot_id}"
        )
        kb.button(
            text="Назад",
            callback_data=f"AdPurchase|mapping|{purchase_id}"
        )
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def channel_list_menu(cls, purchase_id: int, slot_id: int, channels: list):
        kb = cls()
        for ch in channels:
            kb.button(
                text=ch.title,
                callback_data=f"AdPurchase|set_channel|{purchase_id}|{slot_id}|{ch.chat_id}"
            )
        
        kb.button(
            text="Назад",
            callback_data=f"AdPurchase|map_link|{purchase_id}|{slot_id}"
        )
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def purchase_list_menu(cls, purchases: list):
        kb = cls()
        for p in purchases:
            # p is AdPurchase object, needs creative_name attached or fetched
            # Assuming p has creative_name attribute or we pass a dict/object with it
            name = getattr(p, 'creative_name', f"Creative #{p.creative_id}")
            text_str = f"#{p.id} {name} ({p.pricing_type}/{p.price_value})"
            kb.button(text=text_str, callback_data="noop")
            kb.button(text="Открыть", callback_data=f"AdPurchase|view|{p.id}")
        
        kb.button(text="Назад", callback_data="AdPurchase|menu")
        # 2 columns per purchase row (Info | Open), 1 for Back
        sizes = [2] * len(purchases) + [1]
        kb.adjust(*sizes)
        return kb.as_markup()

    @classmethod
    def purchase_view_menu(cls, purchase_id: int):
        kb = cls()
        kb.button(text="Мапинг ссылок", callback_data=f"AdPurchase|mapping|{purchase_id}")
        kb.button(text="📤 Сгенерировать пост", callback_data=f"AdPurchase|gen_post|{purchase_id}")
        kb.button(text="📊 Статистика", callback_data=f"AdPurchase|stats|{purchase_id}")
        kb.button(text="Архивировать", callback_data=f"AdPurchase|archive|{purchase_id}")
        kb.button(text="Удалить", callback_data=f"AdPurchase|delete|{purchase_id}")
        kb.button(text="Назад", callback_data="AdPurchase|list")
        kb.adjust(1)
        return kb.as_markup()
    
    @classmethod
    def stats_period_menu(cls, purchase_id: int):
        kb = cls()
        kb.button(text="📅 24 часа", callback_data=f"AdPurchase|stats_period|{purchase_id}|24h")
        kb.button(text="📅 7 дней", callback_data=f"AdPurchase|stats_period|{purchase_id}|7d")
        kb.button(text="📅 30 дней", callback_data=f"AdPurchase|stats_period|{purchase_id}|30d")
        kb.button(text="📅 Всё время", callback_data=f"AdPurchase|stats_period|{purchase_id}|all")
        kb.button(text="Назад", callback_data=f"AdPurchase|view|{purchase_id}")
        kb.adjust(1)
        return kb.as_markup()
    
    @classmethod
    def global_stats_period_menu(cls):
        kb = cls()
        kb.button(text="📅 24 часа", callback_data="AdPurchase|global_stats_period|24h")
        kb.button(text="📅 7 дней", callback_data="AdPurchase|global_stats_period|7d")
        kb.button(text="📅 30 дней", callback_data="AdPurchase|global_stats_period|30d")
        kb.button(text="📅 Всё время", callback_data="AdPurchase|global_stats_period|all")
        kb.button(text="Назад", callback_data="AdPurchase|menu")
        kb.adjust(1)
        return kb.as_markup()


class Keyboards(
    Reply,
    Inline,
    InlineAdCreative,
    InlineAdPurchase
):
    pass


keyboards = Keyboards()
