"""
Утилиты для работы с Telegram API.

Этот модуль содержит функции для:
- Создания custom emoji из фотографий
- Получения списка редакторов канала
- Настройки MT клиентов для каналов
- Фонового добавления клиентов в каналы
"""
import asyncio
import os
import random
import string
import time
import logging
from pathlib import Path

from aiogram import types
from aiogram.enums import ChatMemberStatus
from PIL import Image, ImageDraw, ImageFilter

from config import Config
from instance_bot import bot as main_bot_obj
from main_bot.database.db import db
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


async def create_emoji(user_id: int, photo_bytes=None):
    """
    Создать custom emoji из фотографии пользователя.
    
    Обрабатывает фото: изменяет размер, делает круглым с размытием краев,
    создает стикер-пак и возвращает ID emoji.
    
    Args:
        user_id: ID пользователя для создания стикер-пака
        photo_bytes: Байты изображения или None для дефолтного emoji
        
    Returns:
        ID custom emoji (строка)
    """
    emoji_id = '5393222813345663485'  # Дефолтный emoji

    # Если фото нет, возвращаем дефолтный emoji
    if not photo_bytes:
        return emoji_id

    try:
        with Image.open(photo_bytes) as img:
            # Изменяем размер до 100x100
            new_image = img.resize((100, 100))
            
            # Создаем круглую маску с размытием
            mask = Image.new("L", new_image.size)
            draw = ImageDraw.Draw(mask)
            draw.ellipse(
                xy=(4, 4, new_image.size[0] - 4, new_image.size[1] - 4),
                fill=255
            )
            mask = mask.filter(ImageFilter.GaussianBlur(2))

            # Сохраняем обработанное изображение
            output_path = f"main_bot/utils/temp/{user_id}.png"
            result = new_image.copy()
            result.putalpha(mask)
            result.save(output_path)

            # Генерируем уникальное имя стикер-пака
            set_id = ''.join(random.sample(string.ascii_letters, k=10)) + '_by_' + (await main_bot_obj.get_me()).username

        # Создаем стикер-пак
        try:
            await main_bot_obj.create_new_sticker_set(
                user_id=user_id,
                name=set_id,
                title='NovaTGEmoji',
                stickers=[
                    types.InputSticker(
                        sticker=types.FSInputFile(
                            path=output_path
                        ),
                        format='static',
                        emoji_list=['🤩']
                    )
                ],
                sticker_format='static',
                sticker_type='custom_emoji'
            )
            r = await main_bot_obj.get_sticker_set(set_id)
            await main_bot_obj.session.close()
            emoji_id = r.stickers[0].custom_emoji_id
            logger.info(f"Создан custom emoji для пользователя {user_id}: {emoji_id}")
        except Exception as e:
            logger.error(f"Ошибка создания стикера: {e}")

        # Удаляем временный файл
        try:
            os.remove(output_path)
        except:
            pass

    except Exception as e:
        logger.error(f"Ошибка обработки фото для emoji: {e}")

    return emoji_id


async def get_editors(call: types.CallbackQuery, chat_id: int):
    """
    Получить список редакторов канала с полными правами.
    
    Проверяет администраторов канала и возвращает только тех,
    у кого есть все необходимые права для редактирования.
    
    Args:
        call: Callback query для доступа к боту
        chat_id: ID канала
        
    Returns:
        Строка с перечислением редакторов (username или имя)
    """
    editors = []

    try:
        admins = await call.bot.get_chat_administrators(chat_id)
        for admin in admins:
            # Пропускаем ботов
            if admin.user.is_bot:
                continue

            # Проверяем наличие записи в БД
            row = await db.get_channel_admin_row(chat_id, admin.user.id)
            if not row:
                continue

            # Для не-владельцев проверяем права
            if not isinstance(admin, types.ChatMemberOwner):
                rights = {
                    admin.can_post_messages,
                    admin.can_edit_messages,
                    admin.can_delete_messages,
                    admin.can_post_stories,
                    admin.can_edit_stories,
                    admin.can_delete_stories
                }
                # Если хотя бы одно право отсутствует - пропускаем
                if False in rights:
                    continue

            editors.append(admin)
    except Exception as e:
        logger.error(f"Ошибка при получении редакторов канала {chat_id}: {e}")
        editors.append("Не удалось обнаружить")

    return "\n".join(
        "@{}".format(i.user.username)
        if i.user.username else i.user.full_name
        for i in editors
    )





