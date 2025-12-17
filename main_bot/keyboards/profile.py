"""
# FORCE UPDATE
Клавиатуры для профиля пользователя: баланс, подписки, папки, платежи, настройки.
"""

from typing import List

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.database.channel.model import Channel
from main_bot.database.user_bot.model import UserBot
from main_bot.database.user_folder.model import UserFolder
from main_bot.utils.lang.language import text
from config import Config


class InlineProfile(InlineKeyboardBuilder):
    """Клавиатуры для профиля пользователя"""

    @classmethod
    def profile_menu(cls):
        kb = cls()

        kb.button(text=text("posting:channels"), callback_data="MenuProfile|channels")
        kb.button(text=text("bots:bots"), callback_data="MenuProfile|bots")
        kb.button(
            text=text("setting:reports"), callback_data="MenuProfile|report_settings"
        )
        kb.button(text=text("setting:timezone"), callback_data="MenuProfile|timezone")
        kb.button(text=text("setting:folders"), callback_data="MenuProfile|folders")
        kb.button(text=text("reply_menu:support"), callback_data="MenuProfile|support")

        kb.adjust(1)
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

        kb.button(text=text("subscribe:channels"), callback_data="Subscribe|channels")
        kb.button(text=text("back:button"), callback_data="Subscribe|cancel")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def profile_setting(cls):
        kb = cls()

        kb.button(text=text("setting:timezone"), callback_data="Setting|timezone")
        kb.button(text=text("setting:folders"), callback_data="Setting|folders")
        kb.button(text=text("setting:reports"), callback_data="Setting|report_settings")
        kb.button(text=text("reply_menu:support"), callback_data="Setting|support")
        kb.button(text=text("back:button"), callback_data="Setting|back")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def choice_payment_method(
        cls,
        data: str,
        has_promo: bool = False,
        is_subscribe: bool = False,
        show_promo: bool = False,
    ):
        kb = cls()

        adjust = []
        if is_subscribe:
            kb.button(
                text=text("payment:method:balance"), callback_data=f"{data}|balance"
            )
            adjust.extend([1])

        # Показываем промокод ТОЛЬКО для пополнения баланса (не для подписки)
        if not is_subscribe and not has_promo:
            kb.button(text=text("payment:method:promo"), callback_data=f"{data}|promo")
            adjust.extend([1])

        kb.button(text=text("payment:method:stars"), callback_data=f"{data}|stars")
        kb.button(
            text=text("payment:method:crypto_bot"), callback_data=f"{data}|crypto_bot"
        )
        kb.button(text=text("payment:method:platega"), callback_data=f"{data}|platega")
        kb.button(text=text("back:button"), callback_data=f"{data}|back")

        # Все кнопки по одной в ряд
        adjust.extend([1, 1, 1, 1])
        kb.adjust(*adjust)
        return kb.as_markup()

    @classmethod
    def choice_period(cls, service: str):
        kb = cls()

        tariffs = Config.TARIFFS.get(service)
        kb.button(text=tariffs[0]["name"], callback_data="ChoiceSubscribePeriod|0")

        kb.button(text=text("back:button"), callback_data="ChoiceSubscribePeriod|back")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def align_sub(
        cls, sub_objects: List[Channel], chosen: List[Channel], remover: int = 0
    ):
        kb = cls()
        count_rows = 7

        for a, idx in enumerate(range(remover, len(sub_objects))):
            if a < count_rows:
                resource_id = sub_objects[idx].chat_id

                kb.add(
                    InlineKeyboardButton(
                        text=f'{"🔹" if resource_id in chosen else ""} {sub_objects[idx].title}',
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
                    text=(
                        text("chosen:cancel_all")
                        if len(chosen) == len(sub_objects)
                        else text("chosen:choice_all")
                    ),
                    callback_data=f"ChoiceResourceAlignSubscribe|choice_all|{remover}",
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data=f"ChoiceResourceAlignSubscribe|cancel|{remover}",
            ),
            InlineKeyboardButton(
                text="🔄 Выровнять",
                callback_data=f"ChoiceResourceAlignSubscribe|align|{remover}",
            ),
        )

        return kb.as_markup()

    @classmethod
    def choice_object_subscribe(
        cls,
        resources: List[Channel | UserBot],
        chosen: List[Channel | UserBot],
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
                        text=f'{"🔹" if resource_id in chosen else ""} {resources[idx].title}',
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
                    text=(
                        text("chosen:cancel_all")
                        if len(chosen) == len(resources)
                        else text("chosen:choice_all")
                    ),
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
    def folders(cls, folders: List[UserFolder], remover: int = 0):
        kb = cls()
        count_rows = 6

        for a, idx in enumerate(range(remover, len(folders))):
            if a < count_rows:
                kb.add(
                    InlineKeyboardButton(
                        text=f"📁 {folders[idx].title}",
                        callback_data=f"ChoiceFolder|{folders[idx].id}|{remover}",
                    )
                )

        kb.adjust(2)

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

    # choice_type_folder removed

    @classmethod
    def choice_object_folders(
        cls, resources: List[Channel], chosen: List[int], remover: int = 0
    ):
        kb = cls()
        count_rows = 6

        for a, idx in enumerate(range(remover, len(resources))):
            if a < count_rows:
                resource_id = resources[idx].chat_id

                kb.add(
                    InlineKeyboardButton(
                        text=f'{"🔹" if resource_id in chosen else ""} {resources[idx].title}',
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
                    text=(
                        text("chosen:cancel_all")
                        if len(chosen) == len(resources)
                        else text("chosen:choice_all")
                    ),
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

    @classmethod
    def subscription_menu(cls):
        """Меню подписки с балансом, подпиской и реферальной системой"""
        kb = cls()

        kb.button(text=text("balance:top_up"), callback_data="MenuSubscription|top_up")
        kb.button(
            text=text("profile:subscribe"), callback_data="MenuSubscription|subscribe"
        )
        kb.button(
            text=text("payment:method:align_sub"),
            callback_data="MenuSubscription|align_sub",
        )
        kb.button(
            text=text("transfer_subscription:button"),
            callback_data="MenuSubscription|transfer_sub",
        )
        kb.button(
            text=text("profile:referral"), callback_data="MenuSubscription|referral"
        )
        kb.button(text=text("info:button"), callback_data="MenuSubscription|info")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def info_menu(cls):
        """Меню информации с политикой конфиденциальности и пользовательским соглашением"""
        kb = cls()

        kb.add(
            InlineKeyboardButton(
                text=text("info:privacy:button"), url=text("info:privacy:url")
            )
        )
        kb.add(
            InlineKeyboardButton(
                text=text("info:terms:button"), url=text("info:terms:url")
            )
        )
        kb.button(text=text("back:button"), callback_data="InfoMenu|back")

        kb.adjust(1, 1, 1)
        return kb.as_markup()

    @classmethod
    def transfer_sub_choose_donor(cls, channels: List[Channel], remover: int = 0):
        """Клавиатура выбора канала-донора для переноса подписки"""
        kb = cls()
        count_rows = 7

        import time

        for a, idx in enumerate(range(remover, len(channels))):
            if a < count_rows:
                channel = channels[idx]
                # Вычисляем оставшиеся дни
                now = int(time.time())
                days_left = max(0, round((channel.subscribe - now) / 86400))

                kb.add(
                    InlineKeyboardButton(
                        text=f"📺 {channel.title} ({days_left} дн.)",
                        callback_data=f"TransferSubDonor|{channel.chat_id}|{remover}",
                    )
                )

        kb.adjust(1)

        # Навигация
        if len(channels) <= count_rows:
            pass
        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"TransferSubDonor|next|{remover + count_rows}",
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"TransferSubDonor|back|{remover - count_rows}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"TransferSubDonor|back|{remover - count_rows}",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"TransferSubDonor|next|{remover + count_rows}",
                ),
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="TransferSubDonor|cancel"
            )
        )

        return kb.as_markup()

    @classmethod
    def transfer_sub_choose_recipients(
        cls, channels: List[Channel], chosen: List[int], remover: int = 0
    ):
        """Клавиатура выбора каналов-получателей для переноса подписки"""
        kb = cls()
        count_rows = 6

        import time

        for a, idx in enumerate(range(remover, len(channels))):
            if a < count_rows:
                channel = channels[idx]
                # Показываем текущую подписку канала
                sub_text = ""
                if channel.subscribe:
                    now = int(time.time())
                    days_left = max(0, round((channel.subscribe - now) / 86400))
                    sub_text = f" ({days_left} дн.)"

                kb.add(
                    InlineKeyboardButton(
                        text=f'{"🔹" if channel.chat_id in chosen else ""} {channel.title}{sub_text}',
                        callback_data=f"TransferSubRecipients|{channel.chat_id}|{remover}",
                    )
                )

        kb.adjust(2)

        # Навигация
        if len(channels) <= count_rows:
            pass
        elif len(channels) > count_rows > remover:
            kb.row(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"TransferSubRecipients|next|{remover + count_rows}",
                )
            )
        elif remover + count_rows >= len(channels):
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"TransferSubRecipients|back|{remover - count_rows}",
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"TransferSubRecipients|back|{remover - count_rows}",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"TransferSubRecipients|next|{remover + count_rows}",
                ),
            )

        # Кнопка "Выбрать всё" / "Отменить всё"
        if channels:
            kb.row(
                InlineKeyboardButton(
                    text=(
                        text("chosen:cancel_all")
                        if len(chosen) == len(channels)
                        else text("chosen:choice_all")
                    ),
                    callback_data=f"TransferSubRecipients|choice_all|{remover}",
                )
            )

        kb.row(
            InlineKeyboardButton(
                text=text("back:button"),
                callback_data=f"TransferSubRecipients|cancel|{remover}",
            ),
            InlineKeyboardButton(
                text="🔀 Перенести",
                callback_data=f"TransferSubRecipients|transfer|{remover}",
            ),
        )

        return kb.as_markup()

    @classmethod
    def report_settings_menu(
        cls, cpm_active: bool, exchange_active: bool, referral_active: bool
    ):
        kb = cls()

        kb.button(
            text=text("report:cpm:button").format(
                text("report:toggle:on") if cpm_active else text("report:toggle:off")
            ),
            callback_data="ReportSetting|cpm",
        )
        kb.button(
            text=text("report:exchange:button").format(
                text("report:toggle:on")
                if exchange_active
                else text("report:toggle:off")
            ),
            callback_data="ReportSetting|exchange",
        )
        kb.button(
            text=text("report:referral:button").format(
                text("report:toggle:on")
                if referral_active
                else text("report:toggle:off")
            ),
            callback_data="ReportSetting|referral",
        )
        kb.button(text=text("back:button"), callback_data="Setting|reports_back")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def report_setting_item(cls, setting_type: str, is_active: bool):
        kb = cls()

        kb.button(
            text=text("report:toggle:off" if is_active else "report:toggle:on"),
            callback_data=f"ReportSetting|toggle|{setting_type}",
        )
        kb.button(
            text=text("report:edit:text"),
            callback_data=f"ReportSetting|edit|{setting_type}",
        )
        kb.button(text=text("back:button"), callback_data="ReportSetting|back")

        kb.adjust(1)
        return kb.as_markup()
