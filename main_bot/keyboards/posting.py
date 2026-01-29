"""
Модуль клавиатур для управления постингом и создания контента.
Содержит инструменты для формирования inline-кнопок управления постами.
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
    """
    Обёртка для словаря, позволяющая обращаться к ключам как к атрибутам.
    Возвращает None, если атрибут не найден.
    """

    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        return self._data.get(name, None)


def ensure_obj(obj):
    """
    Проверяет объект, и если это словарь, оборачивает его в ObjWrapper.

    Аргументы:
        obj: Объект или словарь данных.

    Возвращает:
        Объект или ObjWrapper.
    """
    if isinstance(obj, dict):
        return ObjWrapper(obj)
    return obj


def safe_post_from_dict(data: dict) -> Post | ObjWrapper:
    """
    Создает экземпляр Post из словаря, отфильтровывая лишние поля.

    Аргументы:
        data: Словарь с данными поста.

    Возвращает:
        Экземпляр Post или ObjWrapper при ошибке валидации.
    """
    if not data:
        return None

    if "post_id" in data or "message_id" in data:
        return ObjWrapper(data)

    valid_fields = {
        "id",
        "chat_ids",
        "admin_id",
        "message_options",
        "buttons",
        "send_time",
        "reaction",
        "hide",
        "pin_time",
        "delete_time",
        "report",
        "cpm_price",
        "backup_chat_id",
        "backup_message_id",
        "views_24h",
        "views_48h",
        "views_72h",
        "report_24h_sent",
        "report_48h_sent",
        "report_72h_sent",
        "created_timestamp",
    }

    filtered_data = {k: v for k, v in data.items() if k in valid_fields}

    try:
        return Post(**filtered_data)
    except (TypeError, ValueError):
        return ObjWrapper(data)


class InlinePosting(InlineKeyboardBuilder):
    """
    Класс для создания inline-клавиатур, связанных с постингом.
    """

    @classmethod
    def posting_menu(cls):
        """
        Главное меню постинга.

        Возвращает:
            Готовую разметку клавиатуры.
        """
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
        """
        Клавиатура управления черновиком поста (настройка кнопок, реакций, скрытия и т.д.).

        Аргументы:
            post: Объект поста.
            show_more: Флаг отображения дополнительных настроек.
            is_edit: Флаг режима редактирования.
        """
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
                    if btn_url:
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
                    text=text("manage:post:media_above:button") if not options.show_caption_above_media else text("manage:post:media_below:button"),
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

        from main_bot.database.published_post.model import PublishedPost

        is_published = isinstance(post, PublishedPost) or getattr(
            post, "is_published", False
        )

        if is_published or is_edit:
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
                    text=text("next:button"),
                    callback_data=f"ManagePost|next|{post.id}",
                ),
            )

        return kb.as_markup()

    @classmethod
    def post_kb(cls, post: Post | PublishedPost | BotPost, is_bot: bool = False):
        """
        Генерация клавиатуры, прикрепляемой к самому посту (кнопки-ссылки, скрытие, реакции).

        Аргументы:
            post: Объект поста.
            is_bot: Если True, игнорирует скрытие и реакции (для бот-постов).
        """
        post = ensure_obj(post)
        kb = cls()

        if post.buttons:
            for row in post.buttons.split("\n"):
                buttons = []
                for button in row.split("|"):
                    btn_text, btn_url = _parse_button(button)
                    if btn_url:
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
                            callback_data=f"ClickHide|{row_hide.id}",
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
                                callback_data=f"ClickReact|{react.id}",
                            )
                        )
                    kb.row(*buttons)

        return kb.as_markup()

    @classmethod
    def param_cancel(cls, param: str, data: str = "ParamCancel", post=None):
        """
        Универсальная клавиатура для отмены ввода параметра.
        """
        post = ensure_obj(post)
        kb = cls()
        kb.button(
            text=text(f"manage:post:delete:param:{param}:button"),
            callback_data=f"{data}|delete",
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def param_cpm_input(cls, param: str):
        """
        Клавиатура для ввода значения CPM с кнопками быстрого выбора.
        Позволяет быстро выбрать предустановленное значение или вернуться назад.

        Аргументы:
            param: Имя параметра (для совместимости или отображения).
        """
        kb = cls()

        # Кнопки быстрого выбора CPM в 4 ряда по 4 кнопки
        # Ряд 1: 100, 200, 300, 400
        kb.row(
            InlineKeyboardButton(text="100₽", callback_data="ParamCancel|set|100"),
            InlineKeyboardButton(text="200₽", callback_data="ParamCancel|set|200"),
            InlineKeyboardButton(text="300₽", callback_data="ParamCancel|set|300"),
            InlineKeyboardButton(text="400₽", callback_data="ParamCancel|set|400"),
        )

        # Ряд 2: 500, 600, 700, 800
        kb.row(
            InlineKeyboardButton(text="500₽", callback_data="ParamCancel|set|500"),
            InlineKeyboardButton(text="600₽", callback_data="ParamCancel|set|600"),
            InlineKeyboardButton(text="700₽", callback_data="ParamCancel|set|700"),
            InlineKeyboardButton(text="800₽", callback_data="ParamCancel|set|800"),
        )

        # Ряд 3: 900, 1000, 1500, 2000
        kb.row(
            InlineKeyboardButton(text="900₽", callback_data="ParamCancel|set|900"),
            InlineKeyboardButton(text="1000₽", callback_data="ParamCancel|set|1000"),
            InlineKeyboardButton(text="1500₽", callback_data="ParamCancel|set|1500"),
            InlineKeyboardButton(text="2000₽", callback_data="ParamCancel|set|2000"),
        )

        # Кнопка "Назад"
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="ManageRemainPost|cancel"
            )
        )
        return kb.as_markup()

    @classmethod
    def param_hide(cls, post: Post):
        """
        Клавиатура настройки скрытого контента.
        """
        post = ensure_obj(post)
        kb = cls()
        hide = Hide(hide=post.hide) if post.hide else None

        if hide:
            for hide_item in hide.hide:
                kb.row(
                    InlineKeyboardButton(
                        text=hide_item.button_name, callback_data="..."
                    )
                )

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
        """
        Вернуться назад из настройки скрытия.
        """
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
        """
        Главное меню финализации поста (таймер, публикация, CPM).
        """
        obj = ensure_obj(obj)
        kb = cls()

        is_story = isinstance(obj, Story) or (
            hasattr(obj, "story_options") and getattr(obj, "story_options") is not None
        )

        if is_story:
            options_dict = getattr(obj, "story_options", {}) or {}
            options = StoryOptions(**options_dict)
            delete_time = options.period
        else:
            delete_time = getattr(obj, "delete_time", 0)

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
        """
        Клавиатура выбора времени удаления поста.
        """
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

        kb.row(
            *[
                InlineKeyboardButton(
                    text=f"{m} мин.", callback_data=f"GetDeleteTimePost|{m * 60}"
                )
                for m in groups[0]
            ]
        )
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
        """Приятие даты публикации."""
        kb = cls()
        kb.button(
            text=text("manage:post:accept:date:button"),
            callback_data=f"{data}|send_time",
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def accept_public(cls, data: str = "AcceptPost"):
        """Подтверждение публикации."""
        kb = cls()
        kb.button(
            text=text("manage:post:public:button"), callback_data=f"{data}|public"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def create_finish(cls, data: str = "MenuPosting"):
        """Меню завершения создания (создать новый, контент-план)."""
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
        """
        Управление запланированным (или черновиком) постом из контент-плана.
        Если пост опубликован, вызывает manage_published_post.

        Аргументы:
            post: Объект поста.
            is_published: Флаг того, что пост уже опубликован.
        """
        post = ensure_obj(post)
        kb = cls()
        is_deleted = getattr(post, "status", "active") == "deleted"

        if is_deleted:
            kb.button(text=text("back:button"), callback_data="ManageRemainPost|cancel")
            kb.adjust(1)
            return kb.as_markup()

        if not is_published:
            kb.button(
                text=text("manage:post:change:button"),
                callback_data="ManageRemainPost|change",
            )

            del_time_text = text("manage:post:del_time:not")
            if post.delete_time:
                del_time_text = (
                    f"{int(post.delete_time / 60)} мин."
                    if post.delete_time < 3600
                    else f"{int(post.delete_time / 3600)} ч."
                )

            kb.button(
                text=text("manage:post:del_time:button").format(del_time_text),
                callback_data="FinishPostParams|delete_time",
            )
            kb.button(
                text=text("manage:post:add:cpm:button").format(
                    f"{post.cpm_price}₽" if post.cpm_price else "❌"
                ),
                callback_data="FinishPostParams|cpm_price",
            )
            kb.button(
                text=text("manage:post:send_time").format(
                    datetime.fromtimestamp(post.send_time).strftime("%d.%m %H:%M")
                ),
                callback_data="FinishPostParams|send_time",
            )
            kb.button(
                text=text("manage:post:public:button"),
                callback_data="FinishPostParams|public",
            )
            kb.button(
                text=text("manage:post:delete:button"),
                callback_data="ManageRemainPost|delete",
            )
            kb.button(text=text("back:button"), callback_data="ManageRemainPost|cancel")
            kb.adjust(1)
            return kb.as_markup()
        else:
            return cls.manage_published_post(post)

    @classmethod
    def manage_published_post(cls, post: PublishedPost):
        """
        Управление уже опубликованным постом.

        Аргументы:
            post: Объект PublishedPost.
        """
        post = ensure_obj(post)
        kb = cls()
        is_deleted = getattr(post, "status", "active") == "deleted"

        if is_deleted:
            kb.button(
                text=text("cpm:report:view_button"),
                callback_data="ManagePublishedPost|cpm_report",
            )
            kb.button(
                text=text("back:button"), callback_data="ManagePublishedPost|cancel"
            )
            kb.adjust(1)
            return kb.as_markup()

        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManagePublishedPost|change",
        )

        dt = post.delete_time
        if dt and hasattr(post, "message_id") and hasattr(post, "created_timestamp"):
            dt = post.delete_time - post.created_timestamp

        if not dt:
            timer_text = text("manage:post:del_time:not")
        elif dt % 3600 == 0:
            timer_text = f"{int(dt / 3600)} {text('hours_short')}"
        elif dt > 3600:
            timer_text = f"{int(dt // 3600)} {text('hours_short')} {int((dt % 3600) / 60)} {text('minutes_short')}"
        else:
            timer_text = f"{int(dt / 60)} {text('minutes_short')}"

        kb.button(
            text=text("manage:post:del_time:button").format(timer_text),
            callback_data="ManagePublishedPost|timer",
        )
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
        kb.button(
            text=text("cpm:report:view_button"),
            callback_data="ManagePublishedPost|cpm_report",
        )
        # Кнопка для теста отчета шедулера
        kb.button(
            text="📊 Тест (Шедулер)",
            callback_data="ManagePublishedPost|test_report",
        )
        kb.button(text=text("back:button"), callback_data="ManagePublishedPost|cancel")
        kb.adjust(1)
        return kb.as_markup()
