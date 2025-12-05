"""
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

        kb.button(
            text=text('profile:settings'),
            callback_data='MenuProfile|settings'
        )
        kb.button(
            text=text('reply_menu:support'),
            callback_data='MenuProfile|support'
        )
        kb.button(
            text=text('back:button'),
            callback_data='MenuProfile|back'
        )

        kb.adjust(1, 1, 1)
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

    @classmethod
    def subscription_menu(cls):
        """Меню подписки с балансом, подпиской и реферальной системой"""
        kb = cls()

        kb.button(
            text=text('profile:balance'),
            callback_data='MenuSubscription|balance'
        )
        kb.button(
            text=text('profile:subscribe'),
            callback_data='MenuSubscription|subscribe'
        )
        kb.button(
            text=text('profile:referral'),
            callback_data='MenuSubscription|referral'
        )
        kb.button(
            text=text('back:button'),
            callback_data='MenuSubscription|back'
        )

        kb.adjust(1, 1, 1, 1)
        return kb.as_markup()