async def set_channel_session(chat_id: int):
    # 0. Проверить что бот является членом канала (с retry)
    bot_is_admin = False
    from aiogram.enums import ChatMemberStatus
    
    for attempt in range(3):
        try:
            bot_info = await main_bot_obj.get_me()
            bot_member = await main_bot_obj.get_chat_member(chat_id, bot_info.id)
            
            if bot_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                bot_is_admin = True
                logger.info(f"✅ Бот является администратором в канале {chat_id} (попытка {attempt + 1})")
                break
            else:
                logger.warning(f"⚠️ Бот не является администратором в {chat_id}, статус: {bot_member.status} (попытка {attempt + 1}/3)")
                
        except Exception as e:
            logger.warning(f"⚠️ Невозможно проверить статус бота в {chat_id}: {e} (попытка {attempt + 1}/3)")
        
        # Ждем перед следующей попыткой (кроме последней)
        if attempt < 2:
            logger.info(f"Ожидание 1 секунду перед повторной попыткой...")
            await asyncio.sleep(1.0)
    
    # Если после всех попыток бот не админ - возвращаем ошибку
    if not bot_is_admin:
        error_msg = "Бот не является администратором канала после 3 попыток"
        logger.error(f"❌ {error_msg} в {chat_id}")
        return {
            "error": "Bot Not Admin",
            "message": "Бот не является администратором канала. Пожалуйста, добавьте бота в канал с правами администратора и повторите попытку."
        }
    
    # 1. Получить информацию о канале для round-robin
    channel = await db.get_channel_by_chat_id(chat_id)
    if not channel:
        logger.error(f"Канал {chat_id} не найден в базе данных")
        return {"error": "Channel Not Found"}
    
    # 2. Получить следующего внутреннего клиента используя round-robin
    client = await db.get_next_internal_client(channel.id)
    
    if not client:
        logger.error("Нет активных внутренних клиентов")
        return {"error": "No Active Clients"}
    
    logger.info(f"🔄 Выбран клиент {client.id} ({client.alias}) для канала {chat_id} используя round-robin")
    
    session_path = Path(client.session_path)
    if not session_path.exists():
        logger.error(f"Файл сессии не найден для клиента {client.id}: {session_path}")
        return {"error": "Session File Not Found"}
    async with SessionManager(session_path) as manager:
        if not manager:
            logger.error(f"Не удалось создать SessionManager для клиента {client.id}")
            return {"error": "Session Manager Failed"}
        
        # Получить user_id клиента
        me = await manager.me()
        if not me:
            logger.error(f"Не удалось получить информацию о пользователе для клиента {client.id}")
            return {"error": "Failed to Get User Info"}
        
        logger.info(f"Клиент {client.id} (user_id={me.id}) готов к вступлению")
        # Шаг 0: Превентивно снимаем бан если есть (один раз в начале)
        # Если клиент не забанен, это ничего не сделает благодаря only_if_banned=True
        try:
            await main_bot_obj.unban_chat_member(chat_id, me.id, only_if_banned=True)
            logger.debug(f"Превентивная проверка разбана завершена для клиента {client.id}")
            await asyncio.sleep(0.5)
        except Exception as unban_error:
            # Это нормально - клиент может быть не забанен
            logger.debug(f"Результат превентивного разбана для клиента {client.id}: {unban_error}")
        # Флаг успешного добавления
        client_added = False
        
        # Шаг 1: Если канал публичный - вступаем по username (надежнее и быстрее)
        # Если приватный - переходим к fallback методу с инвайт-ссылкой
        try:
 
             chat = await main_bot_obj.get_chat(chat_id)
             if chat.username:
                 logger.info(f"Канал {chat_id} публичный (@{chat.username}), попытка прямого вступления")
                 if await manager.join(f"@{chat.username}"):
                     client_added = True
                     logger.info(f"✅ Клиент {client.id} вступил через юзернейм @{chat.username}")

        except Exception as e:
            logger.warning(f"Прямое вступление по юзернейму не удалось: {e}")

            
        # Если клиент не был добавлен через InviteToChannelRequest, пробуем через invite ссылку
        if not client_added:
            logger.info(f"Попытка запасного метода (инвайт-ссылка) для клиента {client.id}")
            
            try:
                # Создаем ПОСТОЯННУЮ ссылку для клиента
                from datetime import datetime
                chat_invite_link = await main_bot_obj.create_chat_invite_link(
                    chat_id=chat_id,
                    name=f"Nova Stats {datetime.now().strftime('%d.%m.%Y')}",
                    creates_join_request=False
                    # БЕЗ member_limit - ссылка постоянная и многоразовая
                )
                logger.info(f"✅ Создана постоянная запасная инвайт-ссылка для {chat_id}: {chat_invite_link.invite_link}")
                
                success_join = await manager.join(chat_invite_link.invite_link)
                if not success_join:
                    logger.warning(f"❌ Клиент {client.id} не смог вступить через инвайт-ссылку")
                    return {"error": "Failed to Join via Invite Link"}
                
                logger.info(f"✅ Клиент {client.id} успешно вступил через инвайт-ссылку")
                client_added = True
                    
            except Exception as link_error:
                logger.error(f"❌ Запасная инвайт-ссылка также не сработала для клиента {client.id}: {link_error}")
                
                # Send alert for access loss
                error_str = str(link_error)
                if "USER_NOT_PARTICIPANT" in error_str or "CHANNEL_PRIVATE" in error_str or "CHAT_ADMIN_REQUIRED" in error_str:
                    from main_bot.utils.support_log import send_support_alert, SupportAlert
                    channel_obj = await db.get_channel_by_chat_id(chat_id)
                    
                    await send_support_alert(main_bot_obj, SupportAlert(
                        event_type='INTERNAL_ACCESS_LOST',
                        client_id=client.id,
                        client_alias=client.alias,
                        pool_type=client.pool_type,
                        channel_id=chat_id,
                        is_our_channel=True,
                        error_code=error_str.split('(')[0].strip() if '(' in error_str else error_str[:50],
                        error_text=f"Не удалось добавить клиента в канал: {error_str[:100]}"
                    ))
                
                return {"error": "Failed to Add Client"}
        
        if not client_added:
            logger.error(f"❌ Не удалось добавить клиента {client.id} в канал {chat_id}")
            return {"error": "Failed to Add Client"}
        
        # Клиент успешно добавлен
        logger.info(f"✅ Клиент {client.id} вступил в канал {chat_id}, пропуск повышения (только вручную)")

        # Добавляем клиента в БД как обычного участника
        await db.get_or_create_mt_client_channel(client.id, chat_id)
        # Check if we need to set preferred stats (if none exists)
        preferred_stats = await db.get_preferred_for_stats(chat_id)
        is_preferred = False
        if not preferred_stats:
            is_preferred = True
            
        await db.set_membership(
            client_id=client.id,
            channel_id=chat_id,
            is_member=True,
            is_admin=False,
            can_post_stories=False,
            last_joined_at=int(time.time()),
            preferred_for_stats=is_preferred
        )
        
        await db.update_channel_by_chat_id(
            chat_id=chat_id,
            session_path=str(session_path)
        )
        
        # Update last_client_id for round-robin
        await db.update_last_client(channel.id, client.id)
        logger.info(f"✅ Обновлен last_client_id для канала {channel.id} на {client.id}")
        
        return {"success": True, "bot_rights": {}, "session_path": str(session_path)}


