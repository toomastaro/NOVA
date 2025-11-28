import re
from calendar import monthcalendar, monthrange
from datetime import datetime

from aiogram.types import InlineKeyboardButton, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import Config
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
from main_bot.utils.schemas import (
    ByeAnswer,
    CaptchaObj,
    HelloAnswer,
    Hide,
    MessageOptions,
    MessageOptionsHello,
    React,
    StoryOptions,
)


class Reply:
    @classmethod
    def menu(cls):
        kb = ReplyKeyboardBuilder()

        kb.button(text=text("reply_menu:posting"))
        kb.button(text=text("reply_menu:story"))
        kb.button(text=text("reply_menu:bots"))
        kb.button(text=text("reply_menu:support"))
        kb.button(text=text("reply_menu:profile"))

        kb.adjust(2, 1, 2)
        return kb.as_markup(
            resize_keyboard=True,
        )

    @classmethod
    def captcha_kb(cls, buttons: str, resize: bool = True):
        kb = ReplyKeyboardBuilder()

        for row in buttons.split("\n"):
            buttons = [
                KeyboardButton(
                    text=button.strip(),
                )
                for button in row.split("|")
            ]
            kb.row(*buttons)

        return kb.as_markup(resize_keyboard=resize)


class InlinePosting(InlineKeyboardBuilder):
    @classmethod
    def posting_menu(cls):
        kb = cls()

        kb.button(
            text=text("posting:create_post"), callback_data="MenuPosting|create_post"
        )
        kb.button(text=text("posting:channels"), callback_data="MenuPosting|channels")
        kb.button(
            text=text("posting:content_plan"), callback_data="MenuPosting|content_plan"
        )

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def choice_channels_for_post(
        cls,
        channels: list[Channel],
        folders: list[UserFolder] | None = None,
        chosen: list[int] | None = None,
        data: str = "ChoiceChannelPost",
        remover: int = 0,
        is_folder_view: bool = False,
    ):
        kb = cls()
        count_rows = 7
        folders = folders or []
        chosen = chosen or []

        # Объединяем ресурсы: сначала папки, потом каналы
        # Используем кортежи (тип, объект) для различения
        resources = [("folder", f) for f in folders] + [("channel", c) for c in channels]

        for a, idx in enumerate(range(remover, len(resources))):
            if a < count_rows:
                res_type, obj = resources[idx]
                if res_type == "folder":
                    text_btn = f"📁 {obj.title}"
                    callback_data = f"{data}|folder|{obj.id}"
                else:
                    is_chosen = obj.chat_id in chosen
                    text_btn = f"{'✅ ' if is_chosen else ''}{obj.title}"
                    callback_data = f"{data}|channel|{obj.chat_id}"

                kb.add(
                    InlineKeyboardButton(
                        text=text_btn,
                        callback_data=callback_data,
                    )
                )

        kb.adjust(2)

        # Пагинация
        if len(resources) <= count_rows:
            pass
        elif len(resources) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(resources):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                ),
            )

        # Кнопки управления
        control_buttons = []
        # Кнопка "Выбрать все"
        control_buttons.append(
            InlineKeyboardButton(
                text=text("choice_all"), callback_data=f"{data}|choice_all"
            )
        )
        
        # Кнопка "Готово" (если есть выбранные)
        if chosen:
             control_buttons.append(
                InlineKeyboardButton(
                    text=text("ready"), callback_data=f"{data}|confirm"
                )
            )
        
        kb.row(*control_buttons)

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_channels_for_post(
        cls,
        channels: list[Channel],
        folders: list[UserFolder] = None,
        chosen: list[int] = None,
        data: str = "ChoiceChannelPost",
        remover: int = 0,
        is_folder_view: bool = False
    ):
        """
        Клавиатура для выбора каналов с поддержкой папок
        """
        kb = cls()
        folders = folders or []
        chosen = chosen or []
        count_rows = 7

        # Если мы в папке, показываем только каналы
        if is_folder_view:
            for a, idx in enumerate(range(remover, len(channels))):
                if a < count_rows:
                    channel = channels[idx]
                    selected = "🔹 " if channel.chat_id in chosen else ""
                    kb.add(
                        InlineKeyboardButton(
                            text=f"{selected}{channel.title}",
                            callback_data=f"{data}|channel|{channel.chat_id}"
                        )
                    )
        else:
            # Показываем папки сверху
            for folder in folders:
                kb.add(
                    InlineKeyboardButton(
                        text=f"📁 {folder.title}",
                        callback_data=f"{data}|folder|{folder.id}"
                    )
                )

            # Затем каналы не в папках
            for a, idx in enumerate(range(remover, len(channels))):
                if a < count_rows - len(folders):  # Оставляем место для папок
                    channel = channels[idx]
                    selected = "🔹 " if channel.chat_id in chosen else ""
                    kb.add(
                        InlineKeyboardButton(
                            text=f"{selected}{channel.title}",
                            callback_data=f"{data}|channel|{channel.chat_id}"
                        )
                    )

        kb.adjust(1)

        # Кнопки навигации для каналов (только если слишком много)
        if not is_folder_view:
            max_items = count_rows - len(folders)
        else:
            max_items = count_rows

        if len(channels) > max_items:
            # Логика навигации по страницам
            if len(channels) > max_items > remover:
                kb.row(
                    InlineKeyboardButton(
                        text="➡️", callback_data=f"{data}|next|{remover + max_items}"
                    )
                )
            elif remover + max_items >= len(channels):
                kb.row(
                    InlineKeyboardButton(
                        text="⬅️", callback_data=f"{data}|back|{remover - max_items}"
                    )
                )
            else:
                kb.row(
                    InlineKeyboardButton(
                        text="⬅️", callback_data=f"{data}|back|{remover - max_items}"
                    ),
                    InlineKeyboardButton(
                        text="➡️", callback_data=f"{data}|next|{remover + max_items}"
                    )
                )

        # Кнопка "выбрать все" (всегда видна)
        kb.row(
            InlineKeyboardButton(
                text=text("chosen:choice_all"),  # "🔹 Выбрать все" или "🚫 Очистить",
                callback_data=f"{data}|choice_all"
            )
        )

        # Нижняя панель: Назад и Подтвердить (если что-то выбрано)
        back_text = text("back:button") if is_folder_view else text("cancel")
        bottom_row = [
            InlineKeyboardButton(
                text=back_text,
                callback_data=f"{data}|cancel"
            )
        ]

        if chosen:  # Показываем кнопку подтверждения только когда что-то выбрано
            bottom_row.append(
                InlineKeyboardButton(
                    text=f"✅ Подтвердить ({len(chosen)})",
                    callback_data=f"{data}|confirm"
                )
            )

        kb.row(*bottom_row)
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
                    InlineKeyboardButton(text=row_hide.button_name, callback_data="...")
                )

        if post.buttons:
            for row in post.buttons.split("\n"):
                buttons = [
                    InlineKeyboardButton(
                        text=button.split("—")[0].strip(),
                        url=button.split("—")[1].strip(),
                    )
                    for button in row.split("|")
                ]
                kb.row(*buttons)

        if reactions:
            for row in reactions.rows:
                buttons = []
                for react in row.reactions:
                    buttons.append(
                        InlineKeyboardButton(text=react.react, callback_data="...")
                    )
                kb.row(*buttons)

        kb.row(
            InlineKeyboardButton(
                text=text(
                    "manage:post:{}:desc:button".format(
                        "edit" if options.text or options.caption else "add"
                    )
                ),
                callback_data=f"ManagePost|text|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text(
                    "manage:post:{}:media:button".format(
                        "edit"
                        if options.photo or options.video or options.animation
                        else "add"
                    )
                ),
                callback_data=f"ManagePost|media|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:add:url_buttons:button"),
                callback_data=f"ManagePost|buttons|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:add:cpm:button").format(post.cpm_price or "Нет"),
                callback_data=f"ManagePost|cpm_price|{post.id}",
            )
        )

        if not show_more:
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:show_more:button"),
                    callback_data=f"ManagePost|show_more|{post.id}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:hide:button").format("✅" if hide else "❌"),
                    callback_data=f"ManagePost|hide|{post.id}",
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:has_spoiler:button").format(
                        "✅" if options.has_spoiler else "❌"
                    ),
                    callback_data=f"ManagePost|has_spoiler|{post.id}",
                ),
                InlineKeyboardButton(
                    text=text("manage:post:media_above:button").format(
                        "✅" if options.show_caption_above_media else "❌"
                    ),
                    callback_data=f"ManagePost|media_above|{post.id}",
                ),
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:pin:button").format(
                        "✅" if post.pin_time else "❌"
                    ),
                    callback_data=f"ManagePost|pin_time|{post.id}",
                ),
                InlineKeyboardButton(
                    text=text("manage:post:react:button").format(
                        "✅" if reactions else "❌"
                    ),
                    callback_data=f"ManagePost|reaction|{post.id}",
                ),
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:notification:button").format(
                        "🔔" if not options.disable_notification else "🔕"
                    ),
                    callback_data=f"ManagePost|notification|{post.id}",
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("manage:post:hide_more:button"),
                    callback_data=f"ManagePost|show_more|{post.id}",
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"ManagePost|cancel|{post.id}"
            ),
            InlineKeyboardButton(
                text=text("{}:button".format("save" if is_edit else "next")),
                callback_data=f"ManagePost|next|{post.id}",
            ),
        )

        return kb.as_markup()

    @classmethod
    def post_kb(cls, post: Post | PublishedPost | BotPost, is_bot: bool = False):
        kb = cls()

        if post.buttons:
            for row in post.buttons.split("\n"):
                buttons = [
                    InlineKeyboardButton(
                        text=button.split("—")[0].strip(),
                        url=button.split("—")[1].strip(),
                    )
                    for button in row.split("|")
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
                            callback_data=f"ClickHide|{row_hide.id}",
                        )
                    )

            if reactions:
                for row in reactions.rows:
                    buttons = []
                    for react in row.reactions:
                        buttons.append(
                            InlineKeyboardButton(
                                text=react.react
                                if not len(react.users)
                                else f"{react.react} {len(react.users)}",
                                callback_data=f"ClickReact|{react.id}",
                            )
                        )
                    kb.row(*buttons)

        return kb.as_markup()

    @classmethod
    def param_cancel(cls, param: str, data: str = "ParamCancel"):
        kb = cls()

        kb.button(
            text=text(f"manage:post:delete:param:{param}:button"),
            callback_data=f"{data}|delete",
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def param_hide(cls, post: Post):
        kb = cls()
        hide = Hide(hide=post.hide) if post.hide else None

        if hide:
            for hide in hide.hide:
                kb.row(InlineKeyboardButton(text=hide.button_name, callback_data="..."))

        kb.button(
            text=text("manage:post:add:param:hide:button"),
            callback_data="ParamHide|add",
        )
        kb.button(
            text=text("manage:post:delete:param:hide:button"),
            callback_data="ParamCancel|delete",
        )
        kb.button(text=text("back:button"), callback_data="ParamCancel|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def param_hide_back(cls, data: str = "BackButtonHide"):
        kb = cls()

        kb.button(
            text=text("manage:post:back_step:param:hide:button"),
            callback_data=f"{data}|step",
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

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
            text=text("manage:post:report:button").format("✅" if obj.report else "❌"),
            callback_data=f"{data}|report",
        )
        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(delete_time / 3600)} ч."  # type: ignore
                if delete_time
                else text("manage:post:del_time:not")
            ),
            callback_data=f"{data}|delete_time",
        )
        kb.button(
            text=text("manage:post:send_time:button"), callback_data=f"{data}|send_time"
        )
        kb.button(
            text=text("manage:post:public:button"), callback_data=f"{data}|public"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1, 1, 2, 1)
        return kb.as_markup()

    @classmethod
    def choice_delete_time(cls):
        kb = cls()

        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:delete:param:delete_time:button"),
                callback_data="GetDeleteTimePost|off",
            )
        )
        # Первое значение изменено на 1 минуту (0.017 ч) для удобства тестирования
        groups = [[0.017, 2, 3, 4], [6, 8, 10, 12], [18, 24, 36, 48], [72, 96, 120, 144]]
        for group in groups:
            kb.row(
                *[
                    InlineKeyboardButton(
                        text=f"{h} ч." if h >= 1 else "1 мин", callback_data=f"GetDeleteTimePost|{int(h * 3600) if h >= 1 else 60}"
                    )
                    for h in group
                ]
            )

        kb.row(
            *[
                InlineKeyboardButton(
                    text=f"{i} нед.", callback_data=f"GetDeleteTimePost|{i * 7 * 86400}"
                )
                for i in range(1, 5)
            ]
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="GetDeleteTimePost|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def accept_date(cls, data: str = "AcceptPost"):
        kb = cls()

        kb.button(
            text=text("manage:post:send_time:button"), callback_data=f"{data}|send_time"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def accept_public(cls, data: str = "AcceptPost"):
        kb = cls()

        kb.button(
            text=text("manage:post:public:button"), callback_data=f"{data}|public"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

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
            text=text(f"{value}:create_post"), callback_data=f"{data}|create_post"
        )
        kb.button(
            text=text(f"{value}:content_plan"), callback_data=f"{data}|content_plan"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_remain_post(cls, post: Post):
        kb = cls()

        kb.button(
            text=text("manage:post:send_time").format(
                datetime.fromtimestamp(post.send_time).strftime("%d.%m.%Y %H:%M")
            ),
            callback_data="FinishPostParams|send_time",
        )
        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(post.delete_time / 3600)} ч."  # type: ignore
                if post.delete_time
                else text("manage:post:del_time:not")
            ),
            callback_data="FinishPostParams|delete_time",
        )
        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManageRemainPost|change",
        )
        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManageRemainPost|delete",
        )
        kb.button(text=text("back:button"), callback_data="ManageRemainPost|cancel")
        kb.button(
            text=text("manage:post:public:button"),
            callback_data="FinishPostParams|public",
        )

        kb.adjust(1, 1, 2)
        return kb.as_markup()


