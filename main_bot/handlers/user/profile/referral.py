from aiogram import types, Router, F

from main_bot.handlers.user.menu import profile


async def choice(call: types.CallbackQuery):
    temp = call.data.split('|')
    await call.message.delete()

    if temp[1] == 'back':
        # Возврат в меню подписки
        from main_bot.keyboards import keyboards
        await call.message.answer(
            "💳 <b>Подписка</b>\n\nВ этом разделе вы можете управлять балансом, подписками и реферальной системой.",
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML"
        )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Referral")
    return router
