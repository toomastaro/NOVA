"""
Модуль оформления подписок на каналы и ботов.
"""

from datetime import datetime
import logging

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from httpx import AsyncClient

from config import Config
from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.utils.error_handler import safe_handler
from main_bot.utils.user_settings import get_user_view_mode, set_user_view_mode

logger = logging.getLogger(__name__)


def get_subscribe_list_resources(objects: list, object_type: str, sort_by: str) -> str:
    """Формирует текстовый список ресурсов для подписки."""
    if not objects:
        return text(f"not_found_{object_type}")

    empty_text = ""
    for obj in objects:
        sub_text = text("subscribe_not_found")

        if object_type == "bots":
            if obj.subscribe:
                sub_text = text("subscribe_date_note").format(
                    datetime.fromtimestamp(obj.subscribe).strftime("%d.%m.%Y %H:%M")
                )
        else:
            sub_value = obj.subscribe
            if sub_value:
                sub_text = text("subscribe_date_note").format(
                    datetime.fromtimestamp(sub_value).strftime("%d.%m.%Y %H:%M")
                )

        obj_text = text("resource_title").format(obj.title)
        empty_text += obj_text + sub_text + "\n"

    return empty_text


async def get_pay_info_text(state: FSMContext, user: User) -> str:
    """Формирует текст информации о платеже."""
    data = await state.get_data()

    total_days = data.get("total_days")
    method = data.get("method")
    total_price = data.get("total_price")

    try:
        async with AsyncClient() as client:
            res = await client.get("https://api.coinbase.com/v2/prices/USD-RUB/spot")
            usd_rate = float(res.json().get("data").get("amount", 100))
    except Exception as e:
        logger.error(f"Error fetching USD rate: {e}")
        usd_rate = 100

    total_price_usd = round(total_price / usd_rate, 2)
    total_price_stars = int(total_price / 1.2)  # Курс: 1 Star = 1.2₽

    total_count_resources = data.get("total_count_resources")
    chosen = data.get("chosen")
    service = data.get("service")
    # cor = data.get('cor')

    # Определяем функцию динамически (для pay_info)
    # Здесь нужно определить object_type, но он не передан явно в data для всех кейсов
    # Попробуем определить по наличию ключа в data или по умолчанию channels
    object_type = data.get("object_type", "channels")

    if object_type == "bots":
        cor = db.user_bot.get_user_bots
    else:
        cor = db.channel.get_user_channels

    objects = await cor(user_id=user.id, limit=10, sort_by=service)

    # Форматируем список каналов с их названиями
    channels_list = "\n".join(
        f"📺 {obj.title}" for obj in objects if obj.id in chosen[:10]
    )

    # Форматируем способ оплаты (если выбран)
    method_text = (
        text("pay:info:method").format(text(f"payment:method:{method.lower()}"))
        if method
        else ""
    )

    return text("pay:info").format(
        channels_list,  # Список каналов
        total_price,  # Цена в рублях
        total_price_usd,  # Цена в USD
        total_price_stars,  # Цена в звездах
        total_days,  # Длительность
        total_count_resources,  # Количество каналов
        method_text,  # Способ оплаты
    )


@safe_handler("Subscribe Choice")
async def choice(call: types.CallbackQuery, state: FSMContext, user: User):
    """Маршрутизатор выбора типа подписки (каналы/боты)."""
    temp = call.data.split("|")
    await call.message.delete()

    if temp[1] == "cancel":
        # Возврат в меню подписки с информацией о балансе
        return await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML",
        )

    service = "subscribe"
    message_text = text("subscribe_text:{}".format(temp[1]))

    if temp[1] == "bots":
        cor = db.user_bot.get_user_bots
        object_type = "bots"
    else:
        cor = db.channel.get_user_channels
        object_type = "channels"

    objects = await cor(user_id=user.id, limit=10, sort_by=service)
    await state.update_data(
        service=service,
        object_type=object_type,
        # cor не сохраняем в state
    )
    await call.message.answer(
        message_text.format(
            get_subscribe_list_resources(
                objects=objects, object_type=object_type, sort_by=service
            )
        ),
        reply_markup=keyboards.choice_period(service=service),
    )


