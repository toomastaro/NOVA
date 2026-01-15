"""
Утилиты для работы с Telegram API.

Этот модуль содержит функции для:
- Создания custom emoji из фотографий
- Получения списка редакторов канала
- Настройки MT клиентов для каналов
- Фонового добавления клиентов в каналы
"""

import asyncio
import time
import logging
from pathlib import Path

from aiogram import types
from aiogram.enums import ChatMemberStatus

from instance_bot import bot as main_bot_obj
from main_bot.database.db import db
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


async def create_emoji(user_id: int, photo_bytes=None) -> str:
    """
    Создать custom emoji из фотографии пользователя (ОТКЛЮЧЕНО).
    """
    return "5393222813345663485"  # Дефолтный emoji

    # # Если фото нет, возвращаем дефолтный emoji
    # if not photo_bytes:
    #     return emoji_id

    # try:
    #     with Image.open(photo_bytes) as img:
    #         # Изменяем размер до 100x100
    #         new_image = img.resize((100, 100))

    #         # Создаем круглую маску с размытием
    #         mask = Image.new("L", new_image.size)
    #         draw = ImageDraw.Draw(mask)
    #         draw.ellipse(
    #             xy=(4, 4, new_image.size[0] - 4, new_image.size[1] - 4), fill=255
    #         )
    #         mask = mask.filter(ImageFilter.GaussianBlur(2))

    #         # Сохраняем обработанное изображение
    #         output_path = f"main_bot/utils/temp/{user_id}.png"
    #         # Убеждаемся, что директория существует
    #         os.makedirs(os.path.dirname(output_path), exist_ok=True)

    #         result = new_image.copy()
    #         result.putalpha(mask)
    #         result.save(output_path)

    #         # Генерируем уникальное имя стикер-пака
    #         bot_info = await main_bot_obj.get_me()
    #         set_id = (
    #             "".join(random.sample(string.ascii_letters, k=10))
    #             + "_by_"
    #             + bot_info.username
    #         )

    #     # Создаем стикер-пак
    #     try:
    #         await main_bot_obj.create_new_sticker_set(
    #             user_id=user_id,
    #             name=set_id,
    #             title="NovaTGEmoji",
    #             stickers=[
    #                 types.InputSticker(
    #                     sticker=types.FSInputFile(path=output_path),
    #                     format="static",
    #                     emoji_list=["🤩"],
    #                 )
    #             ],
    #             sticker_format="static",
    #             sticker_type="custom_emoji",
    #         )
    #         r = await main_bot_obj.get_sticker_set(set_id)
    #         # await main_bot_obj.session.close() # Не закрываем сессию здесь, используется общий объект бота
    #         if r.stickers:
    #             emoji_id = r.stickers[0].custom_emoji_id
    #             logger.info(
    #                 f"Создан custom emoji для пользователя {user_id}: {emoji_id}"
    #             )
    #         else:
    #             logger.warning(f"Стикер-пак создан, но стикеров нет для {user_id}")

    #     except Exception as e:
    #         logger.error(f"Ошибка создания стикера: {e}")

    #     # Удаляем временный файл
    #     try:
    #         if os.path.exists(output_path):
    #             os.remove(output_path)
    #     except Exception as e:
    #         logger.warning(f"Не удалось удалить временный файл {output_path}: {e}")

    # except Exception as e:
    #     logger.error(f"Ошибка обработки фото для emoji: {e}")

    # return emoji_id


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
            row = await db.channel.get_channel_admin_row(chat_id, admin.user.id)
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
                    admin.can_delete_stories,
                }
                # Если хотя бы одно право отсутствует - пропускаем
                if False in rights:
                    continue

            editors.append(admin)
    except Exception as e:
        logger.error(f"Ошибка при получении редакторов канала {chat_id}: {e}")
        editors.append("Не удалось обнаружить")

    return "\n".join(
        "@{}".format(i.user.username) if i.user.username else i.user.full_name
        for i in editors
        if not isinstance(i, str)  # Отфильтровать строки ошибок, если они есть
    )


