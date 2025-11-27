from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.keyboards.keyboards import keyboards
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
            }
        )
    )
    return router
