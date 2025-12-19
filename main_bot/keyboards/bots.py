"""
Клавиатуры для управления ботами и постинга через ботов.
"""

from calendar import monthrange, monthcalendar
from datetime import datetime
from typing import List

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.database.bot_post.model import BotPost
from main_bot.database.user_bot.model import UserBot
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import MessageOptionsHello
from typing import Any, Dict, Union


class DictObj:
    """Вспомогательный класс для преобразования ключей словаря в атрибуты."""

    def __init__(self, in_dict: Dict[str, Any]):
        for key, val in in_dict.items():
            setattr(self, key, val)


def ensure_bot_post_obj(
    post: Union[BotPost, Dict[str, Any]],
) -> Union[BotPost, DictObj]:
    """
    Гарантирует, что входные данные являются объектом с атрибутами, а не словарем.
    """
    if isinstance(post, dict):
        return DictObj(post)
    return post


def ensure_bot_obj(bot: Union[UserBot, Dict[str, Any]]) -> Union[UserBot, DictObj]:
    """
    Гарантирует, что входные данные являются объектом с атрибутами, а не словарем.
    """
    if isinstance(bot, dict):
        return DictObj(bot)
    return bot


class InlineBots(InlineKeyboardBuilder):
    """Клавиатуры для управления ботами"""

    @classmethod
    def bots_menu(cls):
        kb = cls()

        kb.button(text=text("bots:create_post"), callback_data="MenuBots|create_post")
        kb.button(text=text("bots:content_plan"), callback_data="MenuBots|content_plan")
        kb.button(text=text("bots:add:button"), callback_data="ChoiceBots|add")

        kb.adjust(1, 1, 1)
        return kb.as_markup()

    @classmethod
    def choice_bots(
        cls, bots: List[UserBot], data: str = "ChoiceBots", remover: int = 0
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
        post = ensure_bot_post_obj(post)
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
        obj = ensure_bot_post_obj(obj)

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
            text=text("manage:post_bot:public:button"), callback_data=f"{data}|public"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
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
        kb.row(
            InlineKeyboardButton(text="1 мин.", callback_data="GetDeleteTimeBotPost|60")
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
        post = ensure_bot_post_obj(post)

        # Первый ряд: Изменить | Дата/Время
        kb.button(
            text=text("manage:post:change:button"),
            callback_data="ManageRemainBotPost|change",
        )
        kb.button(
            text=text("manage:post:send_time:button"),
            callback_data="FinishBotPostParams|send_time",
        )

        # Второй ряд: Таймер удаления | Удалить
        delete_time_text = (
            "Нет" if not post.delete_time else f"{int(post.delete_time / 3600)} ч."
        )
        kb.button(
            text=text("manage:post:del_time:button").format(delete_time_text),
            callback_data="FinishBotPostParams|delete_time",
        )
        kb.button(
            text=text("manage:post:delete:button"),
            callback_data="ManageRemainBotPost|delete",
        )

        # Третий ряд: Назад
        kb.button(text=text("back:button"), callback_data="ManageRemainBotPost|cancel")

        kb.adjust(2, 2, 1)  # 2 кнопки в первом ряду, 2 во втором, 1 в третьем
        return kb.as_markup()

    @classmethod
    def manage_bot(cls, user_bot: UserBot, status: bool):
        kb = cls()
        user_bot = ensure_bot_obj(user_bot)

        # kb.button(
        #     text=text("manage:bot:manage"),
        #     callback_data=f"ManageBot|settings|{user_bot.id}",
        # )

        kb.button(
            text=text("manage:bot:{}_channel".format("add")),
            url="t.me/{}?startchannel&admin=change_info+post_messages+edit_messages+delete_messages+post_stories+edit_stories+delete_stories+promote_members+invite_users".format(
                user_bot.username
            ),
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

    @classmethod
    def accept_bot_public(cls, data: str = "AcceptBotPost"):
        kb = cls()

        kb.button(
            text=text("manage:post_bot:public:button"), callback_data=f"{data}|public"
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def bot_post_kb(cls, post: BotPost):
        kb = cls()
        options = MessageOptionsHello(**post.message)

        if options.reply_markup:
            for row in options.reply_markup.inline_keyboard:
                kb.row(*row)

        return kb.as_markup()

    @classmethod
    def accept_bot_date(cls, data: str = "AcceptBotPost"):
        """Клавиатура подтверждения запланированной рассылки"""
        kb = cls()

        kb.button(
            text=text("manage:post_bot:accept:date:button"),
            callback_data=f"{data}|send_time",
        )
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()