@safe_handler("Subscribe Choice Period")
async def choice_period(call: types.CallbackQuery, state: FSMContext, user: User):
    """Выбор периода подписки."""
    temp = call.data.split("|")

    if temp[1] == "back":
        await call.message.delete()
        # Возврат в меню подписки с информацией о балансе
        return await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML",
        )

    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    # cor = data.get('cor')  <- Получение функции из state вызывает ошибку
    service = data.get("service")
    object_type = data.get("object_type")

    # Защита от потери данных в state
    if not object_type:
        object_type = "channels"

    # Определяем функцию динамически
    if object_type == "bots":
        cor = db.user_bot.get_user_bots
    else:
        cor = db.channel.get_user_channels

    objects = await cor(user_id=user.id, sort_by=service)
    if not objects:
        return await call.answer(text(f"not_found_{object_type}"), show_alert=True)

    await state.update_data(tariff_id=int(temp[1]), chosen=[])

    # Получаем режим просмотра и папки
    view_mode = await get_user_view_mode(call.from_user.id)
    folders = []

    if view_mode == "folders":
        folders = await db.user_folder.get_folders(user_id=user.id)
        # Если режим папок, загружаем только каналы без папок (если это каналы)
        if object_type == "channels":
            objects = await db.channel.get_user_channels_without_folders(
                user_id=user.id
            )
        # Для ботов пока нет папок, грузим всех (или если будет поддержка)
        # else objects (bots) already processed normally because folders logic might not apply fully to bots yet
        # But generic keyboard handles it.

    await call.message.edit_text(
        text(f"subscribe:chosen:{object_type}").format(""),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=[],
            folders=folders,
            data="ChoiceResourceSubscribe",
            view_mode=view_mode,
        ),
    )


