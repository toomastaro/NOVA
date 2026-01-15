"""
Модуль создания клавиатур (keyboards).

Содержит методы для генерации Inline-клавиатур.
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder

from hello_bot.utils.schemas import Answer, HelloAnswer, Protect
from hello_bot.utils.lang.language import text


class Inline(InlineKeyboardBuilder):
    """Базовый класс для создания клавиатур."""

    @classmethod
    def cancel(cls, data: str):
        """Кнопка отмены."""
        kb = cls()

        kb.button(text=text("cancel"), callback_data=data)

        return kb.as_markup()

    @classmethod
    def back(cls, data: str):
        """Кнопка назад."""
        kb = cls()

        kb.button(text=text("back:button"), callback_data=data)

        return kb.as_markup()

    @classmethod
    def add_channel(cls, bot_username: str, data: str = "BackAddChannel"):
        """Кнопки добавления бота в канал."""
        kb = cls()

        kb.button(
            text=text("add_channel:button"),
            url=f"https://t.me/{bot_username}?startchannel&admin=invite_users",
        )
        kb.button(text=text("add_channel_later:button"), callback_data=f"{data}|menu")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def menu(cls):
        """Главное меню."""
        kb = cls()

        kb.button(text=text("menu:stats"), callback_data="Menu|stats")
        kb.button(text=text("menu:answer"), callback_data="Menu|answer")
        kb.button(text=text("menu:hello"), callback_data="Menu|hello")
        kb.button(text=text("menu:bye"), callback_data="Menu|bye")
        kb.button(text=text("menu:application"), callback_data="Menu|application")

        kb.adjust(2, 2, 1)
        return kb.as_markup()

    @classmethod
    def answers(cls, settings):
        """Клавиатура списка ответов."""
        kb = cls()

        for answer in settings.answers:
            answer = Answer(**dict(answer))

            kb.button(
                text="#{} - {}".format(answer.id, answer.key.split()[0]),
                callback_data="Answer|{}".format(answer.id),
            )

        kb.button(text=text("answer:add:button"), callback_data="Answer|add")
        kb.button(text=text("back:button"), callback_data="Answer|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_answer(cls):
        """Меню управления ответом."""
        kb = cls()

        kb.button(
            text=text("answer:change:keyword"), callback_data="ManageAnswer|keyword"
        )
        kb.button(
            text=text("answer:change:message"), callback_data="ManageAnswer|message"
        )
        kb.button(text=text("answer:delete"), callback_data="ManageAnswer|delete")
        kb.button(text=text("back:button"), callback_data="ManageAnswer|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def param_answers_back(cls, data: str = "BackAddAnswer"):
        """Кнопки назад при редактировании ответа."""
        kb = cls()

        kb.button(text=text("back:step"), callback_data=f"{data}|step")
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def manage_answer_user(cls, obj: HelloAnswer, data: str = "ManageHello"):
        """Меню управления приветствием/прощанием."""
        kb = cls()

        kb.button(
            text=text("{}:button".format("on" if obj.active else "off")),
            callback_data=f"{data}|active",
        )
        kb.button(
            text=text("{}:button".format("add" if not obj.message else "delete")),
            callback_data=f"{data}|message",
        )
        kb.button(text=text("bye:buttons:button"), callback_data=f"{data}|buttons")
        kb.button(text=text("check:button"), callback_data=f"{data}|check")
        kb.button(text=text("back:button"), callback_data=f"{data}|cancel")

        kb.adjust(2, 1)
        return kb.as_markup()

    @classmethod
    def manage_application(cls, setting):
        """Меню управления заявками."""
        kb = cls()
        protect = Protect(**setting.protect)

        kb.button(
            text=text("application:delay:button"),
            callback_data="ManageApplication|delay_approve",
        )
        kb.button(
            text=text("application:protect:arab:button").format(
                "✅" if protect.arab else "❌"
            ),
            callback_data="ManageApplication|protect_arab",
        )
        kb.button(
            text=text("application:protect:china:button").format(
                "✅" if protect.china else "❌"
            ),
            callback_data="ManageApplication|protect_china",
        )
        kb.button(
            text=text("application:approve:button").format(
                "✅" if setting.auto_approve else "❌"
            ),
            callback_data="ManageApplication|auto_approve",
        )
        kb.button(text=text("back:button"), callback_data="ManageApplication|cancel")

        kb.adjust(1)
        return kb.as_markup()


class Keyboards(Inline):
    pass


keyboards = Keyboards()