class InlineStories(InlineKeyboardBuilder):
    @classmethod
    def stories_menu(cls):
        kb = cls()

        kb.button(
            text=text("stories:create_post"), callback_data="MenuStories|create_post"
        )
        kb.button(text=text("stories:channels"), callback_data="MenuStories|channels")
        kb.button(
            text=text("stories:content_plan"), callback_data="MenuStories|content_plan"
        )

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def manage_story(cls, post: Story, is_edit: bool = False):
        kb = cls()
        options = StoryOptions(**post.story_options)

        kb.row(
            InlineKeyboardButton(
                text=text(
                    "manage:post:{}:desc:button".format(
                        "edit" if options.caption else "add"
                    )
                ),
                callback_data=f"ManageStory|text|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:edit:media:button"),
                callback_data=f"ManageStory|media|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:story:noforwards:button").format(
                    "✅" if options.noforwards else "❌"
                ),
                callback_data=f"ManageStory|noforwards|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:story:pinned:button").format(
                    "✅" if options.pinned else "❌"
                ),
                callback_data=f"ManageStory|pinned|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"ManageStory|cancel|{post.id}"
            ),
            InlineKeyboardButton(
                text=text("{}:button".format("save" if is_edit else "next")),
                callback_data=f"ManageStory|next|{post.id}",
            ),
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
                    callback_data=f"GetDeleteTimeStories|{period * 3600}",
                )
            )

        kb.row(*row)
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="GetDeleteTimeStories|cancel"
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
            callback_data="FinishStoriesParams|send_time",
        )
        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(options.period / 3600)} ч."  # type: ignore
                if options.period
                else text("manage:post:del_time:not")
            ),
            callback_data="FinishStoriesParams|delete_time",
        )
        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManageRemainStories|change",
        )
        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManageRemainStories|delete",
        )
        kb.button(text=text("back:button"), callback_data="ManageRemainStories|cancel")
        kb.button(
            text=text("manage:post:public:button"),
            callback_data="FinishStoriesParams|public",
        )

        kb.adjust(1, 1, 2)
        return kb.as_markup()