async def set_channel_session(chat_id: int):
    """
    Настройка сессии MT клиента для канала.
    Проверяет права бота, создает инвайт, назначает свободный клиент с round-robin.
    """
    # 0. Проверить что бот является членом канала (с retry)
    bot_is_admin = False

    for attempt in range(3):
        try:
            bot_info = await main_bot_obj.get_me()
            bot_member = await main_bot_obj.get_chat_member(chat_id, bot_info.id)

            if bot_member.status in [
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            ]:
                bot_is_admin = True
                logger.info(
                    f"✅ Бот является администратором в канале {chat_id} (попытка {attempt + 1})"
                )
                break
            else:
                logger.warning(
                    f"⚠️ Бот не является администратором в {chat_id}, статус: {bot_member.status} (попытка {attempt + 1}/3)"
                )

        except Exception as e:
            logger.warning(
                f"⚠️ Невозможно проверить статус бота в {chat_id}: {e} (попытка {attempt + 1}/3)"
            )

        # Ждем перед следующей попыткой (кроме последней)
        if attempt < 2:
            logger.info("Ожидание 1 секунду перед повторной попыткой...")
            await asyncio.sleep(1.0)

    # Если после всех попыток бот не админ - возвращаем ошибку
    if not bot_is_admin:
        error_msg = "Bot Not Admin"
        logger.error(f"❌ {error_msg} в {chat_id}")
        return {
            "error": "Bot Not Admin",
            "message": "Бот не является администратором канала. Пожалуйста, добавьте бота в канал с правами администратора и повторите попытку.",
        }

    # Создать инвайт-ссылку для помощника
    invite_link = None
    try:
        invite = await main_bot_obj.create_chat_invite_link(
            chat_id=chat_id, name="Nova Assistant Auto", creates_join_request=False
        )
        invite_link = invite.invite_link
        logger.info(f"Создана инвайт-ссылка для канала {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка создания ссылки приглашения: {e}")
        return {
            "error": "Invite Creation Failed",
            "message": f"Не удалось создать ссылку: {str(e)}",
        }

    # 1. Получить информацию о канале для round-robin
    channel = await db.channel.get_channel_by_chat_id(chat_id)
    if not channel:
        logger.error(f"Канал {chat_id} не найден в базе данных")
        return {"error": "Channel Not Found"}

    # 2. Получить следующего внутреннего клиента используя round-robin
    client = await db.mt_client.get_next_internal_client(chat_id)

    if not client:
        logger.error("Нет активных внутренних клиентов")
        return {"error": "No Active Clients"}

    logger.info(
        f"🔄 Выбран клиент {client.id} ({client.alias}) для канала {chat_id} используя Least Used (min load)"
    )

    session_path = Path(client.session_path)
    if not session_path.exists():
        logger.error(f"Файл сессии не найден для клиента {client.id}: {session_path}")
        return {"error": "Session File Not Found"}

    async with SessionManager(session_path) as manager:
        if not manager.client:  # Проверка инициализации клиента
            logger.error(
                f"Не удалось инициализировать SessionManager для клиента {client.id}"
            )
            return {"error": "Session Manager Failed"}

        # Получить user_id клиента
        me = await manager.me()
        if not me:
            logger.error(
                f"Не удалось получить информацию о пользователе для клиента {client.id}"
            )
            return {"error": "Failed to Get User Info"}

        # Попытка автоматического вступления
        logger.info(f"Клиент {client.id} пробует вступить в канал {chat_id}...")
        join_success = False
        try:
            if invite_link:
                join_success = await manager.join(invite_link, max_attempts=5)
            else:
                logger.warning("Ссылка приглашения отсутствует, пропуск вступления")

            if join_success:
                logger.info(f"✅ Клиент {client.id} успешно вступил в канал {chat_id}")
            else:
                logger.warning(
                    f"⚠️ Клиент {client.id} не смог вступить в канал {chat_id} (5 попыток)"
                )
        except Exception as e:
            logger.error(f"Ошибка при вступлении клиента {client.id}: {e}")

        if me.username:
            await db.mt_client.update_mt_client(client.id, alias=me.username)

        # Добавляем клиента в БД
        await db.mt_client_channel.get_or_create_mt_client_channel(client.id, chat_id)

        # Проверяем, есть ли другие помощники
        preferred_stats = await db.mt_client_channel.get_preferred_for_stats(chat_id)
        is_preferred = False
        if not preferred_stats:
            is_preferred = True

        # Проверяем права сразу после вступления (или если уже в канале)
        is_admin = False
        can_stories = False
        perms = await manager.check_permissions(chat_id)
        if not perms.get("error"):
            is_admin = perms.get("is_admin", False)
            can_stories = perms.get("can_post_stories", False)
            if perms.get("me") and perms["me"].username:
                await db.mt_client.update_mt_client(
                    client.id, alias=perms["me"].username
                )

        # Устанавливаем членство с актуальными правами
        await db.mt_client_channel.set_membership(
            client_id=client.id,
            channel_id=chat_id,
            is_member=perms.get("is_member", join_success),
            is_admin=is_admin,
            can_post_stories=can_stories,
            last_joined_at=int(time.time()),
            preferred_for_stats=is_preferred,
        )

        # Обновление сессии и last_client_id для всех админов канала (синхронизация)
        await db.channel.update_channel_by_chat_id(
            chat_id=chat_id, session_path=str(session_path), last_client_id=client.id
        )
        logger.info(
            f"✅ Обновлены сессия и last_client_id для канала {chat_id} (клиент: {client.id})"
        )

        return {
            "success": True,
            "bot_rights": {},
            "session_path": str(session_path),
            "joined": join_success,
            "client_info": {
                "id": me.id,
                "first_name": me.first_name,
                "username": me.username,
            },
        }


async def background_join_channel(chat_id: int, user_id: int = None):
    """
    Попытка добавить клиента в канал в фоне с ретраями.
    Делает 3 попытки с экспоненциальной задержкой.
    """
    # Попытка добавления клиента с экспоненциальной задержкой
    for attempt in range(3):
        try:
            # Используем существующую логику set_channel_session
            res = await set_channel_session(chat_id)

            # Проверяем успех (теперь возвращает dict с bot_rights или dict с ошибкой)
            if isinstance(res, dict):
                # Проверка на ошибку "Бот не в канале"
                if res.get("error") == "Bot Not Admin":
                    logger.error(f"❌ {res.get('error')}: {res.get('message')}")
                    return  # Прекращаем попытки

                # Проверка на успех
                if res.get("success"):
                    logger.info(
                        f"Успешно добавлен Нова помощник в канал {chat_id} на попытке {attempt + 1}"
                    )
                    return

            # Если вернулась ошибка
            logger.warning(
                f"Попытка {attempt + 1} добавления клиента в канал {chat_id} неудачна: {res}"
            )

        except Exception as e:
            logger.error(
                f"Ошибка при фоновом добавлении клиента в канал {chat_id}: {e}"
            )

        # Ждем перед следующей попыткой (экспоненциально)
        if attempt < 2:  # Не ждем после последней попытки
            await asyncio.sleep(5 * (attempt + 1))

    # Если все попытки исчерпаны
    logger.error(f"Все попытки добавления клиента в канал {chat_id} исчерпаны")
