from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.channel_bot_settings.model import ChannelBotSetting

from main_bot.database.db import db
from main_bot.handlers.user.bots.bot_settings.menu import show_channel_setting, show_captcha
from main_bot.states.user import Captcha
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.utils.schemas import Media, MessageOptionsCaptcha
from main_bot.utils.functions import answer_message


async def show_manage_captcha(message: types.Message,  state: FSMContext):
    data = await state.get_data()
    captcha = await db.channel_bot_captcha.get_captcha(
        message_id=data.get("captcha_id")
    )

    await message.answer(
        text("manage_captcha"),
        reply_markup=keyboards.manage_captcha(
            captcha=captcha
        )
    )


async def choice(call: types.CallbackQuery, state: FSMContext, db_obj: Database, channel_settings: ChannelBotSetting):
    temp = call.data.split('|')
    data = await state.get_data()
    await call.message.delete()

    if temp[1] in ["next", "back"]:
        channel_captcha_list = await db.channel_bot_captcha.get_all_captcha(
            chat_id=channel_settings.id
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channel_captcha(
                channel_captcha_list=channel_captcha_list,
                active_captcha=channel_settings.active_captcha_id,
                remover=int(temp[2])
            )
        )

    if temp[1] == "cancel":
        return await show_channel_setting(call.message, db_obj, state)

    if temp[1] == "add":
        await call.message.answer(
            text("input_captcha_message"),
            reply_markup=keyboards.back(
                data="AddCaptchaBack"
            )
        )
        return await state.set_state(Captcha.message)

    captcha_id = int(temp[2])
    await state.update_data(
        captcha_id=captcha_id
    )

    if temp[1] == "choice":
        if captcha_id == channel_settings.active_captcha_id:
            captcha_id = None

        await db.channel_bot_settings.update_channel_bot_setting(
            chat_id=data.get("chat_id"),
            active_captcha_id=captcha_id
        )
        channel_settings = await db.channel_bot_settings.get_channel_bot_setting(
            chat_id=data.get("chat_id"),
        )

        return await show_captcha(call.message, channel_settings, db_obj)

    if temp[1] == "change":
        await show_manage_captcha(call.message, state)


async def manage_hello_message(call: types.CallbackQuery, state: FSMContext, db_obj: Database):
    temp = call.data.split("|")
    data = await state.get_data()

    if temp[1] in ["cancel", "delete"]:
        if temp[1] == "delete":
            await db.channel_bot_captcha.delete_captcha(
                data.get("captcha_id")
            )

        cs = await db.channel_bot_settings.get_channel_bot_setting(data.get("chat_id"))

        await call.message.delete()
        return await show_captcha(call.message, cs, db_obj)

    captcha = await db.channel_bot_captcha.get_captcha(
        message_id=data.get("captcha_id")
    )

    if temp[1] == "delay":
        await call.message.delete()
        await call.message.answer(
            text("application:delay"),
            reply_markup=keyboards.choice_captcha_delay(
                current=captcha.delay
            )
        )

    if temp[1] == "change":
        await call.message.delete()

        msg = MessageOptionsCaptcha(**captcha.message)
        post_id = await answer_message(call.message, msg)
        await state.update_data(
            post_id=post_id.message_id,
            is_edit=True
        )

        await call.message.answer(
            text("edit_hello"),
            reply_markup=keyboards.manage_captcha_post(
                resize=msg.resize_markup
            )
        )


async def manage_hello_message_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()

    if temp[1] == "cancel":
        await state.update_data(
            is_edit=None
        )
        await call.bot.delete_message(call.from_user.id, data.get("post_id"))
        await call.message.answer("✅ Меню возвращено", reply_markup=keyboards.menu())

        await call.message.delete()
        return await show_manage_captcha(call.message, state)

    if temp[1] == "reply_buttons":
        await call.message.delete()
        await call.message.answer(
            text("manage:captcha:new:buttons"),
            reply_markup=keyboards.back(
                data="AddCaptchaBack"
            )
        )
        return await state.set_state(Captcha.buttons)

    if temp[1] == "resize":
        captcha = await db.channel_bot_captcha.get_captcha(
            message_id=data.get("captcha_id")
        )

        message_obj = MessageOptionsCaptcha(**captcha.message)
        if not message_obj.reply_markup:
            return await call.answer("Сначала добавьте кнопки!")

        message_obj.resize_markup = not message_obj.resize_markup
        message_obj.reply_markup = keyboards.captcha_kb(
            "\n".join("|".join(btn.text for btn in row) for row in message_obj.reply_markup.keyboard),
            message_obj.resize_markup
        )

        await db.channel_bot_captcha.update_captcha(
            captcha_id=captcha.id,
            return_obj=True,
            message=message_obj.model_dump()
        )

        await call.bot.delete_message(call.from_user.id, data.get("post_id"))
        post_id = await answer_message(call.message, message_obj)

        await state.update_data(
            post_id=post_id.message_id,
            is_edit=True
        )

        await call.message.delete()
        await call.message.answer(
            text("edit_hello"),
            reply_markup=keyboards.manage_captcha_post(
                resize=message_obj.resize_markup
            )
        )

    if temp[1] == "message":
        await call.message.delete()
        await call.message.answer(
            text("input_captcha_message"),
            reply_markup=keyboards.back(
                data="AddCaptchaBack"
            )
        )
        return await state.set_state(Captcha.message)