class InlineBots(InlineKeyboardBuilder):
    @classmethod
    def bots_menu(cls):
        kb = cls()

        kb.button(text=text("bots:create_post"), callback_data="MenuBots|create_post")
        kb.button(text=text("bots:bots"), callback_data="MenuBots|bots")
        kb.button(text=text("bots:content_plan"), callback_data="MenuBots|content_plan")

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def choice_bots(
        cls, bots: list[UserBot], data: str = "ChoiceBots", remover: int = 0
    ):
        kb = cls()
        count_rows = 3

        for a, idx in enumerate(range(remover, len(bots))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=bots[idx].title,
                        callback_data=f"{data}|{bots[idx].id}|{remover}",
                    )
                )

        kb.adjust(1)

        if len(bots) <= count_rows:
            pass

        elif len(bots) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(bots):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("bots:add:button"), callback_data=f"{data}|add"
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
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
                text=text(
                    "manage:post:{}:desc:button".format(
                        "edit" if options.caption or options.text else "add"
                    )
                ),
                callback_data=f"ManageBotPost|text|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:edit:media:button"),
                callback_data=f"ManageBotPost|media|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:add:url_buttons:button"),
                callback_data=f"ManageBotPost|buttons|{post.id}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data=f"ManageBotPost|cancel|{post.id}",
            ),
            InlineKeyboardButton(
                text=text("{}:button".format("save" if is_edit else "next")),
                callback_data=f"ManageBotPost|next|{post.id}",
            ),
        )

        return kb.as_markup()

    @classmethod
    def finish_bot_post_params(cls, obj: BotPost, data: str = "FinishBotPostParams"):
        kb = cls()

        kb.button(
            text=text("manage:post:report:button").format("✅" if obj.report else "❌"),
            callback_data=f"{data}|report",
        )
        kb.button(
            text=text("manage_hello_msg:text_with_name:button").format(
                "✅" if obj.text_with_name else "❌"
            ),
            callback_data=f"{data}|text_with_name",
        )
        kb.button(
            text=text("manage:post:del_time:button").format(
                f"{int(obj.delete_time / 3600)} ч."  # type: ignore
                if obj.delete_time
                else text("manage:post:del_time:not")
            ),
            callback_data=f"{data}|delete_time",
        )
        kb.button(
            text=text("manage:post:send_time:button"), callback_data=f"{data}|send_time"
        )
        kb.button(
            text=text("manage:post:public:button"), callback_data=f"{data}|public"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1, 1, 1, 2, 1)
        return kb.as_markup()

    @classmethod
    def choice_delete_time_bot_post(cls):
        kb = cls()

        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:delete:param:delete_time:button"),
                callback_data="GetDeleteTimeBotPost|off",
            )
        )
        groups = [
            [12, 24, 36, 40],
        ]
        for group in groups:
            kb.row(
                *[
                    InlineKeyboardButton(
                        text=f"{h} ч.", callback_data=f"GetDeleteTimeBotPost|{h * 3600}"
                    )
                    for h in group
                ]
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="GetDeleteTimeBotPost|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_send_time_bot_post(cls, day: datetime, data: str = "SendTimeBotPost"):
        kb = cls()

        kb.row(
            InlineKeyboardButton(
                text=text("short:content:button"), callback_data=f"{data}|show_more"
            )
        )
        kb.row(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{data}|back_month|{monthrange(day.year, day.month)[1]}",
            ),
            InlineKeyboardButton(
                text=f"{text('other_month').get(str(day.month))} {day.year}",
                callback_data=f"{data}|...",
            ),
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{data}|next_month|{-monthrange(day.year, day.month)[1]}",
            ),
        )

        month = monthcalendar(day.year, day.month)
        for week in month:
            days = []
            for week_day in week:
                days.append(
                    InlineKeyboardButton(text="...", callback_data=f"{data}|...")
                    if week_day == 0
                    else InlineKeyboardButton(
                        text=str(week_day) if week_day != day.day else "🔸",
                        callback_data=f"{data}|choice_day|{day.year}-{day.month}-{week_day}",
                    )
                )
            kb.row(*days)

        kb.row(
            InlineKeyboardButton(text="⬅️", callback_data=f"{data}|back_day|1"),
            InlineKeyboardButton(
                text=f"{day.day} {text('month').get(str(day.month))}",
                callback_data=f"{data}|...",
            ),
            InlineKeyboardButton(text="➡️", callback_data=f"{data}|next_day|-1"),
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
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
            callback_data="FinishBotPostParams|send_time",
        )
        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManageRemainBotPost|change",
        )
        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManageRemainBotPost|delete",
        )
        kb.button(text=text("back:button"), callback_data="ManageRemainBotPost|cancel")
        kb.button(
            text=text("manage:post:public:button"),
            callback_data="FinishBotPostParams|public",
        )

        kb.adjust(1, 2)
        return kb.as_markup()

    @classmethod
    def manage_bot(cls, user_bot: UserBot, status: bool):
        kb = cls()

        kb.button(text=text("manage:bot:manage"), callback_data="ManageBot|settings")

        kb.button(
            text=text("manage:bot:{}_channel".format("add")),
            url=f"t.me/{user_bot.username}?startchannel&admin=invite_users",
        )
        kb.button(
            text=text("manage:bot:refresh_token"),
            callback_data="ManageBot|refresh_token",
        )
        kb.button(
            text=text("manage:bot:check_token"), callback_data="ManageBot|check_token"
        )
        kb.button(
            text=text("manage:bot:import_db"), callback_data="ManageBot|import_db"
        )
        kb.button(
            text=text("manage:bot:export_db"), callback_data="ManageBot|export_db"
        )
        kb.button(
            text=text("manage:bot:set_{}".format("off" if status else "on")),
            callback_data="ManageBot|status",
        )
        kb.button(text=text("manage:bot:delete"), callback_data="ManageBot|delete")
        kb.button(text=text("back:button"), callback_data="ManageBot|cancel")

        kb.adjust(1, 1, 1, 1, 2, 1)
        return kb.as_markup()

    @classmethod
    def export_type(cls):
        kb = cls()

        kb.button(text=text("export:type:txt"), callback_data="ExportType|txt")
        kb.button(text=text("export:type:csv"), callback_data="ExportType|csv")
        kb.button(text=text("export:type:xlsx"), callback_data="ExportType|xlsx")
        kb.button(text=text("back:button"), callback_data="ExportType|cancel")

        kb.adjust(1, 2, 1)
        return kb.as_markup()


