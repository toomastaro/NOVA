from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text


async def choice(call: types.CallbackQuery, user: User, state: FSMContext):
    temp = call.data.split('|')
    await call.message.delete()

    menu = {
        'timezone': {
            'cor': show_timezone,
            'args': (call.message, state,)
        },
        'folders': {
            'cor': show_folders,
            'args': (call.message,)
        },
        'support': {
            'cor': show_support,
            'args': (call.message, state,)
        },
        'back': {
            'cor': back_to_main,
            'args': (call.message,)
        },
    }

    cor, args = menu[temp[1]].values()
    await cor(*args)


async def show_balance(message: types.Message, user: User):
    await message.answer(
        text("balance_text").format(
            user.balance
        ),
        reply_markup=keyboards.profile_balance()
    )


async def show_timezone(message: types.Message, state: FSMContext):
    """Показать меню настройки часового пояса"""
    from main_bot.database.db import db
    from datetime import timedelta, datetime
    from main_bot.states.user import Setting
    
    user = await db.get_user(user_id=message.chat.id)
    delta = timedelta(hours=abs(user.timezone))

    if user.timezone > 0:
        timezone = datetime.utcnow() + delta
    else:
        timezone = datetime.utcnow() - delta

    await message.answer(
        text('input_timezone').format(
            f"+{user.timezone}" if user.timezone > 0 else user.timezone,
            timezone.strftime('%H:%M')
        ),
        reply_markup=keyboards.back(
            data='InputTimezoneCancel'
        )
    )
    await state.set_state(Setting.input_timezone)


async def show_folders(message: types.Message):
    """Показать меню папок"""
    from main_bot.handlers.user.profile.settings import show_folders as settings_folders
    await settings_folders(message)


async def show_subscribe(message: types.Message, state: FSMContext = None):
    """Показать выбор каналов для подписки (без промежуточного меню)"""
    from main_bot.handlers.user.profile.subscribe import get_subscribe_list_resources
    from aiogram.fsm.context import FSMContext
    
    service = "subscribe"
    object_type = 'channels'
    cor = db.get_user_channels
    
    # Получаем список каналов пользователя
    user = await db.get_user(user_id=message.chat.id)
    objects = await cor(
        user_id=user.id,
        limit=10,
        sort_by=service
    )
    
    # Сохраняем данные в state для следующих шагов
    if state:
        await state.update_data(
            service=service,
            object_type=object_type,
            cor=cor,
        )
    
    await message.answer(
        text('subscribe_text:channels').format(
            get_subscribe_list_resources(
                objects=objects,
                object_type=object_type,
                sort_by=service
            )
        ),
        reply_markup=keyboards.choice_period(
            service=service
        )
    )


async def show_setting(message: types.Message):
    await message.answer(
        text("setting_text"),
        reply_markup=keyboards.profile_setting()
    )


async def show_referral(message: types.Message, user: User):
    referral_count = await db.get_count_user_referral(
        user_id=user.id
    )

    await message.answer(
        text('referral_text').format(
            referral_count,
            0,
            user.referral_earned,
            text('referral_url').format(
                (await message.bot.get_me()).username,
                user.id
            )
        ),
        reply_markup=keyboards.back(
            data='Referral|back'
        )
    )


async def show_support(message: types.Message, state: FSMContext):
    """Показать информацию о поддержке"""
    from main_bot.states.user import Support
    await message.answer(
        "📝 <b>Книга жалоб и предложений</b>\n\n"
        "Здесь вы можете оставить свои предложения по улучшению сервиса "
        "или сообщить о проблемах.\n\n"
        "Напишите ваше сообщение:",
        reply_markup=keyboards.back(data='CancelSupport'),
        parse_mode="HTML"
    )
    await state.set_state(Support.message)


async def subscription_menu_choice(call: types.CallbackQuery, user: User, state: FSMContext):
    """Обработчик выбора пунктов меню подписки"""
    temp = call.data.split('|')
    
    if temp[1] == 'align_sub':
        # Показать меню выравнивания подписки
        await call.message.delete()
        
        # Получаем все каналы пользователя
        channels = await db.get_user_channels(user_id=user.id)
        
        if not channels:
            return await call.message.answer(
                text("error_no_channels"),
                reply_markup=keyboards.subscription_menu()
            )
        
        await state.update_data(align_chosen=[])
        
        await call.message.answer(
            text("align_sub"),
            reply_markup=keyboards.align_sub(
                sub_objects=channels,
                chosen=[],
                remover=0
            )
        )
    
    elif temp[1] == 'transfer_sub':
        # Показать меню переноса подписки
        from main_bot.handlers.user.profile.transfer_subscription import show_transfer_sub_menu
        await call.message.delete()
        await show_transfer_sub_menu(call, state)
    
    elif temp[1] == 'top_up':
        # Пополнение баланса
        from main_bot.handlers.user.profile.payment import show_payment
        await call.message.delete()
        await show_payment(call.message, user)
    
    elif temp[1] == 'subscribe':
        # Подписка на каналы
        await call.message.delete()
        await show_subscribe(call.message, state)
    
    elif temp[1] == 'referral':
        # Реферальная программа
        await call.message.delete()
        await show_referral(call.message, user)
    
    elif temp[1] == 'info':
        # Информация о подписке
        await call.message.delete()
        await call.message.answer(
            text("subscription_info"),
            reply_markup=keyboards.back(data='MenuSubscription|back')
        )
    
    elif temp[1] == 'back':
        # Возврат в профиль
        await call.message.delete()
        await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML"
        )


async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    from main_bot.keyboards.common import Reply
    await message.answer(
        "Главное меню",
        reply_markup=Reply.menu()
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuProfile")
    router.callback_query.register(subscription_menu_choice, F.data.split("|")[0] == "MenuSubscription")
    return router
