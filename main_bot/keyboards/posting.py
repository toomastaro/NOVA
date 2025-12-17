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


class ObjWrapper:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'dict' object has no attribute '{name}'")


def ensure_obj(obj):
    if isinstance(obj, dict):
        return ObjWrapper(obj)
    return obj


class InlinePosting(InlineKeyboardBuilder):
    """Клавиатуры для постинга в каналы"""

    @classmethod
    def posting_menu(cls):
        kb = cls()

        kb.button(
            text=text("posting:create_post"), callback_data="MenuPosting|create_post"
        )
        kb.button(
            text=text("posting:content_plan"), callback_data="MenuPosting|content_plan"
        )
        kb.button(
            text=text("channels:add:button"), callback_data="ChoicePostChannel|add"
        )

        kb.adjust(1, 1, 1)
        return kb.as_markup()

    @classmethod
    def manage_post(cls, post: Post, show_more: bool = False, is_edit: bool = False):
        post = ensure_obj(post)
        kb = cls()
        hide = Hide(hide=post.hide) if post.hide else None

        reaction_data = getattr(post, "reaction", None)
        reactions = React(rows=reaction_data.get("rows")) if reaction_data else None

        options = MessageOptions(**post.message_options)

        if hide:
            for row_hide in hide.hide:
                kb.row(
                    InlineKeyboardButton(text=row_hide.button_name, callback_data="...")
                )

        if post.buttons:
            for row in post.buttons.split("\n"):
                buttons = []
                for button in row.split("|"):
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
            ),
            InlineKeyboardButton(
                text=text(
                    "manage:post:{}:media:button".format(
                        "edit"
                        if options.photo or options.video or options.animation
                        else "add"
                    )
                ),
                callback_data=f"ManagePost|media|{post.id}",
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text=text("manage:post:add:url_buttons:button"),
                callback_data=f"ManagePost|buttons|{post.id}",
            ),
            InlineKeyboardButton(
                text=text("manage:post:notification:button").format(
                    "🔔" if not options.disable_notification else "🔕"
                ),
                callback_data=f"ManagePost|notification|{post.id}",
            ),
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
                        "✅"
                        if getattr(post, "pin_time", getattr(post, "unpin_time", None))
                        else "❌"
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
                    text=text("manage:post:hide_more:button"),
                    callback_data=f"ManagePost|show_more|{post.id}",
                )
            )

        # Для уже опубликованных постов кнопка Сохранить избыточна
        from main_bot.database.published_post.model import PublishedPost

        is_published = isinstance(post, PublishedPost) or getattr(
            post, "is_published", False
        )

        if is_published:
            kb.row(
                InlineKeyboardButton(
                    text=text("back:button"),
                    callback_data=f"ManagePost|cancel|{post.id}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text=text("back:button"),
                    callback_data=f"ManagePost|cancel|{post.id}",
                ),
                InlineKeyboardButton(
                    text=text("{}:button".format("save" if is_edit else "next")),
                    callback_data=f"ManagePost|next|{post.id}",
                ),
            )

        return kb.as_markup()

    @classmethod
    def post_kb(cls, post: Post | PublishedPost | BotPost, is_bot: bool = False):
        post = ensure_obj(post)
        kb = cls()

        if post.buttons:
            for row in post.buttons.split("\n"):
                buttons = []
                for button in row.split("|"):
                    btn_text, btn_url = _parse_button(button)
                    if btn_url:  # Только если есть URL
                        buttons.append(InlineKeyboardButton(text=btn_text, url=btn_url))
                if buttons:
                    kb.row(*buttons)

        if not is_bot:
            hide = Hide(hide=post.hide) if post.hide else None

            reaction_data = getattr(post, "reaction", None)
            reactions = React(rows=reaction_data.get("rows")) if reaction_data else None

            if hide:
                for row_hide in hide.hide:
                    kb.row(
                        InlineKeyboardButton(
                            text=row_hide.button_name,
                            callback_data="ClickHide|{}".format(row_hide.id),
                        )
                    )

            if reactions:
                for row in reactions.rows:
                    buttons = []
                    for react in row.reactions:
                        buttons.append(
                            InlineKeyboardButton(
                                text=(
                                    react.react
                                    if not len(react.users)
                                    else f"{react.react} {len(react.users)}"
                                ),
                                callback_data="ClickReact|{}".format(react.id),
                            )
                        )
                    kb.row(*buttons)

        return kb.as_markup()

    @classmethod
    def param_cancel(cls, param: str, data: str = "ParamCancel"):
        kb = cls()

        kb.button(
            text=text("manage:post:delete:param:{}:button".format(param)),
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
        obj = ensure_obj(obj)
        kb = cls()

        # Determine type based on available fields if it's a wrapper/dict
        is_story = hasattr(obj, "story_options") or isinstance(obj, Story)

        if is_story:
            options = StoryOptions(**obj.story_options)
            delete_time = options.period
        else:
            # Assume Post
            delete_time = getattr(obj, "delete_time", 0)

        # Report & CPM buttons only for Posts
        if not is_story:
            # report = getattr(obj, "report", False)
            # kb.button(
            #     text=text("manage:post:report:button").format("✅" if report else "❌"),
            #     callback_data=f"{data}|report",
            # )
            pass

        kb.button(
            text=text("manage:post:del_time:button").format(
                (
                    f"{int(delete_time / 60)} мин."
                    if delete_time < 3600
                    else f"{int(delete_time / 3600)} ч."
                )
                if delete_time
                else text("manage:post:del_time:not")
            ),
            callback_data=f"{data}|delete_time",
        )

        if not is_story:
            cpm_price = getattr(obj, "cpm_price", None)
            kb.button(
                text=text("manage:post:add:cpm:button").format(
                    f"{cpm_price}₽" if cpm_price else "❌"
                ),
                callback_data=f"{data}|cpm_price",
            )

        kb.button(
            text=text("manage:post:send_time:button"), callback_data=f"{data}|send_time"
        )
        kb.button(
            text=text("manage:post:public:button"), callback_data=f"{data}|public"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
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
        groups = [
            [1, 15, 30, 45],  # минуты
            [1, 2, 4, 6],  # часы
            [6, 8, 10, 12],  # часы
            [18, 24, 48, 72],  # часы
        ]

        # Первый ряд - минуты
        kb.row(
            *[
                InlineKeyboardButton(
                    text=f"{m} мин.", callback_data=f"GetDeleteTimePost|{m * 60}"
                )
                for m in groups[0]
            ]
        )

        # Остальные ряды - часы
        for group in groups[1:]:
            kb.row(
                *[
                    InlineKeyboardButton(
                        text=f"{h} ч.", callback_data=f"GetDeleteTimePost|{h * 3600}"
                    )
                    for h in group
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
            text=text("manage:post:accept:date:button"),
            callback_data=f"{data}|send_time",
        )
        # kb.button(
        #     text=text("manage:post:send_time:button"),
        #     callback_data=f"{data}|change_time",
        # )
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
    def manage_remain_post(cls, post: Post, is_published: bool = False):
        post = ensure_obj(post)
        kb = cls()

        # Check for deleted status
        is_deleted = getattr(post, "status", "active") == "deleted"

        if is_deleted:
            # Report is shown in text, buttons are for returning
            # User requested: "посмотреть отчет об удалении поста" - done via text
            kb.button(text=text("back:button"), callback_data="ManageRemainPost|cancel")
            kb.adjust(1)
            return kb.as_markup()

        if not is_published:
            # SCHEDULED
            # 1. Изменить пост
            kb.button(
                text=text("manage:post:change:button"),
                callback_data="ManageRemainPost|change",
            )

            # 2. Настроить таймер удаления
            del_time_text = text("manage:post:del_time:not")
            if post.delete_time:
                if post.delete_time < 3600:
                    del_time_text = f"{int(post.delete_time / 60)} мин."
                else:
                    del_time_text = f"{int(post.delete_time / 3600)} ч."

            kb.button(
                text=text("manage:post:del_time:button").format(del_time_text),
                callback_data="FinishPostParams|delete_time",
            )

            # 3. Настроить CPM (добавлено)
            kb.button(
                text=text("manage:post:add:cpm:button").format(
                    f"{post.cpm_price}₽" if post.cpm_price else "❌"
                ),
                callback_data="FinishPostParams|cpm_price",
            )

            # 4. Изменить время (Send Time)
            kb.button(
                text=text("manage:post:send_time").format(
                    datetime.fromtimestamp(post.send_time).strftime("%d.%m %H:%M")
                ),
                callback_data="FinishPostParams|send_time",
            )

            # 5. Опубликовать сейчас
            kb.button(
                text=text("manage:post:public:button"),
                callback_data="FinishPostParams|public",
            )

            kb.row(
                InlineKeyboardButton(
                    text=text("back:button"), callback_data="ManageRemainPost|cancel"
                ),
                InlineKeyboardButton(
                    text=text("manage:post:delete:button"),
                    callback_data="ManageRemainPost|delete",
                ),
            )
            # Layout:
            # [Change]
            # [Timer] [CPM]
            # [Time] [Public Now]
            # [Delete] [Back]
            kb.adjust(
                1, 2, 2
            )  # Adjust for the first 5 buttons, the last row is explicit
            return kb.as_markup()

        else:
            # Should not happen here usually, but if called for published
            return cls.manage_published_post(post)  # type: ignore

    @classmethod
    def manage_published_post(cls, post: PublishedPost):
        post = ensure_obj(post)
        kb = cls()

        # Check for deleted status
        is_deleted = getattr(post, "status", "active") == "deleted"

        if is_deleted:
            # Если пост удален - показываем только кнопку отчета и назад
            kb.button(
                text=text("cpm:report:view_button"),
                callback_data="ManagePublishedPost|cpm_report",
            )

            kb.button(
                text=text("back:button"), callback_data="ManagePublishedPost|cancel"
            )
            kb.adjust(1)
            return kb.as_markup()

        # 1. Изменить + Таймер
        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManagePublishedPost|change",
        )

        # Логика отображения таймера
        dt = post.delete_time
        if not dt:
            timer_text = text("manage:post:del_time:not")
        elif dt % 3600 == 0:
            timer_text = f"{int(dt / 3600)} ч."
        elif dt > 3600:
            timer_text = f"{int(dt // 3600)} ч. {int((dt % 3600) / 60)} мин."
        else:
            timer_text = f"{int(dt / 60)} мин."

        kb.button(
            text=text("manage:post:del_time:button").format(timer_text),
            callback_data="ManagePublishedPost|timer",
        )

        # 2. CPM + Удалить
        kb.button(
            text=text("manage:post:add:cpm:button").format(
                f"{post.cpm_price}₽" if post.cpm_price else "❌"
            ),
            callback_data="ManagePublishedPost|cpm",
        )

        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManagePublishedPost|delete",
        )

        # 3. Назад + Отчет
        kb.button(text=text("back:button"), callback_data="ManagePublishedPost|cancel")

        kb.button(
            text=text("cpm:report:view_button"),
            callback_data="ManagePublishedPost|cpm_report",
        )

        kb.adjust(1)
        return kb.as_markup()