class InlineBotSetting(InlineKeyboardBuilder):
    @classmethod
    def choice_cleaner_type(cls):
        kb = cls()

        kb.button(
            text=text("cleaner:application:button"),
            callback_data="ChoiceCleanerType|application",
        )
        kb.button(
            text=text("cleaner:ban:button"), callback_data="ChoiceCleanerType|ban"
        )
        kb.button(text=text("back:button"), callback_data="ChoiceCleanerType|cancel")

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

            kb.button(text=value, callback_data=f"ChoiceClonerSetting|{key}")

        kb.adjust(1)

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceClonerSetting|cancel"
            ),
            InlineKeyboardButton(
                text=text("clone:start:button"),
                callback_data="ChoiceClonerSetting|clone",
            ),
        )
        return kb.as_markup()

    @classmethod
    def choice_channel_for_cloner(
        cls, channels: list[Channel], chosen: list, remover: int = 0
    ):
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
                        callback_data=f"ChoiceClonerTarget|{channels[idx].chat_id}|{remover}",
                    )
                )

        kb.adjust(2)

        if len(channels) <= count_rows:
            pass

        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceClonerTarget|next|{remover + count_rows}",
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceClonerTarget|back|{remover - count_rows}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceClonerTarget|back|{remover - count_rows}",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceClonerTarget|next|{remover + count_rows}",
                ),
            )

        if channels:
            kb.row(
                InlineKeyboardButton(
                    text=text("chosen:cancel_all")
                    if len(chosen) == len(channels)
                    else text("chosen:choice_all"),
                    callback_data=f"ChoiceClonerTarget|choice_all|{remover}",
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceClonerTarget|cancel"
            ),
            InlineKeyboardButton(
                text=text("next:button"), callback_data="ChoiceClonerTarget|next_step"
            ),
        )

        return kb.as_markup()

    @classmethod
    def choice_channel_captcha(
        cls,
        channel_captcha_list: list[ChannelCaptcha],
        active_captcha: int,
        remover: int = 0,
    ):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(channel_captcha_list))):
            if a < count_rows:
                captcha_obj = CaptchaObj.from_orm(channel_captcha_list[idx])
                button_text = (
                    captcha_obj.message.text or captcha_obj.message.caption or "Медиа"
                )
                setting_text = "Настроить"

                if active_captcha == channel_captcha_list[idx].id:
                    button_text = "✅ " + button_text
                    setting_text = setting_text + f" ⌛️ {captcha_obj.delay}"

                kb.row(
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"ChoiceCaptcha|choice|{channel_captcha_list[idx].id}",
                    ),
                    InlineKeyboardButton(
                        text=setting_text,
                        callback_data=f"ChoiceCaptcha|change|{channel_captcha_list[idx].id}",
                    ),
                )

        kb.adjust(2)

        if len(channel_captcha_list) <= count_rows:
            pass

        elif len(channel_captcha_list) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"ChoiceCaptcha|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(channel_captcha_list):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"ChoiceCaptcha|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"ChoiceCaptcha|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"ChoiceCaptcha|next|{remover + count_rows}"
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("add:button"), callback_data="ChoiceCaptcha|add"
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceCaptcha|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def manage_captcha(cls, captcha: ChannelCaptcha):
        kb = cls()

        kb.button(
            text=text("application:delay:button").format(captcha.delay),
            callback_data="ManageCaptcha|delay",
        )
        kb.button(text=text("change:button"), callback_data="ManageCaptcha|change")
        kb.button(text=text("delete:button"), callback_data="ManageCaptcha|delete")
        kb.button(text=text("back:button"), callback_data="ManageCaptcha|cancel")

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

            kb.button(text=label, callback_data=f"ChoiceCaptchaDelay|{seconds}")

        kb.adjust(3)
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceCaptchaDelay|cancel"
            ),
        )

        return kb.as_markup()

    @classmethod
    def manage_captcha_post(cls, resize: bool = True):
        kb = cls()

        kb.button(text="Кнопки", callback_data="ManagePostCaptcha|reply_buttons")
        kb.button(
            text="Широкие кнопки: {}".format("✅" if not resize else "❌"),
            callback_data="ManagePostCaptcha|resize",
        )
        kb.button(
            text=text("manage:hello:edit:desc:button"),
            callback_data="ManagePostCaptcha|message",
        )
        kb.button(text=text("back:button"), callback_data="ManagePostCaptcha|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_hello_message(cls, hello_message: ChannelHelloMessage):
        kb = cls()

        kb.button(
            text=text("on" if hello_message.is_active else "off"),
            callback_data="ManageHelloMessage|on",
        )
        kb.button(
            text=text("application:delay:button").format(hello_message.delay),
            callback_data="ManageHelloMessage|delay",
        )
        kb.button(
            text=text("manage_hello_msg:text_with_name:button").format(
                "✅" if hello_message.text_with_name else "❌"
            ),
            callback_data="ManageHelloMessage|text_with_name",
        )
        kb.button(text=text("change:button"), callback_data="ManageHelloMessage|change")
        kb.button(text=text("delete:button"), callback_data="ManageHelloMessage|delete")
        kb.button(text=text("back:button"), callback_data="ManageHelloMessage|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_hello_message_post(cls):
        kb = cls()

        kb.button(
            text=text("manage:post:add:url_buttons:button"),
            callback_data="ManagePostHelloMessage|url_buttons",
        )
        kb.button(
            text=text("manage:hello:edit:desc:button"),
            callback_data="ManagePostHelloMessage|message",
        )
        kb.button(
            text=text("back:button"), callback_data="ManagePostHelloMessage|cancel"
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def hello_kb(cls, buttons: str):
        kb = cls()

        for row in buttons.split("\n"):
            buttons = [
                InlineKeyboardButton(
                    text=button.split("—")[0].strip(), url=button.split("—")[1].strip()
                )
                for button in row.split("|")
            ]
            kb.row(*buttons)

        return kb.as_markup()

    @classmethod
    def choice_invite_url(cls, invite_urls: list[str], remover: int = 0):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(invite_urls))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=invite_urls[idx],
                        callback_data=f"ChoiceInviteUrlApplication|{invite_urls[idx]}",
                    )
                )

        kb.adjust(1)

        if len(invite_urls) <= count_rows:
            pass

        elif len(invite_urls) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceInviteUrlApplication|next|{remover + count_rows}",
                )
            )
        elif remover + count_rows >= len(invite_urls):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceInviteUrlApplication|back|{remover - count_rows}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceInviteUrlApplication|back|{remover - count_rows}",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceInviteUrlApplication|next|{remover + count_rows}",
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data="ChoiceInviteUrlApplication|cancel",
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_channel_for_setting(
        cls,
        channels: list[Channel],
        data: str = "ChoiceBotSettingChannel",
        remover: int = 0,
    ):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(channels))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=channels[idx].title,
                        callback_data=f"{data}|{channels[idx].chat_id}",
                    )
                )

        kb.adjust(2)

        if len(channels) <= count_rows:
            pass

        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def add_channel(cls, bot_username: str, data: str = "BackAddChannel"):
        kb = cls()

        kb.button(
            text=text("add_channel:button"),
            url=f"https://t.me/{bot_username}?startchannel&admin=invite_users",
        )
        kb.button(text=text("add_channel_later:button"), callback_data=f"{data}|menu")

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
            callback_data="BotSettingMenu|application",
        )
        kb.button(text=text("bot_menu:hello"), callback_data="BotSettingMenu|hello")
        kb.button(
            text=text("bot_menu:captcha").format(
                "✅" if channel_settings.active_captcha_id else "❌"
            ),
            callback_data="BotSettingMenu|captcha",
        )
        kb.button(text=text("bot_menu:cloner"), callback_data="BotSettingMenu|clone")
        kb.button(
            text=text("bot_menu:bye").format("✅" if bye.active else "❌"),
            callback_data="BotSettingMenu|bye",
        )
        kb.button(text=text("bot_menu:cleaner"), callback_data="BotSettingMenu|cleaner")
        kb.button(text=text("bot_menu:update"), callback_data="BotSettingMenu|update")
        kb.button(text=text("back:button"), callback_data="BotSettingMenu|back")

        kb.adjust(1, 1, 2)
        return kb.as_markup()

    @classmethod
    def param_answers_back(cls, data: str = "BackAddAnswer"):
        kb = cls()

        kb.button(text=text("back:step"), callback_data=f"{data}|step")
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_answer_user(cls, obj: HelloAnswer, data: str = "ManageHello"):
        kb = cls()

        kb.button(
            text=text("{}:button".format("on" if obj.active else "off")),
            callback_data=f"{data}|active",
        )
        kb.button(
            text=text("{}:button".format("add" if not obj.message else "delete")),
            callback_data=f"{data}|message",
        )
        kb.button(text=text("check:button"), callback_data=f"{data}|check")
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def manage_hello_messages(
        cls, hello_messages: list[ChannelHelloMessage], remover: int = 0
    ):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(hello_messages))):
            if a < count_rows:
                hello = HelloAnswer.from_orm(hello_messages[idx])

                button_text = "{} сообщение {} Задержка: {}".format(
                    a + 1, "✅" if hello.is_active else "❌", hello.delay
                )

                kb.add(
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"ChoiceHelloMessage|{hello_messages[idx].id}|{a + 1}",
                    )
                )

        kb.adjust(1)

        if len(hello_messages) <= count_rows:
            pass

        elif len(hello_messages) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceHelloMessage|next|{remover + count_rows}",
                )
            )
        elif remover + count_rows >= len(hello_messages):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceHelloMessage|back|{remover - count_rows}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceHelloMessage|back|{remover - count_rows}",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceHelloMessage|next|{remover + count_rows}",
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("add:button"), callback_data="ChoiceHelloMessage|add"
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceHelloMessage|cancel"
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

            kb.button(text=label, callback_data=f"ChoiceHelloMessageDelay|{seconds}")

        kb.adjust(3)
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceHelloMessageDelay|cancel"
            ),
        )

        return kb.as_markup()

    @classmethod
    def manage_application(
        cls, not_approve_count: int, auto_approve: bool, delay_approve: int
    ):
        kb = cls()

        kb.button(
            text=text("application:count:button").format(not_approve_count),
            callback_data="ManageApplication|...",
        )
        kb.button(
            text=text("application:approve:button").format(
                "✅" if auto_approve else "❌"
            ),
            callback_data="ManageApplication|auto_approve",
        )
        kb.button(
            text=text("application:manual_approve:button"),
            callback_data="ManageApplication|manual_approve",
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
            text=text("application:delay:button").format(variants_dict[delay_approve]),
            callback_data="ManageApplication|delay",
        )
        kb.button(text=text("back:button"), callback_data="ManageApplication|cancel")

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

            kb.button(text=label, callback_data=f"ChoiceApplicationDelay|{seconds}")

        kb.adjust(3)
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceApplicationDelay|cancel"
            ),
        )

        return kb.as_markup()

    @classmethod
    def choice_manual_approve(cls):
        kb = cls()

        kb.button(
            text=text("application:manual_approve:all"),
            callback_data="ChoiceManualApprove|all",
        )
        kb.button(
            text=text("application:manual_approve:part"),
            callback_data="ChoiceManualApprove|part",
        )
        kb.button(
            text=text("application:manual_approve:invite_url"),
            callback_data="ChoiceManualApprove|invite_url",
        )
        kb.button(text=text("back:button"), callback_data="ChoiceManualApprove|cancel")

        kb.adjust(2, 1)
        return kb.as_markup()


