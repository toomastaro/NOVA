from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from main_bot.database.db import db
from main_bot.keyboards.profile import InlineProfile
from main_bot.utils.lang.language import text


class ReportSettingsStates(StatesGroup):
    input_text = State()


async def show_report_settings_menu(call: types.CallbackQuery):
    """
    Показывает главное меню настроек отчетов.
    """
    user = await db.get_user(call.from_user.id)
    
    await call.message.answer(
        text('report_settings_text'),
        reply_markup=InlineProfile.report_settings_menu(
            cpm_active=user.cpm_signature_active,
            exchange_active=user.exchange_signature_active,
            referral_active=user.referral_signature_active
        )
    )


async def show_specific_setting(call: types.CallbackQuery, setting_type: str):
    """
    Показывает настройки конкретной подписи (CPM/Exchange/Referral).
    """
    user = await db.get_user(call.from_user.id)
    
    is_active = False
    current_text = ""
    title_key = ""
    default_key = ""
    
    if setting_type == 'cpm':
        is_active = user.cpm_signature_active
        current_text = user.cpm_signature_text or text('default:cpm_signature')
        title_key = 'report:cpm:title'
        default_key = 'default:cpm_signature'
    elif setting_type == 'exchange':
        is_active = user.exchange_signature_active
        current_text = user.exchange_signature_text or text('default:exchange_signature')
        title_key = 'report:exchange:title'
        default_key = 'default:exchange_signature'
    elif setting_type == 'referral':
        is_active = user.referral_signature_active
        current_text = user.referral_signature_text or text('default:referral_signature')
        title_key = 'report:referral:title'
        default_key = 'default:referral_signature'
        
    status = text('on') if is_active else text('off')
    
    await call.message.edit_text(
        text(title_key).format(status, current_text),
        reply_markup=InlineProfile.report_setting_item(setting_type, is_active),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def process_toggle(call: types.CallbackQuery):
    """
    Переключает состояние подписи (Вкл/Выкл).
    """
    setting_type = call.data.split('|')[2]
    user_id = call.from_user.id
    user = await db.get_user(user_id)
    
    new_state = False
    
    if setting_type == 'cpm':
        new_state = not user.cpm_signature_active
        await db.update_user(user_id=user_id, cpm_signature_active=new_state, return_obj=False)
    elif setting_type == 'exchange':
        new_state = not user.exchange_signature_active
        await db.update_user(user_id=user_id, exchange_signature_active=new_state, return_obj=False)
    elif setting_type == 'referral':
        new_state = not user.referral_signature_active
        await db.update_user(user_id=user_id, referral_signature_active=new_state, return_obj=False)
        
    await show_specific_setting(call, setting_type)


async def start_edit_text(call: types.CallbackQuery, state: FSMContext):
    """
    Начинает редактирование текста подписи.
    """
    setting_type = call.data.split('|')[2]
    await state.update_data(editing_setting_type=setting_type)
    
    await call.message.edit_text(
        text('report:input_text'),
        reply_markup=None # Можно добавить кнопку отмены
    )
    await state.set_state(ReportSettingsStates.input_text)


async def finish_edit_text(message: types.Message, state: FSMContext):
    """
    Завершает редактирование текста.
    """
    data = await state.get_data()
    setting_type = data.get('editing_setting_type')
    new_text = message.text # Или message.html_text если нужна разметка? Лучше html_text, но aiogram 3.x передаёт raw text, надо самому форматировать или брать html
    # Обычно берут message.html_text если поддерживается или форматируют сами. 
    # В данном проекте похоже используют простой текст. Но пользователь просил "с эмоджи и хтмл форматированием".
    # aiogram 3 Message object has `html_text` property if parsing enabled? No, usually helpers.
    # We will use message.html_text if available, or just message.text if parse_mode is causing issues. 
    # Let's assume message.html_text is available via property or we fetch raw.
    # Actually, let's just use message.html_text (user logic usually supports it).
    
    # Check if `message.html_text` works?
    try:
        content = message.html_text
    except AttributeError:
        # Fallback if html_text not available
        content = message.text

    if not content:
        content = message.caption
        
    if not content:
        await message.answer("❌ Текст не найден")
        return

    user_id = message.from_user.id
    
    if setting_type == 'cpm':
        await db.update_user(user_id=user_id, cpm_signature_text=content, return_obj=False)
    elif setting_type == 'exchange':
        await db.update_user(user_id=user_id, exchange_signature_text=content, return_obj=False)
    elif setting_type == 'referral':
        await db.update_user(user_id=user_id, referral_signature_text=content, return_obj=False)
        
    await message.answer(text('report:text_updated'))
    
    # Вернуться в меню настройки
    # Для этого нам нужен call... но у нас message.
    # Мы можем отправить новое сообщение с меню.
    
    # Имитируем вызов show_specific_setting, но у нас нет callbackQuery с message для edit.
    # Поэтому просто отправляем новое сообщение.
    
    user = await db.get_user(user_id)
    
    # Copy-paste logic from show_specific_setting but for message answer
    is_active = False
    current_text = ""
    title_key = ""
    
    if setting_type == 'cpm':
        is_active = user.cpm_signature_active
        current_text = user.cpm_signature_text or text('default:cpm_signature')
        title_key = 'report:cpm:title'
    elif setting_type == 'exchange':
        is_active = user.exchange_signature_active
        current_text = user.exchange_signature_text or text('default:exchange_signature')
        title_key = 'report:exchange:title'
    elif setting_type == 'referral':
        is_active = user.referral_signature_active
        current_text = user.referral_signature_text or text('default:referral_signature')
        title_key = 'report:referral:title'
        
    status = text('on') if is_active else text('off')
    
    await message.answer(
        text(title_key).format(status, current_text),
        reply_markup=InlineProfile.report_setting_item(setting_type, is_active),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await state.clear()


async def back_to_main_settings(call: types.CallbackQuery):
    """
    Возврат в главное меню настроек (из отчетов).
    """
    from main_bot.handlers.user.profile.settings import choice
    # Мы не можем вызвать choice напрямую так как ему нужен split array.
    # Лучше просто вызвать отображение меню настроек.
    # В settings.py нет функции show_settings_menu, там просто router, 
    # а отображение идет через InlineProfile.profile_setting() обычно в profile.py
    
    # Посмотрим profile.py
    # Там profile_setting() возвращает клаву.
    # Сообщение текста 'setting_text'.
    
    await call.message.edit_text(
        text('setting_text'),
        reply_markup=InlineProfile.profile_setting()
    )


async def router_choice(call: types.CallbackQuery):
    action = call.data.split('|')[1]
    if action == 'cpm':
        await show_specific_setting(call, 'cpm')
    elif action == 'exchange':
        await show_specific_setting(call, 'exchange')
    elif action == 'referral':
        await show_specific_setting(call, 'referral')
    elif action == 'back':
        await show_report_settings_menu(call)
    elif action == 'toggle':
        await process_toggle(call)
    elif action == 'edit':
        # Need state
        pass 


def hand_add():
    router = Router()
    
    # Handlers
    
    # Navigate to specific setting
    router.callback_query.register(
        lambda c: show_specific_setting(c, 'cpm'), 
        F.data == "ReportSetting|cpm"
    )
    router.callback_query.register(
        lambda c: show_specific_setting(c, 'exchange'), 
        F.data == "ReportSetting|exchange"
    )
    router.callback_query.register(
        lambda c: show_specific_setting(c, 'referral'), 
        F.data == "ReportSetting|referral"
    )
    
    # Toggle
    router.callback_query.register(process_toggle, F.data.startswith("ReportSetting|toggle|"))
    
    # Edit Text Start
    router.callback_query.register(start_edit_text, F.data.startswith("ReportSetting|edit|"))
    
    # Back to Report Menu (from Item)
    router.callback_query.register(show_report_settings_menu, F.data == "ReportSetting|back")
    
    # Back to Main Settings (from Report Menu)
    router.callback_query.register(back_to_main_settings, F.data == "Setting|reports_back")
    
    # Process text input
    router.message.register(finish_edit_text, ReportSettingsStates.input_text)
    
    return router
