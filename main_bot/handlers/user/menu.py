from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.keyboards import keyboards
from main_bot.states.user import Support
from main_bot.utils.lang.language import text


async def choice(message: types.Message, state: FSMContext):
    await state.clear()

    menu = {
        text('reply_menu:posting'): {
            'cor': start_posting,
            'args': (message,)
        },
        text('reply_menu:story'): {
            'cor': start_stories,
            'args': (message,)
        },
        text('reply_menu:bots'): {
            'cor': start_bots,
            'args': (message,)
        },
        text('reply_menu:support'): {
            'cor': support,
            'args': (message, state,)
        },
        text('reply_menu:profile'): {
            'cor': profile,
            'args': (message,)
        },
        text('reply_menu:subscription'): {
            'cor': subscription,
            'args': (message,)
        },
        text('reply_menu:channels'): {
            'cor': show_channels,
            'args': (message,)
        },
    }

    cor, args = menu[message.text].values()
    await cor(*args)


async def start_posting(message: types.Message):
    await message.answer(
        text('start_post_text'),
        reply_markup=keyboards.posting_menu()
    )


async def start_stories(message: types.Message):
    await message.answer(
        text('start_stories_text'),
        reply_markup=keyboards.stories_menu()
    )


async def start_bots(message: types.Message):
    await message.answer(
        text('start_bots_text'),
        reply_markup=keyboards.bots_menu()
    )


async def support(message: types.Message, state: FSMContext):
    await message.answer(
        text('start_support_text'),
        reply_markup=keyboards.cancel(
            data="CancelSupport"
        )
    )
    await state.set_state(Support.message)


async def profile(message: types.Message):
    await message.answer(
        text('start_profile_text'),
        reply_markup=keyboards.profile_menu()
    )


async def subscription(message: types.Message):
    """Меню подписки с балансом, подпиской и реферальной системой"""
    from main_bot.database.db import db
    
    user = await db.get_user(user_id=message.chat.id)
    await message.answer(
        text("balance_text").format(user.balance),
        reply_markup=keyboards.subscription_menu(),
        parse_mode="HTML"
    )


async def show_channels(message: types.Message):
    """Показать список каналов пользователя"""
    from main_bot.database.db import db
    
    channels = await db.get_user_channels(
        user_id=message.chat.id,
        sort_by="posting"
    )
    await message.answer(
        text('channels_text'),
        reply_markup=keyboards.channels(
            channels=channels
        )
    )


def hand_add():
    router = Router()
    router.message.register(
        choice,
        F.text.in_(
            {
                # RU
                text('reply_menu:posting'),
                text('reply_menu:story'),
                text('reply_menu:bots'),
                text('reply_menu:support'),
                text('reply_menu:profile'),
                text('reply_menu:subscription'),
                text('reply_menu:channels'),
            }
        )
    )
    return router
