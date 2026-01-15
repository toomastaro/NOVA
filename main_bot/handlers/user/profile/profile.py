"""
Модуль профиля пользователя.

Содержит:
- Главное меню профиля
- Настройки аккаунта (часовой пояс)
- Списки каналов и ботов
- Подписку и реферальную программу
"""

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.database.db_types import FolderType
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.handlers.user.profile.report_settings import show_report_settings_menu
from utils.error_handler import safe_handler
from main_bot.utils.user_settings import get_user_view_mode


@safe_handler(
    "Профиль: выбор"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice(call: types.CallbackQuery, user: User, state: FSMContext):
    """Маршрутизатор меню профиля."""
    temp = call.data.split("|")
    await call.message.delete()

    menu = {
        "timezone": {
            "cor": show_timezone,
            "args": (
                call.message,
                state,
            ),
        },
        "folders": {"cor": show_folders, "args": (call.message,)},
        "report_settings": {"cor": show_report_settings_menu, "args": (call,)},
        "channels": {"cor": show_channels, "args": (call.message, state)},
        "bots": {"cor": show_bots, "args": (call.message,)},
        "support": {
            "cor": show_support,
            "args": (
                call.message,
                state,
            ),
        },
        "back": {"cor": back_to_main, "args": (call.message,)},
    }

    cor, args = menu[temp[1]].values()
    await cor(*args)


@safe_handler(
    "Профиль: баланс"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_balance(message: types.Message, user: User):
    await message.answer(
        text("balance_text").format(user.balance),
        reply_markup=keyboards.profile_balance(),
    )


@safe_handler(
    "Профиль: каналы"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_channels(message: types.Message, state: FSMContext):
    """Показать список каналов пользователя (перенесено из Posting)"""
    data = await state.get_data()
    view_mode = data.get("channels_view_mode")
    if not view_mode:
        view_mode = await get_user_view_mode(message.chat.id)
    current_folder_id = data.get("channels_folder_id")

    folders = await db.user_folder.get_folders(
        user_id=message.chat.id, folder_type=FolderType.CHANNEL
    )
    
    if current_folder_id:
        folder = await db.user_folder.get_folder_by_id(current_folder_id)
        channels = await db.channel.get_user_channels(
            user_id=message.chat.id, 
            from_array=[int(c) for c in folder.content] if folder and folder.content else [],
            sort_by="posting"
        )
    else:
        if view_mode == "folders":
            channels = await db.channel.get_user_channels_without_folders(user_id=message.chat.id)
        else:
            channels = await db.channel.get_user_channels(
                user_id=message.chat.id, sort_by="posting"
            )

    await state.update_data(channels_view_mode=view_mode)

    await message.answer(
        text("channels_text"),
        reply_markup=keyboards.channels(
            channels=channels,
            folders=folders,
            view_mode=view_mode,
            is_inside_folder=bool(current_folder_id),
        ),
    )


@safe_handler(
    "Профиль: боты"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_bots(message: types.Message):
    """Показать список ботов пользователя (перенесено из Bots/Mailing)"""
    bots = await db.user_bot.get_user_bots(user_id=message.chat.id, sort_by=True)
    await message.answer(
        text("bots_text"),
        reply_markup=keyboards.choice_bots(
            bots=bots,
        ),
    )


@safe_handler(
    "Профиль: часовой пояс"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_timezone(message: types.Message, state: FSMContext):
    """Показать меню настройки часового пояса"""
    from main_bot.database.db import db
    from datetime import timedelta, datetime
    from main_bot.states.user import Setting

    user = await db.user.get_user(user_id=message.chat.id)
    delta = timedelta(hours=abs(user.timezone))

    if user.timezone > 0:
        timezone = datetime.utcnow() + delta
    else:
        timezone = datetime.utcnow() - delta

    await message.answer(
        text("input_timezone").format(
            f"+{user.timezone}" if user.timezone > 0 else user.timezone,
            timezone.strftime("%H:%M"),
        ),
        reply_markup=keyboards.back(data="InputTimezoneCancel"),
    )
    await state.set_state(Setting.input_timezone)


@safe_handler(
    "Профиль: папки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_folders(message: types.Message):
    """Показать меню папок"""
    from main_bot.handlers.user.profile.settings import show_folders as settings_folders

    await settings_folders(message)


@safe_handler(
    "Профиль: подписка"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_subscribe(message: types.Message, state: FSMContext = None):
    """Показать выбор каналов для подписки (без промежуточного меню)"""
    from main_bot.handlers.user.profile.subscribe import get_subscribe_list_resources

    service = "subscribe"
    object_type = "channels"
    cor = db.channel.get_user_channels

    # Получаем список каналов пользователя
    user = await db.user.get_user(user_id=message.chat.id)
    objects = await cor(user_id=user.id, limit=10, sort_by=service)

    # Сохраняем данные в state для следующих шагов
    if state:
        await state.update_data(
            service=service,
            object_type=object_type,
            # cor не сохраняем в state
        )

    await message.answer(
        text("subscribe_text:channels").format(
            get_subscribe_list_resources(
                objects=objects, object_type=object_type, sort_by=service
            )
        ),
        reply_markup=keyboards.choice_period(service=service),
    )


@safe_handler(
    "Профиль: настройки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_setting(message: types.Message):
    await message.answer(text("setting_text"), reply_markup=keyboards.profile_setting())


@safe_handler(
    "Профиль: реферальная система"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_referral(message: types.Message, user: User):
    referral_count = await db.user.get_count_user_referral(user_id=user.id)

    await message.answer(
        text("referral_text").format(
            referral_count,
            0,
            user.referral_earned,
            text("referral_url").format((await message.bot.get_me()).username, user.id),
        ),
        reply_markup=keyboards.back(data="Referral|back"),
    )


@safe_handler(
    "Профиль: поддержка"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_support(message: types.Message, state: FSMContext):
    """Показать информацию о поддержке"""
    from main_bot.states.user import Support

    await message.answer(
        "📝 <b>Книга жалоб и предложений</b>\n\n"
        "Здесь вы можете оставить свои предложения по улучшению сервиса "
        "или сообщить о проблемах.\n\n"
        "Напишите ваше сообщение:",
        reply_markup=keyboards.back(data="CancelSupport"),
        parse_mode="HTML",
    )
    await state.set_state(Support.message)


@safe_handler(
    "Профиль: меню подписки"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def subscription_menu_choice(
    call: types.CallbackQuery, user: User, state: FSMContext
):
    """Обработчик выбора пунктов меню подписки"""
    temp = call.data.split("|")

    if temp[1] == "align_sub":
        # Показать меню выравнивания подписки
        await call.message.delete()

        # Получаем все каналы пользователя
        channels = await db.channel.get_user_channels(user_id=user.id)

        if not channels:
            return await call.message.answer(
                text("error_subscription_required"),
                reply_markup=keyboards.subscription_menu(),
            )

        await state.update_data(align_chosen=[])

        # Форматируем список каналов с датами подписки
        from datetime import datetime
        import time

        channels_info = []
        for ch in channels:
            if ch.subscribe and ch.subscribe > int(time.time()):
                sub_date = datetime.fromtimestamp(ch.subscribe).strftime("%d.%m.%Y")
                channels_info.append(f"📺 {ch.title} — до {sub_date}")
            else:
                channels_info.append(f"📺 {ch.title} — нет подписки")

        channels_list = "\n".join(channels_info)

        await call.message.answer(
            f"{text('align_sub')}\n\n<blockquote>{channels_list}</blockquote>",
            reply_markup=keyboards.align_sub(
                sub_objects=channels, chosen=[], remover=0
            ),
            parse_mode="HTML",
        )

    elif temp[1] == "transfer_sub":
        # Показать меню переноса подписки
        from main_bot.handlers.user.profile.transfer_subscription import (
            show_transfer_sub_menu,
        )

        # Проверка наличия каналов
        channels = await db.channel.get_user_channels(user_id=user.id)
        if not channels:
            return await call.message.answer(
                text("error_subscription_required"),
                reply_markup=keyboards.subscription_menu(),
            )

        await call.message.delete()
        await show_transfer_sub_menu(call, state)

    elif temp[1] == "top_up":
        # Пополнение баланса
        from main_bot.handlers.user.profile.balance import show_top_up

        await call.message.delete()
        await show_top_up(call.message, state)

    elif temp[1] == "subscribe":
        # Подписка на каналы
        await call.message.delete()
        await show_subscribe(call.message, state)

    elif temp[1] == "referral":
        # Реферальная программа
        await call.message.delete()
        await show_referral(call.message, user)

    elif temp[1] == "info":
        # Информация о подписке
        await call.message.delete()
        await call.message.answer(
            text("info:menu"), reply_markup=keyboards.info_menu(), parse_mode="HTML"
        )

    elif temp[1] == "back":
        # Возврат в главное меню
        await call.message.delete()
        await back_to_main(call.message)


@safe_handler(
    "Профиль: возврат в главное меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    from main_bot.keyboards.common import Reply

    await message.answer("Главное меню", reply_markup=Reply.menu())


@safe_handler(
    "Профиль: выбор в инфо-меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def info_menu_choice(call: types.CallbackQuery, user: User):
    temp = call.data.split("|")

    if temp[1] == "back":
        # Возврат в меню подписки
        await call.message.delete()
        await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML",
        )


def get_router():
    """Регистрация роутеров профиля."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuProfile")
    router.callback_query.register(
        subscription_menu_choice, F.data.split("|")[0] == "MenuSubscription"
    )
    router.callback_query.register(info_menu_choice, F.data.split("|")[0] == "InfoMenu")
    return router
