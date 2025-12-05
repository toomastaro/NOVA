from aiogram import types, Router, F

from main_bot.handlers.user.menu import profile


async def choice(call: types.CallbackQuery):
    temp = call.data.split('|')
    await call.message.delete()

    if temp[1] == 'back':
        # Возврат в меню подписки с информацией о балансе
        from main_bot.database.db import db
        from main_bot.keyboards import keyboards
        from main_bot.utils.lang.language import text
        
        user = await db.get_user(user_id=call.from_user.id)
        await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML"
        )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Referral")
    return router
