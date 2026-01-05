"""
Клавиатуры для настроек ботов: капча, приветствия, клонер, авто-прием и т.д.
"""

from typing import List

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.database.channel.model import Channel
from main_bot.database.channel_bot_captcha.model import ChannelCaptcha
from main_bot.database.channel_bot_hello.model import ChannelHelloMessage
from main_bot.database.channel_bot_settings.model import ChannelBotSetting
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import HelloAnswer, ByeAnswer, CaptchaObj
from main_bot.keyboards.base import _parse_button


class InlineBotSetting(InlineKeyboardBuilder):
    """Клавиатуры для настроек ботов"""

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
        cls, channels: List[Channel], chosen: list, remover: int = 0
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
                    text=(
                        text("chosen:cancel_all")
                        if len(chosen) == len(channels)
                        else text("chosen:choice_all")
                    ),
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
        channel_captcha_list: List[ChannelCaptcha],
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
            row_buttons = []
            for button in row.split("|"):
                btn_text, btn_url = _parse_button(button)
                if btn_url:  # Только если есть URL
                    row_buttons.append(InlineKeyboardButton(text=btn_text, url=btn_url))
            if row_buttons:
                kb.row(*row_buttons)

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
        channels: List[Channel],
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
                text=text("back:button"), callback_data=f"{data}|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def add_channel(cls, data: str = "BackAddChannel"):
        kb = cls()
        from config import Config

        kb.button(
            text=text("add_channel:button"),
            url=f"https://t.me/{Config.BOT_USERNAME}?startchannel&admin=change_info+post_messages+edit_messages+delete_messages+post_stories+edit_stories+delete_stories+promote_members+invite_users",
        )
        kb.button(text=text("add_channel_later:button"), callback_data=f"{data}|menu")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def bot_setting_menu(cls, channel_settings: ChannelBotSetting):
        kb = cls()

        bye = ByeAnswer(**channel_settings.bye)

        # Ряд 1: Автоприём + Приветствие
        kb.button(
            text=text("bot_menu:application").format(
                "✅" if channel_settings.auto_approve else "❌"
            ),
            callback_data="BotSettingMenu|application",
        )
        kb.button(text=text("bot_menu:hello"), callback_data="BotSettingMenu|hello")

        # Ряд 2: Капча + Прощание
        kb.button(
            text=text("bot_menu:captcha").format(
                "✅" if channel_settings.active_captcha_id else "❌"
            ),
            callback_data="BotSettingMenu|captcha",
        )
        kb.button(
            text=text("bot_menu:bye").format("✅" if bye.active else "❌"),
            callback_data="BotSettingMenu|bye",
        )

        # Ряд 3: Клонировать + Чистка
        kb.button(text=text("bot_menu:cloner"), callback_data="BotSettingMenu|clone")
        kb.button(text=text("bot_menu:cleaner"), callback_data="BotSettingMenu|cleaner")

        # Ряд 4: Назад + Обновить данные
        kb.button(text=text("back:button"), callback_data="BotSettingMenu|back")
        kb.button(text=text("bot_menu:update"), callback_data="BotSettingMenu|update")

        kb.adjust(2, 2, 2, 2)
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
        cls, hello_messages: List[ChannelHelloMessage], remover: int = 0
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
        # kb.row(
        #     InlineKeyboardButton(
        #         text=text("back:button"), callback_data="ChoiceHelloMessage|cancel"
        #     )
        # )

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
