import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Union

from telethon import TelegramClient, functions, types, utils
from telethon.errors import (
    UserAlreadyParticipantError,
    FloodWaitError,
    UserDeactivatedError,
    AuthKeyUnregisteredError,
    UserNotParticipantError,
    ChatAdminRequiredError,
    rpcerrorlist
)

from config import Config
from main_bot.utils.schemas import StoryOptions

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, session_path: Path):
        self.session_path = session_path
        self.client: TelegramClient | None = None

    async def __aenter__(self):
        await self.init_client()
        if self.client:
            return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def init_client(self):
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
            
            # Quick check if authorized
            if not await self.client.is_user_authorized():
                # If not authorized, we might need to handle it, but for now just let it be.
                # The health_check will catch it.
                pass
                
        except Exception as e:
            print(f"Init client error: {e}")

    async def close(self):
        if self.client:
            await self.client.disconnect()

    async def me(self):
        if not self.client:
            return None
        return await self.client.get_me()

    async def health_check(self) -> dict:
        """
        Checks if the session is alive and working.
        Returns: {"ok": True} or {"ok": False, "error_code": "..."}
        """
        if not self.client or not self.client.is_connected():
            return {"ok": False, "error_code": "CLIENT_NOT_CONNECTED"}

        try:
            # Simple RPC call to check connection and auth
            await self.client(functions.help.GetConfigRequest())
            me = await self.client.get_me()
            if not me:
                return {"ok": False, "error_code": "USER_NOT_FOUND"}
                
            return {"ok": True}

        except UserDeactivatedError:
            return {"ok": False, "error_code": "USER_DEACTIVATED"}
        except AuthKeyUnregisteredError:
            return {"ok": False, "error_code": "AUTH_KEY_UNREGISTERED"}
        except FloodWaitError as e:
            return {"ok": False, "error_code": f"FLOOD_WAIT_{e.seconds}"}
        except Exception as e:
            return {"ok": False, "error_code": f"UNKNOWN_ERROR_{str(e)}"}

    async def join(self, invite_link_or_username: str) -> bool:
        """
        Вступает в канал/группу с надежной логикой повторных попыток.
        Делает 10 попыток с прогрессивной задержкой для обработки лагов серверов Telegram.
        Возвращает True в случае успеха.
        Вызывает исключения для обработки на уровнях выше.
        """
        max_attempts = 10
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"Попытка вступления {attempt + 1}/{max_attempts} в {invite_link_or_username[:20]}...")
                
                if "t.me/+" in invite_link_or_username or "joinchat" in invite_link_or_username:
                    # Приватная ссылка
                    # Обработка "t.me/+HASH"
                    if "t.me/+" in invite_link_or_username:
                        part = invite_link_or_username.split('/')[-1]
                        if part.startswith('+'):
                            hash_arg = part[1:]
                        else:
                            hash_arg = part
                    # Обработка "joinchat/HASH"
                    elif "joinchat" in invite_link_or_username:
                         hash_arg = invite_link_or_username.split('joinchat/')[-1]
                    else:
                         hash_arg = invite_link_or_username.split('/')[-1]

                    # Очистка от query параметров (?)
                    hash_arg = hash_arg.split('?')[0].strip()

                    await self.client(functions.messages.ImportChatInviteRequest(hash=hash_arg))
                else:
                    # Публичный юзернейм
                    username = invite_link_or_username.split('/')[-1]
                    await self.client(functions.channels.JoinChannelRequest(channel=username))
                
                logger.info(f"✅ Успешное вступление в {invite_link_or_username[:20]} с попытки {attempt + 1}")
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
                     continue # Повторяем сразу после ожидания
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
                    logger.warning(f"⚠️ Попытка вступления {attempt + 1} провалилась: {e}. Повтор через {delay}с...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Не удалось вступить после {max_attempts} попыток: {e}")
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
            chat_full = await self.client(functions.channels.GetFullChannelRequest(channel=peer))
            
            # Проверка глобальной доступности историй
            chat_full_dict = chat_full.to_dict()
            
            # Проверка уровня бустов
            full_chat = chat_full_dict.get('full_chat', {})
            boosts_applied = full_chat.get('boosts_applied', 0)
            boosts_for_stories = full_chat.get('boosts_for_next_level_min', 0)
            
            logger.info(f"Бусты канала {chat_id}: {boosts_applied}, необходимо для историй: {boosts_for_stories}")
            
            # Если требуется следующий уровень для историй и бустов недостаточно
            if boosts_for_stories > 0 and boosts_applied < boosts_for_stories:
                logger.warning(f"Недостаточно бустов для {chat_id}: {boosts_applied}/{boosts_for_stories}")
                return False
            
            if chat_full_dict.get('chats', [{}])[0].get('stories_unavailable', False):
                logger.warning(f"Истории недоступны для {chat_id}")
                return False

            # Проверка прав администратора
            participant = await self.client(functions.channels.GetParticipantRequest(
                channel=peer,
                participant=types.InputUserSelf()
            ))
            
            logger.info(f"Тип участника для {chat_id}: {type(participant.participant).__name__}")
            
            if isinstance(participant.participant, types.ChannelParticipantCreator):
                logger.info(f"Пользователь создатель {chat_id}, может публиковать истории")
                return True
            
            if isinstance(participant.participant, types.ChannelParticipantAdmin):
                can_post = participant.participant.admin_rights.post_stories
                logger.info(f"Пользователь админ в {chat_id}, post_stories={can_post}")
                return can_post
            
            logger.warning(f"Пользователь не админ в {chat_id}, тип участника: {type(participant.participant).__name__}")
            return False

        except Exception as e:
            logger.error(f"Ошибка проверки историй для {chat_id}: {e}", exc_info=True)
            return False

    async def send_story(self, chat_id: int, file_path: str, options: StoryOptions) -> bool:
        try:
            caption, entities = utils.html.parse(options.caption)
            peer = await self.client.get_input_entity(chat_id)

            file = await self.client.upload_file(file_path)

            if options.photo:
                media = types.InputMediaUploadedPhoto(file=file)
            else:
                # Default video attributes, can be enhanced to parse actual video metadata
                media = types.InputMediaUploadedDocument(
                    file=file,
                    mime_type="video/mp4",
                    attributes=[
                        types.DocumentAttributeVideo(
                            duration=15, 
                            w=720, 
                            h=1280, 
                            supports_streaming=True
                        )
                    ]
                )

            await self.client(functions.stories.SendStoryRequest(
                peer=peer,
                media=media,
                privacy_rules=[types.InputPrivacyValueAllowAll()],
                noforwards=options.noforwards,
                caption=caption,
                entities=entities,
                pinned=options.pinned,
                period=options.period
            ))
            return True

        except FloodWaitError as e:
            raise e
        except Exception as e:
            logger.error(f"Ошибка отправки истории: {e}")
            raise e

    async def get_views(self, chat_id: int, messages_ids: List[int]) -> Optional[types.messages.MessageViews]:
        try:
            peer = await self.client.get_input_entity(chat_id)
            return await self.client(functions.messages.GetMessagesViewsRequest(
                peer=peer,
                id=messages_ids,
                increment=False
            ))
        except Exception as e:
            logger.error(f"Ошибка получения просмотров: {e}")
            return None

    async def leave_channel(self, chat_id: int) -> bool:
        try:
            peer = await self.client.get_input_entity(chat_id)
            await self.client(functions.channels.LeaveChannelRequest(channel=peer))
            return True
        except Exception as e:
            logger.error(f"Ошибка выхода из канала: {e}")
            return False