async def choice_hello_message_delay(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_manage_captcha(call.message, state)

    delay = int(temp[1])
    captcha = await db.channel_bot_captcha.update_captcha(
        captcha_id=data.get("captcha_id"),
        return_obj=True,
        delay=delay
    )

    await call.message.delete()
    await call.message.answer(
        text("application:delay"),
        reply_markup=keyboards.choice_captcha_delay(
            current=captcha.delay
        )
    )


async def back(call: types.CallbackQuery, state: FSMContext, db_obj: Database):
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)

    await call.message.delete()

    if data.get("is_edit"):
        captcha = await db.channel_bot_captcha.get_captcha(
            message_id=data.get("captcha_id")
        )
        message_obj = MessageOptionsCaptcha(**captcha.message)

        await call.message.answer(
            text("edit_hello"),
            reply_markup=keyboards.manage_captcha_post(
                resize=message_obj.resize_markup
            )
        )
    else:
        cs = await db.channel_bot_settings.get_channel_bot_setting(data.get("chat_id"))
        return await show_captcha(call.message, cs, db_obj)


async def get_message(message: types.Message, state: FSMContext, db_obj: Database):
    message_text_length = len(message.caption or message.text or "")
    if message_text_length > 1024:
        return await message.answer(
            text('error_length_text')
        )

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)
    if dump_message.get("reply_markup"):
        dump_message["reply_markup"] = None

    message_options = MessageOptionsCaptcha(**dump_message)
    if message_text_length:
        if message_options.text:
            message_options.text = message.html_text
        if message_options.caption:
            message_options.caption = message.html_text

    data = await state.get_data()

    if data.get("is_edit"):
        await db.channel_bot_captcha.update_captcha(
            captcha_id=data.get("captcha_id"),
            message=message_options.model_dump()
        )

        await message.bot.delete_message(message.from_user.id, data.get("post_id"))
        post_id = await answer_message(message, message_options)

        data.pop('post_id')
        await state.clear()
        await state.update_data(post_id=post_id.message_id, **data)

        return await message.answer(
            text("edit_hello"),
            reply_markup=keyboards.manage_captcha_post(
                resize=message_options.resize_markup
            )
        )

    else:
        await db.channel_bot_captcha.add_channel_captcha(
            channel_id=data.get("chat_id"),
            message=message_options.model_dump()
        )
        data = await state.get_data()

    await state.clear()
    await state.update_data(**data)

    await message.answer(text("success_add_captcha"))

    cs = await db.channel_bot_settings.get_channel_bot_setting(data.get("chat_id"))
    await show_captcha(message, cs, db_obj)


async def get_buttons(message: types.Message, state: FSMContext):
    data = await state.get_data()
    hello_obj = await db.channel_bot_captcha.get_captcha(
        message_id=data.get("captcha_id")
    )

    try:
        reply_markup = keyboards.captcha_kb(message.text, hello_obj.message["resize_markup"])
        r = await message.answer('...', reply_markup=reply_markup)
        await r.delete()
    except Exception as e:
        print(e)
        return await message.answer(
            text("error_input")
        )

    hello_message = MessageOptionsCaptcha(**hello_obj.message)
    hello_message.reply_markup = reply_markup

    await db.channel_bot_captcha.update_captcha(
        captcha_id=hello_obj.id,
        message=hello_message.model_dump()
    )

    await message.bot.delete_message(message.from_user.id, data.get("post_id"))
    post_id = await answer_message(message, hello_message)

    data.pop('post_id')
    await state.clear()
    await state.update_data(post_id=post_id.message_id, **data)

    await message.answer(
        text("edit_hello"),
        reply_markup=keyboards.manage_captcha_post(
            resize=hello_message.resize_markup
        )
    )


def get_router():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoiceCaptcha")
    router.callback_query.register(manage_hello_message, F.data.split("|")[0] == "ManageCaptcha")
    router.callback_query.register(choice_hello_message_delay, F.data.split("|")[0] == "ChoiceCaptchaDelay")
    router.callback_query.register(manage_hello_message_post, F.data.split("|")[0] == "ManagePostCaptcha")
    router.callback_query.register(back, F.data.split("|")[0] == "AddCaptchaBack")

    router.message.register(get_buttons, Captcha.buttons, F.text)
    router.message.register(get_message, Captcha.message, F.text | F.photo | F.video | F.animation)

    return router
