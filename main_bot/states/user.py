from aiogram.fsm.state import State, StatesGroup


class Support(StatesGroup):
    message = State()


class Balance(StatesGroup):
    pay_stars = State()
    input_amount = State()
    input_promo = State()


class Subscribe(StatesGroup):
    pay_stars = State()
    input_promo = State()


class Setting(StatesGroup):
    input_timezone = State()


class Folder(StatesGroup):
    input_name = State()


class Posting(StatesGroup):
    input_send_time = State()
    input_value = State()
    input_message = State()


class Stories(StatesGroup):
    input_send_time = State()
    input_value = State()
    input_message = State()


class AddHide(StatesGroup):
    button_name = State()
    not_member_text = State()
    for_member_text = State()


class Bots(StatesGroup):
    input_send_time = State()
    input_value = State()
    input_message = State()


class AddBot(StatesGroup):
    import_file = State()
    update_token = State()
    input_token = State()


class Answer(StatesGroup):
    message = State()
    keyword = State()


class Hello(StatesGroup):
    buttons = State()
    message = State()


class Captcha(StatesGroup):
    buttons = State()
    message = State()


class Cleaner(StatesGroup):
    period = State()


class Bye(StatesGroup):
    message = State()


class Application(StatesGroup):
    part = State()
