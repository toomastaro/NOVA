from aiogram import types, Router, F

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


async def show_timezone(message: types.Message):
    """Показать меню настройки часового пояса"""
    from main_bot.handlers.user.profile.settings import show_timezone as settings_timezone
    await settings_timezone(message)


async def show_folders(message: types.Message):
    """Показать меню папок"""
    from main_bot.handlers.user.profile.settings import show_folders as settings_folders
    await settings_folders(message)


async def show_subscribe(message: types.Message):
    await message.answer(
        text("subscribe_text"),
        reply_markup=keyboards.profile_sub_choice()
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
        "support_feedback": "📝 <b>Книга жалоб и предложений</b>\n\n"
"Здесь вы можете оставить идеи по улучшению сервиса или сообщить о проблеме.\n\n"
"❗️ Это не чат — одно сообщение рассматривается как один запрос.\nНужен новый вопрос → создайте новый тикет.\n\n"
"✍️ Напишите ваше сообщение:"

        reply_markup=keyboards.back(data='CancelSupport'),
        parse_mode="HTML"
    )
    await state.set_state(Support.message)


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
    return router