class InlineProfile(InlineKeyboardBuilder):
    @classmethod
    def profile_menu(cls):
        kb = cls()

        kb.button(text=text("profile:balance"), callback_data="MenuProfile|balance")
        kb.button(text=text("profile:subscribe"), callback_data="MenuProfile|subscribe")
        kb.button(text=text("profile:referral"), callback_data="MenuProfile|referral")
        kb.button(text=text("profile:settings"), callback_data="MenuProfile|settings")

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def profile_balance(cls):
        kb = cls()

        kb.button(text=text("balance:top_up"), callback_data="Balance|top_up")
        kb.button(text=text("back:button"), callback_data="Balance|back")

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
        kb.button(text=text("subscribe:channels"), callback_data="Subscribe|channels")
        kb.button(text=text("back:button"), callback_data="Subscribe|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def profile_setting(cls):
        kb = cls()

        kb.button(text=text("setting:timezone"), callback_data="Setting|timezone")
        kb.button(text=text("setting:folders"), callback_data="Setting|folders")
        kb.button(text=text("back:button"), callback_data="Setting|back")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_payment_method(
        cls, data: str, has_promo: bool = False, is_subscribe: bool = False
    ):
        kb = cls()

        adjust = []
        if is_subscribe:
            kb.button(
                text=text("payment:method:align_sub"), callback_data=f"{data}|align_sub"
            )
            kb.button(
                text=text("payment:method:balance"), callback_data=f"{data}|balance"
            )
            adjust.extend([1, 1])

        if not has_promo:
            kb.button(text=text("payment:method:promo"), callback_data=f"{data}|promo")
            adjust.append(1)

        kb.button(text=text("payment:method:stars"), callback_data=f"{data}|stars")
        kb.button(
            text=text("payment:method:crypto_bot"), callback_data=f"{data}|crypto_bot"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|back")

        adjust.extend([2, 1])
        kb.adjust(*adjust)
        return kb.as_markup()

    @classmethod
    def choice_period(cls, service: str):
        kb = cls()

        tariffs = Config.TARIFFS.get(service)
        for key in tariffs:
            kb.button(
                text=tariffs[key]["name"], callback_data=f"ChoiceSubscribePeriod|{key}"
            )

        kb.button(text=text("back:button"), callback_data="ChoiceSubscribePeriod|back")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def align_sub(
        cls, sub_objects: list[Channel], chosen: list[Channel], remover: int = 0
    ):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(sub_objects))):
            if a < count_rows:
                resource_id = sub_objects[idx].chat_id

                kb.add(
                    InlineKeyboardButton(
                        text=f"{'🔹' if resource_id in chosen else ''} {sub_objects[idx].title}",
                        callback_data=f"ChoiceResourceAlignSubscribe|{resource_id}|{remover}",
                    )
                )

        kb.adjust(2)

        if len(sub_objects) <= count_rows:
            pass

        elif len(sub_objects) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceResourceAlignSubscribe|next|{remover + count_rows}",
                )
            )
        elif remover + count_rows >= len(sub_objects):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceResourceAlignSubscribe|back|{remover - count_rows}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceResourceAlignSubscribe|back|{remover - count_rows}",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceResourceAlignSubscribe|next|{remover + count_rows}",
                ),
            )

        if sub_objects:
            kb.row(
                InlineKeyboardButton(
                    text=text("chosen:cancel_all")
                    if len(chosen) == len(sub_objects)
                    else text("chosen:choice_all"),
                    callback_data=f"ChoiceResourceAlignSubscribe|choice_all|{remover}",
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data="ChoiceResourceAlignSubscribe|cancel",
            ),
            InlineKeyboardButton(
                text=text("save:button"),
                callback_data="ChoiceResourceAlignSubscribe|align",
            ),
        )

        return kb.as_markup()

    @classmethod
    def choice_object_subscribe(
        cls,
        resources: list[Channel | UserBot],
        chosen: list[Channel | UserBot],
        remover: int = 0,
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
                        text=f"{'🔹' if resource_id in chosen else ''} {resources[idx].title}",
                        callback_data=f"ChoiceResourceSubscribe|{resource_id}|{remover}",
                    )
                )

        kb.adjust(2)

        if len(resources) <= count_rows:
            pass

        elif len(resources) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceResourceSubscribe|next|{remover + count_rows}",
                )
            )
        elif remover + count_rows >= len(resources):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceResourceSubscribe|back|{remover - count_rows}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceResourceSubscribe|back|{remover - count_rows}",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceResourceSubscribe|next|{remover + count_rows}",
                ),
            )

        if resources:
            kb.row(
                InlineKeyboardButton(
                    text=text("chosen:cancel_all")
                    if len(chosen) == len(resources)
                    else text("chosen:choice_all"),
                    callback_data=f"ChoiceResourceSubscribe|choice_all|{remover}",
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceResourceSubscribe|cancel"
            ),
            InlineKeyboardButton(
                text=text("pay:button"), callback_data="ChoiceResourceSubscribe|pay"
            ),
        )

        return kb.as_markup()

    @classmethod
    def folders(cls, folders: list[UserFolder], remover: int = 0):
        kb = cls()
        count_rows = 3

        for a, idx in enumerate(range(remover, len(folders))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=f"{'📕' if folders[idx].type == FolderType.BOT else '📘'} {folders[idx].title}",
                        callback_data=f"ChoiceFolder|{folders[idx].id}|{remover}",
                    )
                )

        kb.adjust(1)

        if len(folders) <= count_rows:
            pass

        elif len(folders) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"ChoiceFolder|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(folders):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"ChoiceFolder|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"ChoiceFolder|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"ChoiceFolder|next|{remover + count_rows}"
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("folders:create:button"), callback_data="ChoiceFolder|create"
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceFolder|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_type_folder(cls):
        kb = cls()

        kb.add(
            InlineKeyboardButton(
                text=text("folder:type:channels"),
                callback_data=f"ChoiceTypeFolder|{FolderType.CHANNEL}",
            ),
            InlineKeyboardButton(
                text=text("folder:type:bots"),
                callback_data=f"ChoiceTypeFolder|{FolderType.BOT}",
            ),
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceTypeFolder|back"
            ),
        )

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_object_folders(
        cls,
        resources: list[Channel | UserBot],
        chosen: list[Channel | UserBot],
        remover: int = 0,
    ):
        kb = cls()
        count_rows = 6

        for a, idx in enumerate(range(remover, len(resources))):
            if a < count_rows:
                if isinstance(resources[idx], Channel):
                    resource_id = resources[idx].chat_id
                else:
                    resource_id = resources[idx].id

                kb.add(
                    InlineKeyboardButton(
                        text=f"{'🔹' if resource_id in chosen else ''} {resources[idx].title}",
                        callback_data=f"ChoiceResourceFolder|{resource_id}|{remover}",
                    )
                )

        kb.adjust(2)

        if len(resources) <= count_rows:
            pass

        elif len(resources) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceResourceFolder|next|{remover + count_rows}",
                )
            )
        elif remover + count_rows >= len(resources):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceResourceFolder|back|{remover - count_rows}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"ChoiceResourceFolder|back|{remover - count_rows}",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"ChoiceResourceFolder|next|{remover + count_rows}",
                ),
            )

        if resources:
            kb.row(
                InlineKeyboardButton(
                    text=text("chosen:cancel_all")
                    if len(chosen) == len(resources)
                    else text("chosen:choice_all"),
                    callback_data=f"ChoiceResourceFolder|choice_all|{remover}",
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ChoiceResourceFolder|cancel"
            ),
            InlineKeyboardButton(
                text=text("next:button"), callback_data="ChoiceResourceFolder|next_step"
            ),
        )

        return kb.as_markup()

    @classmethod
    def manage_folder(cls):
        kb = cls()

        kb.button(
            text=text("manage:folder:content:button"),
            callback_data="ManageFolder|content",
        )
        kb.button(
            text=text("manage:folder:title:button"), callback_data="ManageFolder|title"
        )
        kb.button(
            text=text("manage:folder:remove:button"),
            callback_data="ManageFolder|remove",
        )
        kb.button(text=text("back:button"), callback_data="ManageFolder|back")

        kb.adjust(1)
        return kb.as_markup()


