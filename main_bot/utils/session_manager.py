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
        Joins a channel/group with retry logic.
        Attempts 3 times with progressive delays (0s, 1s, 2s).
        Returns True if successful.
        Raises specific exceptions for handling.
        """
        for attempt in range(3):
            try:
                if "t.me/+" in invite_link_or_username or "joinchat" in invite_link_or_username:
                    # Private invite link
                    # Handle "t.me/+HASH"
                    if "t.me/+" in invite_link_or_username:
                        # Split by "t.me/+" but also handle potential http/https prefix
                        # Easiest is split by '+' and take the last part IF strict format
                        # Safer: split by "/" and take last, then remove leading +
                        part = invite_link_or_username.split('/')[-1]
                        if part.startswith('+'):
                            hash_arg = part[1:]
                        else:
                            hash_arg = part # Should not happen if t.me/+ check passed, but safe fallback
                    # Handle "joinchat/HASH" logic
                    elif "joinchat" in invite_link_or_username:
                         hash_arg = invite_link_or_username.split('joinchat/')[-1]
                    else:
                         hash_arg = invite_link_or_username.split('/')[-1]

                    # Strip any potential query params (?)
                    hash_arg = hash_arg.split('?')[0].strip()

                    await self.client(functions.messages.ImportChatInviteRequest(hash=hash_arg))
                else:
                    # Public username
                    username = invite_link_or_username.split('/')[-1]
                    await self.client(functions.channels.JoinChannelRequest(channel=username))
                return True

            except UserAlreadyParticipantError:
                # Already joined, consider success
                return True
            except FloodWaitError as e:
                # Don't retry on flood wait
                raise e
            except rpcerrorlist.InviteHashExpiredError as e:
                # Link expired, no point retrying
                raise e
            except Exception as e:
                if attempt < 2:  # Not the last attempt
                    delay = attempt + 1  # 1s on first retry, 2s on second retry
                    print(f"Join attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Last attempt failed
                    print(f"Join failed after 3 attempts: {e}")
                    raise e
        
        return False

    async def can_send_stories(self, chat_id: int) -> bool:
        """
        Checks if the user can post stories to the chat.
        Includes boost level check.
        """
        try:
            logger.info(f"Checking if can send stories to {chat_id}")
            peer = await self.client.get_input_entity(chat_id)
            chat_full = await self.client(functions.channels.GetFullChannelRequest(channel=peer))
            
            # Check if stories are globally unavailable for this chat
            # Note: Telethon structure might vary, checking dict representation is safer for some fields
            chat_full_dict = chat_full.to_dict()
            
            # Check boost level requirement
            full_chat = chat_full_dict.get('full_chat', {})
            boosts_applied = full_chat.get('boosts_applied', 0)
            boosts_for_stories = full_chat.get('boosts_for_next_level_min', 0)
            
            logger.info(f"Channel {chat_id} boosts: {boosts_applied}, required for stories: {boosts_for_stories}")
            
            # If boosts_for_next_level_min is set and we don't have enough boosts
            if boosts_for_stories > 0 and boosts_applied < boosts_for_stories:
                logger.warning(f"Not enough boosts for {chat_id}: {boosts_applied}/{boosts_for_stories}")
                return False
            
            if chat_full_dict.get('chats', [{}])[0].get('stories_unavailable', False):
                logger.warning(f"Stories are unavailable for {chat_id}")
                return False

            # Check admin rights
            participant = await self.client(functions.channels.GetParticipantRequest(
                channel=peer,
                participant=types.InputUserSelf()
            ))
            
            logger.info(f"Participant type for {chat_id}: {type(participant.participant).__name__}")
            
            if isinstance(participant.participant, types.ChannelParticipantCreator):
                logger.info(f"User is creator of {chat_id}, can post stories")
                return True
            
            if isinstance(participant.participant, types.ChannelParticipantAdmin):
                can_post = participant.participant.admin_rights.post_stories
                logger.info(f"User is admin of {chat_id}, post_stories={can_post}")
                return can_post
            
            logger.warning(f"User is not admin of {chat_id}, participant type: {type(participant.participant).__name__}")
            return False

        except Exception as e:
            logger.error(f"Check stories error for {chat_id}: {e}", exc_info=True)
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
            print(f"Send story error: {e}")
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
            print(f"Get views error: {e}")
            return None

    async def leave_channel(self, chat_id: int) -> bool:
        try:
            peer = await self.client.get_input_entity(chat_id)
            await self.client(functions.channels.LeaveChannelRequest(channel=peer))
            return True
        except Exception as e:
            print(f"Leave channel error: {e}")
            return False


async def main():
    # Example usage
    session_path = Path("sessions/test.session")
    
    # Ensure directory exists for testing
    session_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Testing session: {session_path}")
    
    async with SessionManager(session_path) as manager:
        if not manager.client or not await manager.client.is_user_authorized():
            print("Session not authorized or not found.")
            # Here you would normally trigger login flow
            return

        # 1. Health Check
        print("Running Health Check...")
        health = await manager.health_check()
        print(f"Health Check Result: {health}")

        if not health["ok"]:
            print("Session is not healthy, aborting.")
            return

        # 2. Get Me
        me = await manager.me()
        print(f"Logged in as: {me.first_name} (ID: {me.id})")

        # 3. Check Stories Capability (example channel ID)
        test_channel_id = -1001234567890 # Replace with real ID
        # can_post = await manager.can_send_stories(test_channel_id)
        # print(f"Can post stories to {test_channel_id}: {can_post}")


if __name__ == '__main__':
    asyncio.run(main())