async def background_join_channel(chat_id: int, user_id: int = None):
    """
    Попытка добавить клиента в канал в фоне с ретраями.
    Делает 3 попытки с экспоненциальной задержкой.
    Отправляет уведомление пользователю о результате выдачи прав администратора.
    """
    import asyncio
    
    for attempt in range(3):
        try:
            # Используем существующую логику set_channel_session
            res = await set_channel_session(chat_id)
            
            # Проверяем успех (теперь возвращает dict с bot_rights или dict с ошибкой)
            if isinstance(res, dict):
                # Проверка на ошибку "Бот не в канале"
                if res.get("error") == "Bot Not Admin":
                    logger.error(f"❌ {res.get('error')}: {res.get('message')}")
                    
                    # Отправить сообщение пользователю
                    if user_id:
                        try:
                            await main_bot_obj.send_message(
                                chat_id=user_id,
                                text=f"❌ <b>Ошибка добавления MTProto-клиента</b>\n\n{res.get('message')}",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                    
                    return  # Прекращаем попытки
                
                # Проверка на успех
                if res.get("success"):
                    logger.info(f"Успешно добавлен клиент в канал {chat_id} на попытке {attempt+1}")
                
                # Отправить уведомление пользователю только при ошибках
                if user_id:
                    bot_rights = res.get("bot_rights", {})
                    
                    if bot_rights.get("promoted"):
                        # Auto-promoted (should not happen now)
                        message = f"✅ <b>MTProto-клиент настроен!</b>\n\nКлиент был успешно добавлен и получил права администратора."
                    else:
                        # Manual promotion required
                        message = (
                            f"✅ <b>MTProto-клиент добавлен!</b>\n\n"
                            f"Клиент успешно вступил в канал {chat_id}.\n"
                            f"👉 <b>ОБЯЗАТЕЛЬНО:</b> Зайдите в настройки канала и назначьте этого пользователя администратором вручную.\n"
                            f"Необходимые права: Публикация, Редактирование, Удаление."
                        )
                    
                    try:
                        if message:  # Отправляем только если message не None
                            await main_bot_obj.send_message(
                                chat_id=user_id,
                                text=message,
                                parse_mode="HTML"
                            )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                
                return
            
            # Если вернулась ошибка
            logger.warning(f"Попытка {attempt+1} добавления клиента в канал {chat_id} неудачна: {res}")
            
        except Exception as e:
            logger.error(f"Ошибка при фоновом добавлении клиента в канал {chat_id}: {e}")
            
        # Ждем перед следующей попыткой (экспоненциально)
        if attempt < 2:  # Не ждем после последней попытки
            await asyncio.sleep(5 * (attempt + 1))
    
    # Если все попытки исчерпаны - алерт уже будет отправлен внутри set_channel_session
    logger.error(f"Все попытки добавления клиента в канал {chat_id} исчерпаны")