class InlineAdmin(InlineKeyboardBuilder):
    @classmethod
    def admin(cls):
        kb = cls()

        kb.button(text="👤 Сессии", callback_data="Admin|session")
        kb.button(text="📩 Рассылка", callback_data="Admin|mail")
        kb.button(text="📊 Статистика сервиса", callback_data="Admin|stats")
        kb.button(text="🎁 Создать промокод", callback_data="Admin|promo")
        kb.button(text="🦋 Рекламные ссылки", callback_data="Admin|ads")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_sessions(cls):
        kb = cls()

        kb.button(text=text("add:button"), callback_data="AdminSession|add")
        kb.button(text=text("back:button"), callback_data="AdminSession|cancel")

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

        kb.button(text=text("cancel"), callback_data=data)

        return kb.as_markup()

    @classmethod
    def back(cls, data: str):
        kb = cls()

        kb.button(text=text("back:button"), callback_data=data)

        return kb.as_markup()

    @classmethod
    def accept(cls, data: str):
        kb = cls()

        kb.button(text=text("delete:button"), callback_data=data + "|yes")
        kb.button(text=text("back:button"), callback_data=data)

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def wait_payment(cls, data: str, pay_url: str):
        kb = cls()

        kb.button(text=text("go_to_payment"), url=pay_url)
        kb.button(text=text("back:button"), callback_data=f"{data}")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def channels(
        cls, channels: list[Channel], data: str = "ChoicePostChannel", remover: int = 0
    ):
        kb = cls()
        count_rows = 3

        for a, idx in enumerate(range(remover, len(channels))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=channels[idx].title,
                        callback_data=f"{data}|{channels[idx].chat_id}|{remover}",
                    )
                )

        kb.adjust(1)

        if len(channels) <= count_rows:
            pass

        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("channels:add:button"), callback_data=f"{data}|add"
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def add_channel(cls, bot_username: str, data: str = "BackAddChannelPost"):
        kb = cls()

        kb.button(
            text=text("channels:add:button"),
            url=f"https://t.me/{bot_username}?startchannel&admin=change_info+post_messages+edit_messages+delete_messages+promote_members+invite_users",
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_channel(cls, data: str = "ManageChannelPost"):
        kb = cls()

        kb.button(text=text("channel:delete:button"), callback_data=f"{data}|delete")
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_objects(
        cls,
        resources: list[Channel | UserBot],
        chosen: list[Channel | UserBot],
        folders: list[UserFolder],
        chosen_folders: list[UserFolder],
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
                    button_text = (
                        f"{'🔹' if resource_id in chosen else ''} {objects[idx].title}"
                    )
                elif isinstance(objects[idx], UserBot):
                    resource_id = objects[idx].id
                    resource_type = "bot"
                    button_text = (
                        f"{'🔹' if resource_id in chosen else ''} {objects[idx].title}"
                    )
                else:
                    resource_id = objects[idx].id
                    resource_type = "folder"
                    button_text = f"{'🔹' if resource_id in chosen_folders else ''} Папка {objects[idx].title}"

                kb.add(
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"{data}|{resource_id}|{remover}|{resource_type}",
                    )
                )

        kb.adjust(1)

        if len(objects) <= count_rows:
            pass

        elif len(objects) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(objects):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                ),
            )

        if objects:
            kb.row(
                InlineKeyboardButton(
                    text=text("chosen:cancel_all")
                    if (len(chosen) + len(chosen_folders)) == len(objects)
                    else text("chosen:choice_all"),
                    callback_data=f"{data}|choice_all|{remover}",
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
            ),
            InlineKeyboardButton(
                text=text("next:button"), callback_data=f"{data}|next_step"
            ),
        )

        return kb.as_markup()

    @classmethod
    def choice_object_content(
        cls,
        channels: list[Channel | UserBot],
        data: str = "ChoiceObjectContentPost",
        remover: int = 0,
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
                        text=channels[idx].title, callback_data=f"{data}|{resource_id}"
                    )
                )

        kb.adjust(2)

        if len(channels) <= count_rows:
            pass

        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_row_content(
        cls,
        posts: list[Post | Story | BotPost],
        day: datetime,
        show_more: bool = False,
        data: str = "ContentPost",
    ):
        kb = cls()

        for post in posts:
            emoji = "⏳"

            if isinstance(post, Post):
                options = post.message_options
                message_text = options.get("text") or options.get("caption")
            elif isinstance(post, BotPost):
                options = post.message
                message_text = options.get("text") or options.get("caption")
                emoji = "⏳" if post.status == Status.PENDING else "✅"
            else:
                options = post.story_options
                message_text = options.get("caption")

            if message_text:
                message_text = message_text.replace("tg-emoji emoji-id", "").replace(
                    "</tg-emoji>", ""
                )
                message_text = re.sub(r"<[^>]+>", "", message_text)

            kb.row(
                InlineKeyboardButton(
                    text="{} {} | {}".format(
                        emoji,
                        datetime.fromtimestamp(
                            post.send_time or post.start_timestamp
                        ).strftime("%d.%m.%Y %H:%M"),
                        message_text or "Медиа",
                    ),
                    callback_data=f"{data}|{post.id}",
                )
            )

        if not show_more:
            kb.row(
                InlineKeyboardButton(text="⬅️", callback_data=f"{data}|back_day|1"),
                InlineKeyboardButton(
                    text=f"{day.day} {text('month').get(str(day.month))}",
                    callback_data=f"{data}|...",
                ),
                InlineKeyboardButton(text="➡️", callback_data=f"{data}|next_day|-1"),
            )
            kb.row(
                InlineKeyboardButton(
                    text=text("expand:content:button"),
                    callback_data=f"{data}|show_more",
                )
            )

        else:
            kb.row(
                InlineKeyboardButton(
                    text=text("short:content:button"), callback_data=f"{data}|show_more"
                )
            )
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"{data}|back_month|{monthrange(day.year, day.month)[1]}",
                ),
                InlineKeyboardButton(
                    text=f"{text('other_month').get(str(day.month))} {day.year}",
                    callback_data=f"{data}|...",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"{data}|next_month|{-monthrange(day.year, day.month)[1]}",
                ),
            )

            month = monthcalendar(day.year, day.month)
            for week in month:
                days = []
                for week_day in week:
                    days.append(
                        InlineKeyboardButton(
                            text="...", callback_data="ContentPost|..."
                        )
                        if week_day == 0
                        else InlineKeyboardButton(
                            text=str(week_day) if week_day != day.day else "🔸",
                            callback_data=f"{data}|choice_day|{day.year}-{day.month}-{week_day}",
                        )
                    )
                kb.row(*days)

            kb.row(
                InlineKeyboardButton(text="⬅️", callback_data=f"{data}|back_day|1"),
                InlineKeyboardButton(
                    text=f"{day.day} {text('month').get(str(day.month))}",
                    callback_data=f"{data}|...",
                ),
                InlineKeyboardButton(text="➡️", callback_data=f"{data}|next_day|-1"),
            )

        kb.row(
            InlineKeyboardButton(
                text=text(
                    "show_all:content{}:button".format(
                        ":story" if data == "ContentStories" else ""
                    )
                ),
                callback_data=f"{data}|show_all",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def choice_time_objects(
        cls,
        objects: list[Post | Story | BotPost],
        data: str = "ChoiceTimeObjectContentPost",
        remover: int = 0,
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
                    message_text = message_text.replace(
                        "tg-emoji emoji-id", ""
                    ).replace("</tg-emoji>", "")
                    message_text = re.sub(r"<[^>]+>", "", message_text)

                kb.row(
                    InlineKeyboardButton(
                        text="{} {} | {}".format(
                            emoji,
                            datetime.fromtimestamp(objects[idx].send_time).strftime(
                                "%d.%m.%Y %H:%M"
                            ),
                            message_text or "Медиа",
                        ),
                        callback_data=f"{obj_data}|{objects[idx].id}",
                    )
                )

        kb.adjust(1)

        if len(objects) <= count_rows:
            pass

        elif len(objects) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                )
            )
        elif remover + count_rows >= len(objects):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{data}|back|{remover - count_rows}"
                ),
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{data}|next|{remover + count_rows}"
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data=f"{data}|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def accept_delete_row_content(cls, data: str = "AcceptDeletePost"):
        kb = cls()

        kb.button(
            text=text("manage:post:delete:button"), callback_data=f"{data}|accept"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()


class Keyboards(Reply, Inline):
    pass


keyboards = Keyboards()