@safe_handler("Subscribe Choice Object")
async def choice_object_subscribe(
    call: types.CallbackQuery, state: FSMContext, user: User
):
    """Выбор конкретных каналов/ботов для подписки."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    service = data.get("service")
    object_type = data.get("object_type")
    chosen = data.get("chosen", [])

    # Защита от потери данных
    if not service:
        service = "subscribe"
    if not object_type:
        object_type = "channels"

    tariff_id = data.get("tariff_id")
    if tariff_id is None:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    # Helpers
    if object_type == "bots":
        cor = db.user_bot.get_user_bots
    else:
        cor = db.channel.get_user_channels

    # SWITCH VIEW
    if temp[1] == "switch_view":
        current_view = await get_user_view_mode(call.from_user.id)
        new_view = "channels" if current_view == "folders" else "folders"
        await set_user_view_mode(call.from_user.id, new_view)
        # Reset folder navigation
        await state.update_data(current_folder_id=None)

        # Reloading happens below

    view_mode = await get_user_view_mode(call.from_user.id)
    current_folder_id = data.get("current_folder_id")

    # Load Objects
    if object_type == "bots":
        # Bots don't have folders logic yet
        objects = await cor(user_id=user.id, sort_by=service)
        folders = []
    else:
        # Channels
        if view_mode == "channels":
            objects = await cor(user_id=user.id, sort_by=service)
            folders = []
        else:  # folders mode
            folders = await db.user_folder.get_folders(user_id=user.id)
            if current_folder_id:
                # Inside a folder
                folder = await db.user_folder.get_folder_by_id(int(current_folder_id))
                objects = []
                if folder and folder.content:
                    for chat_id in folder.content:
                        ch = await db.channel.get_channel_by_chat_id(int(chat_id))
                        if ch:
                            objects.append(ch)
                folders = []  # Don't show folders when inside a folder
            else:
                # Root of folders view
                objects = []

    # SELECT ITEM/FOLDER
    if temp[1].replace("-", "").isdigit():  # Check for digit (ID)
        resource_id = int(temp[1])
        # temp[3] is type if present
        resource_type = temp[3] if len(temp) > 3 else None

        if resource_type == "folder":
            await state.update_data(current_folder_id=resource_id)
            # Re-run logic to enter folder (recursive call or just proceed)
            # Efficient way: update local vars and proceed to render
            current_folder_id = resource_id
            folder = await db.user_folder.get_folder_by_id(resource_id)
            objects = []
            if folder and folder.content:
                for chat_id in folder.content:
                    ch = await db.channel.get_channel_by_chat_id(int(chat_id))
                    if ch:
                        objects.append(ch)
            folders = []
            # Reset pagination
            if len(temp) > 2:
                temp[2] = "0"
        else:
            # It's a channel or bot
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                chosen.append(resource_id)
            await state.update_data(chosen=chosen)

    # CHOICE ALL
    if temp[1] == "choice_all":
        # Get IDs of current objects
        # For folders, decide behavior. Usually 'choice_all' applies to visible items?
        # choice_objects usually implements "select all visible".
        # If view_mode=folders and root, objects are orphaned channels.
        visible_ids = [
            o.chat_id if isinstance(o, db.channel.model.Channel) else o.id
            for o in objects
        ]

        if all(i in chosen for i in visible_ids):
            # Unselect all visible
            for i in visible_ids:
                if i in chosen:
                    chosen.remove(i)
        else:
            # Select all visible
            for i in visible_ids:
                if i not in chosen:
                    chosen.append(i)
        await state.update_data(chosen=chosen)

    # PAYMENT (Next Step)
    if temp[1] == "next_step":
        if not chosen:
            return await call.answer(text("error_min_choice"), show_alert=True)

        total_count_resources = len(chosen)
        total_days = Config.TARIFFS.get(service).get(tariff_id).get("period")
        total_price = (
            Config.TARIFFS.get(service).get(tariff_id).get("amount")
            * total_count_resources
        )

        await state.update_data(
            total_price=total_price,
            total_days=total_days,
            total_count_resources=total_count_resources,
        )
        pay_info_text = await get_pay_info_text(state, user)

        await call.message.delete()
        return await call.message.answer(
            pay_info_text,
            reply_markup=keyboards.choice_payment_method(
                data="ChoicePaymentMethodSubscribe", is_subscribe=True
            ),
        )

    # BACK handling (Folder navigation or Menu)
    if temp[1] == "back" and current_folder_id:
        # Exit folder
        await state.update_data(current_folder_id=None)
        # Logic will auto-reset to root view next render
        # Need to reset objects/folders for correct rendering NOW if we don't return
        folders = await db.user_folder.get_folders(user_id=user.id)
        objects = await db.channel.get_user_channels_without_folders(user_id=user.id)
        # Reset pagination
        if len(temp) > 2:
            temp[2] = "0"

    # CANCEL (Back to Period Choice)
    if temp[1] == "cancel":
        # Recalculate objects for period choice screen? Or just go back.
        # Original code went back to period choice.
        objects = await cor(user_id=user.id, limit=10, sort_by=service)
        await call.message.delete()
        return await call.message.answer(
            text("subscribe_text:{}".format(object_type)).format(
                get_subscribe_list_resources(
                    objects=objects, object_type=object_type, sort_by=service
                )
            ),
            reply_markup=keyboards.choice_period(service=service),
        )

    # RENDER
    # Determine pagination
    remover = 0
    if len(temp) > 2 and temp[2].isdigit():
        remover = int(temp[2])

    # Calculate real chosen titles for display
    # Need to fetch titles for all chosen IDs to display them in text?
    # Original code displayed chosen titles.
    # To avoid N+1, maybe just show count? Or fetch all user channels?
    # Original: text(f'subscribe:chosen:{object_type}').format(...)
    # Let's fetch all user channels to map titles for chosen ones.
    all_resources = await cor(user_id=user.id)
    # Use dictionary for O(1)
    res_map = {
        (r.chat_id if hasattr(r, "chat_id") else r.id): r.title for r in all_resources
    }

    display_text = "\n".join(
        text("resource_title").format(res_map.get(cid, "Unknown"))
        for cid in chosen[:10]
    )

    try:
        await call.message.edit_text(
            text(f"subscribe:chosen:{object_type}").format(display_text),
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                remover=remover,
                data="ChoiceResourceSubscribe",
                view_mode=view_mode,
            ),
        )
    except Exception:
        # Ignore message not modified
        pass


def get_router():
    """Регистрация роутеров подписки."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Subscribe")
    router.callback_query.register(
        choice_period, F.data.split("|")[0] == "ChoiceSubscribePeriod"
    )
    router.callback_query.register(
        choice_object_subscribe, F.data.split("|")[0] == "ChoiceResourceSubscribe"
    )
    return router
