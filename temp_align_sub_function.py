async def show_align_sub_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню выравнивания подписки"""
    from main_bot.database.db import db
    from main_bot.keyboards import keyboards
    from main_bot.utils.lang.language import text
    
    user = await db.get_user(user_id=call.from_user.id)
    sub_objects = await db.get_subscribe_channels(
        user_id=user.id
    )

    if len(sub_objects) < 2:
        return await call.answer(
            text("error_align_sub"),
            show_alert=True
        )

    await state.update_data(
        align_chosen=[]
    )

    await call.message.answer(
        text("align_sub"),
        reply_markup=keyboards.align_sub(
            sub_objects=sub_objects,
            chosen=[]
        )
    )
