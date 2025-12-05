from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from config import Config
from main_bot.keyboards import keyboards
from main_bot.states.user import Support
from main_bot.utils.lang.language import text


async def support_back(call: types.CallbackQuery, state: FSMContext):
    await state.clear()

    await call.message.delete()
    await call.message.answer(
        text=text("start_text"),
        reply_markup=keyboards.menu()
    )


async def get_user_message(message: types.Message, state: FSMContext):
    if message.photo:
        await message.bot.send_photo(
            photo=message.photo[-1].file_id,
            chat_id=Config.ADMIN_SUPPORT,
            caption=text("user_support_msg").format(
                message.caption,
                message.from_user.full_name,
                message.from_user.username,
                message.from_user.id
            )
        )
    else:
        await message.bot.send_message(
            chat_id=Config.ADMIN_SUPPORT,
            text=text("user_support_msg").format(
                message.text,
                message.from_user.full_name,
                message.from_user.username,
                message.from_user.id
            )
        )

    await state.clear()
    await message.answer(
        text("success_msg_support"),
        reply_markup=keyboards.back(
            data="CancelSupport"
        )
    )


async def get_support_message(message: types.Message):
    try:
        user_id = message.reply_to_message.caption.split('ID: ')[1] \
            if message.reply_to_message.caption else message.reply_to_message.text.split('ID: ')[1]
    except Exception as e:
        return print(e)

    if message.photo:
        await message.bot.send_photo(
            photo=message.photo[-1].file_id,
            chat_id=user_id,
            caption=text("support_answer").format(
                message.caption
            )
        )
    else:
        await message.bot.send_message(
            chat_id=user_id,
            text=text("support_answer").format(
                message.text
            )
        )


def hand_add():
    router = Router()
    router.message.register(get_user_message, Support.message, F.text | F.photo)
    router.message.register(get_support_message, (F.chat.id == Config.ADMIN_SUPPORT) & (F.text | F.photo))
    router.callback_query.register(support_back, F.data.split("|")[0] == "CancelSupport")
    return router
