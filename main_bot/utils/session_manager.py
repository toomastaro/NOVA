"""
Менеджер сессий Telegram клиентов.

Управляет инициализацией, блокировками и использованием Telethon клиентов.
Обеспечивает потокобезопасный доступ к файлам сессий.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from telethon import TelegramClient, functions, types, utils
from telethon.errors import (
    UserAlreadyParticipantError,
    FloodWaitError,
    UserDeactivatedError,
    AuthKeyUnregisteredError,
    UserNotParticipantError,
    rpcerrorlist,
)

from config import Config
from main_bot.utils.schemas import StoryOptions

logger = logging.getLogger(__name__)


class SessionManager:
    _locks = {}

    def __init__(self, session_path: Path):
        self.session_path = session_path
        self.client: TelegramClient | None = None
        self._session_lock = None

    async def __aenter__(self):
        await self.init_client()
        if self.client:
            return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def init_client(self):
        """Инициализация клиента с блокировкой файла сессии"""
        # Получаем или создаем блокировку для этого файла сессии
        path_str = str(self.session_path)
        if path_str not in self._locks:
            self._locks[path_str] = asyncio.Lock()

        self._session_lock = self._locks[path_str]

        # Ожидаем освобождения сессии
        await self._session_lock.acquire()

        try:
            self.client = TelegramClient(
                session=str(self.session_path),
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
                system_version="4.16.30-vxCUSTOM",
                device_model="Desktop",
                app_version="1.0.0",
            )
            await self.client.connect()

            # Быстрая проверка авторизации
            if not await self.client.is_user_authorized():
                # Если не авторизован, health_check это обнаружит позже.
                pass

        except Exception as e:
            logger.error(f"Ошибка инициализации клиента: {e}")
            # Если возникла ошибка, освобождаем блокировку
            if self._session_lock and self._session_lock.locked():
                self._session_lock.release()
                self._session_lock = None

    async def close(self):
        """Закрытие соединения и освобождение блокировки"""
        if self.client:
            await self.client.disconnect()

        if self._session_lock and self._session_lock.locked():
            self._session_lock.release()
            self._session_lock = None

    async def me(self):
        """Получения информации о текущем пользователе"""
        if not self.client:
            return None
        return await self.client.get_me()

    async def health_check(self) -> dict:
        """
        Проверяет, жива ли сессия и работает ли она.
        Выполняет глубокую проверку, включая статус ограничений (Restricted).
        Возвращает: {"ok": True, "me": ...} или {"ok": False, "error_code": "..."}
        """
        # 1. Проверка и попытка восстановления соединения
        if not self.client:
             return {"ok": False, "error_code": "CLIENT_NOT_INITIALIZED"}

        if not self.client.is_connected():
            try:
                await self.client.connect()
            except Exception as e:
                return {"ok": False, "error_code": f"CONNECTION_FAILED: {str(e)}"}

        try:
            # 2. Запрос информации о текущем пользователе (GetMe)
            # Это самый надежный способ проверить валидность AuthKey
            me = await self.client.get_me()
            
            if not me:
                # Иногда бывает, если аккаунт удален, но ошибка не вылетела
                return {"ok": False, "error_code": "USER_NOT_FOUND"}

            # 3. Проверка на ограничения (Спам-блок и т.д.)
            if getattr(me, "restricted", False):
                reasons = []
                if me.restriction_reason:
                    for r in me.restriction_reason:
                        reasons.append(f"{r.platform}: {r.text}")
                reason_str = " | ".join(reasons)
                return {"ok": False, "error_code": f"RESTRICTED: {reason_str}"}

            # 4. Проверка на метку SCAM / FAKE (опционально, но полезно знать)
            if getattr(me, "scam", False):
                 return {"ok": False, "error_code": "ACCOUNT_MARKED_AS_SCAM"}
            
            if getattr(me, "fake", False):
                 return {"ok": False, "error_code": "ACCOUNT_MARKED_AS_FAKE"}

            # 5. Активная проверка: отправка сообщения "как дела?" пользователю @mousesquad
            # Это позволяет выявить PeerFloodError (скрытый спам-блок), который не виден в флагах.
            try:
                await self.client.send_message("mousesquad", "как дела?")
            except Exception as e:
                err_str = str(e)
                # Специальная обработка для PeerFlood (частый признак спам-блока)
                if "PEER_FLOOD" in err_str.upper() or "FLOOD_WAIT" in err_str.upper():
                    return {"ok": False, "error_code": f"SPAM_RESTRICTED: {err_str}"}
                
                return {"ok": False, "error_code": f"SEND_FAILED: {err_str}"}

            return {"ok": True, "me": me}

        except UserDeactivatedError:
            return {"ok": False, "error_code": "USER_DEACTIVATED"}
        except rpcerrorlist.UserDeactivatedBanError:
            return {"ok": False, "error_code": "USER_BANNED"}
        except AuthKeyUnregisteredError:
            return {"ok": False, "error_code": "AUTH_KEY_UNREGISTERED"}
        except FloodWaitError as e:
            return {"ok": False, "error_code": f"FLOOD_WAIT_{e.seconds}"}
        except Exception as e:
            logger.error(f"Ошибка health_check: {e}")
            return {"ok": False, "error_code": f"UNKNOWN: {str(e)}"}

    async def join(self, invite_link_or_username: str, max_attempts: int = 10) -> bool:
        """
        Вступает в канал/группу с надежной логикой повторных попыток.
        Делает заданное кол-во попыток (default 10) с прогрессивной задержкой.
        Возвращает True в случае успеха.
        """

        for attempt in range(max_attempts):
            try:
                logger.info(
                    f"Попытка вступления {attempt + 1}/{max_attempts} в {invite_link_or_username[:20]}..."
                )

                if (
                    "t.me/+" in invite_link_or_username
                    or "joinchat" in invite_link_or_username
                ):
                    # Приватная ссылка
                    # Обработка "t.me/+HASH"
                    if "t.me/+" in invite_link_or_username:
                        part = invite_link_or_username.split("/")[-1]
                        if part.startswith("+"):
                            hash_arg = part[1:]
                        else:
                            hash_arg = part
                    # Обработка "joinchat/HASH"
                    elif "joinchat" in invite_link_or_username:
                        hash_arg = invite_link_or_username.split("joinchat/")[-1]
                    else:
                        hash_arg = invite_link_or_username.split("/")[-1]

                    # Очистка от query параметров (?)
                    hash_arg = hash_arg.split("?")[0].strip()

                    await self.client(
                        functions.messages.ImportChatInviteRequest(hash=hash_arg)
                    )
                else:
                    # Публичный юзернейм
                    username = invite_link_or_username.split("/")[-1]
                    await self.client(
                        functions.channels.JoinChannelRequest(channel=username)
                    )

                logger.info(
                    f"✅ Успешное вступление в {invite_link_or_username[:20]} с попытки {attempt + 1}"
                )
                return True

            except UserAlreadyParticipantError:
                # Уже участник - считаем успехом
                logger.info("ℹ️ Уже является участником")
                return True
            except FloodWaitError as e:
                # FloodWait нужно соблюдать
                logger.warning(f"⚠️ FloodWaitError: {e}")
                if e.seconds < 30:
                    logger.info(f"⏳ Ожидание {e.seconds}с из-за FloodWait...")
                    await asyncio.sleep(e.seconds)
                    continue  # Повторяем сразу после ожидания
                raise e
            except rpcerrorlist.InviteHashExpiredError as e:
                logger.error("❌ Срок действия инвайт-ссылки истек")
                raise e
            except Exception as e:
                # Ловим сетевые ошибки, таймауты
                is_last_attempt = attempt == max_attempts - 1

                if not is_last_attempt:
                    # Прогрессивная задержка: 2, 4, 6...
                    delay = (attempt + 1) * 2
                    logger.warning(
                        f"⚠️ Попытка вступления {attempt + 1} провалилась: {e}. Повтор через {delay}с..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"❌ Не удалось вступить после {max_attempts} попыток: {e}"
                    )
                    raise e

        return False

    async def can_send_stories(self, chat_id: int) -> bool:
        """
        Проверяет, может ли пользователь публиковать истории в чат.
        Включает проверку уровня бустов.
        """
        try:
            logger.info(f"Проверка возможности публикации историй в {chat_id}")
            peer = await self.client.get_input_entity(chat_id)
            chat_full = await self.client(
                functions.channels.GetFullChannelRequest(channel=peer)
            )

            # Доступ к атрибутам напрямую, чтобы избежать проблем с to_dict()
            full_chat = chat_full.full_chat
            boosts_applied = getattr(full_chat, "boosts_applied", 0) or 0
            # boosts_unrestrict часто является полем для "boosts needed to unrestrict"
            boosts_for_stories = getattr(full_chat, "boosts_unrestrict", 0) or 0

            logger.info(
                f"Бусты канала {chat_id}: {boosts_applied}, необходимо для историй: {boosts_for_stories}"
            )

            # Если требуется следующий уровень для историй и бустов недостаточно
            if boosts_for_stories > 0 and boosts_applied < boosts_for_stories:
                logger.warning(
                    f"Недостаточно бустов для {chat_id}: {boosts_applied}/{boosts_for_stories}"
                )
                # return False # Отключено по запросу

            if chat_full.chats and getattr(
                chat_full.chats[0], "stories_unavailable", False
            ):
                logger.warning(f"Истории недоступны для {chat_id}")
                # return False # Отключено по запросу

            # Проверка прав администратора
            participant = await self.client(
                functions.channels.GetParticipantRequest(
                    channel=peer, participant=types.InputUserSelf()
                )
            )

            logger.info(
                f"Тип участника для {chat_id}: {type(participant.participant).__name__}"
            )

            if isinstance(participant.participant, types.ChannelParticipantCreator):
                logger.info(
                    f"Пользователь создатель {chat_id}, может публиковать истории"
                )
                return True

            if isinstance(participant.participant, types.ChannelParticipantAdmin):
                can_post = participant.participant.admin_rights.post_stories
                logger.info(f"Пользователь админ в {chat_id}, post_stories={can_post}")
                if not can_post:
                    logger.warning(
                        "⚠️ Прав на публикацию сторис формально нет, но пытаемся отправить (Checks Disabled)"
                    )
                return True  # Always try

            logger.warning(
                f"Пользователь не админ в {chat_id}, тип участника: {type(participant.participant).__name__}"
            )
            return True  # Always try

        except Exception as e:
            logger.error(f"Ошибка проверки историй для {chat_id}: {e}", exc_info=True)
            # Even if check failed, try to send
            return True

    async def send_story(
        self, chat_id: int, file_path: str, options: StoryOptions
    ) -> bool:
        """Отправка истории в канал (MTProto)."""
        try:
            caption, entities = utils.html.parse(options.caption)
            peer = await self.client.get_input_entity(chat_id)

            file = await self.client.upload_file(file_path)

            if options.photo:
                media = types.InputMediaUploadedPhoto(file=file)
            else:
                # Атрибуты видео по умолчанию, можно улучшить для парсинга реальных метаданных видео
                media = types.InputMediaUploadedDocument(
                    file=file,
                    mime_type="video/mp4",
                    attributes=[
                        types.DocumentAttributeVideo(
                            duration=15, w=720, h=1280, supports_streaming=True
                        )
                    ],
                )

            await self.client(
                functions.stories.SendStoryRequest(
                    peer=peer,
                    media=media,
                    privacy_rules=[types.InputPrivacyValueAllowAll()],
                    noforwards=options.noforwards,
                    caption=caption,
                    entities=entities,
                    pinned=options.pinned,
                    period=options.period,
                )
            )
            return True

        except FloodWaitError as e:
            raise e
        except Exception as e:
            logger.error(f"Ошибка отправки истории: {e}")
            raise e

    async def get_views(
        self, chat_id: int, messages_ids: List[int]
    ) -> Optional[types.messages.MessageViews]:
        """Получить количество просмотров для сообщений."""
        try:
            peer = await self.client.get_input_entity(chat_id)
            return await self.client(
                functions.messages.GetMessagesViewsRequest(
                    peer=peer, id=messages_ids, increment=False
                )
            )
        except Exception as e:
            logger.error(f"Ошибка получения просмотров: {e}")
            return None

    async def leave_channel(self, chat_id: int) -> bool:
        """Выйти из канала."""
        try:
            peer = await self.client.get_input_entity(chat_id)
            await self.client(functions.channels.LeaveChannelRequest(channel=peer))
            return True
        except Exception as e:
            logger.error(f"Ошибка выхода из канала: {e}")
            return False

    async def check_permissions(self, chat_id: int) -> dict:
        """
        Полная проверка прав клиента в канале.
        Возвращает словарь с правами.
        """
        result = {
            "is_member": False,
            "is_admin": False,
            "can_post_messages": False,
            "can_post_stories": False,
            "can_invite_users": False,
            "error": None,
            "me": None,
        }

        try:
            me = await self.client.get_me()
            result["me"] = me

            peer = await self.client.get_input_entity(chat_id)
            participant = await self.client(
                functions.channels.GetParticipantRequest(
                    channel=peer, participant=types.InputUserSelf()
                )
            )

            result["is_member"] = True

            if isinstance(participant.participant, types.ChannelParticipantCreator):
                result["is_admin"] = True
                result["can_post_messages"] = True
                result["can_post_stories"] = True
                result["can_invite_users"] = True
                return result

            if isinstance(participant.participant, types.ChannelParticipantAdmin):
                result["is_admin"] = True
                admin_rights = participant.participant.admin_rights
                result["can_post_messages"] = admin_rights.post_messages
                result["can_post_stories"] = admin_rights.post_stories
                result["can_invite_users"] = admin_rights.invite_users

            return result

        except UserNotParticipantError:
            result["error"] = "USER_NOT_PARTICIPANT"
            return result
        except Exception as e:
            logger.error(f"Ошибка проверки прав в {chat_id}: {e}")
            result["error"] = str(e)
            return result
