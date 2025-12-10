from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.keyboards import keyboards
from main_bot.states.user import Support
from main_bot.utils.lang.language import text
from main_bot.utils.logger import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Menu Choice")
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

    if message.text in menu:
        cor, args = menu[message.text].values()
        await cor(*args)
    else:
        logger.warning(f"Unknown menu command: {message.text}")


@safe_handler("Start Posting Menu")
async def start_posting(message: types.Message):
    await message.answer(
        text('start_post_text'),
        reply_markup=keyboards.posting_menu()
    )


@safe_handler("Start Stories Menu")
async def start_stories(message: types.Message):
    await message.answer(
        text('start_stories_text'),
        reply_markup=keyboards.stories_menu()
    )


@safe_handler("Start Bots Menu")
async def start_bots(message: types.Message):
    await message.answer(
        text('start_bots_text'),
        reply_markup=keyboards.bots_menu()
    )


@safe_handler("Start Support")
async def support(message: types.Message, state: FSMContext):
    await message.answer(
        text('start_support_text'),
        reply_markup=keyboards.cancel(
            data="CancelSupport"
        )
    )
    await state.set_state(Support.message)


@safe_handler("Start Profile")
async def profile(message: types.Message):
    await message.answer(
        text('start_profile_text'),
        reply_markup=keyboards.profile_menu()
    )


@safe_handler("Start Subscription")
async def subscription(message: types.Message):
    """Меню подписки с балансом, подпиской и реферальной системой"""
    from main_bot.database.db import db
    
    user = await db.get_user(user_id=message.chat.id)
    if not user:
        await db.add_user(
            id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )
        user = await db.get_user(user_id=message.chat.id)
    await message.answer(
        text("balance_text").format(user.balance),
        reply_markup=keyboards.subscription_menu(),
        parse_mode="HTML"
    )


@safe_handler("Show Channels")
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
