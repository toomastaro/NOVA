import asyncio
from pathlib import Path
from typing import List

from telethon import TelegramClient, functions, types, utils
from telethon.errors import UserAlreadyParticipantError, FloodWaitError

from config import Config
from main_bot.utils.schemas import StoryOptions


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
                session=self.session_path,
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
            )
            await self.client.connect()
            await asyncio.wait_for(self.client.get_me(), timeout=10)
        except Exception as e:
            return print(e)

    async def close(self):
        if self.client:
            await self.client.disconnect()

    async def me(self):
        return await self.client(
            functions.users.GetUsersRequest(
                [types.InputUserSelf()]
            )
        )

    async def join(self, invite_url: str):
        invite_hash = invite_url.split('/')[-1].replace('+', '')

        try:
            return await self.client(
                functions.messages.ImportChatInviteRequest(
                   hash=invite_hash
                )
            )
        except (UserAlreadyParticipantError, FloodWaitError, Exception) as e:
            print(e)

    async def can_send_stories(self, chat_id: int):
        peer = await self.client.get_input_entity(chat_id)
        chat_info = await self.client(
            functions.channels.GetFullChannelRequest(
                types.InputChannel(
                    channel_id=chat_id,
                    access_hash=peer.access_hash
                )
            )
        )
        raw = chat_info.to_dict()
        return raw.get("chats", [{}])[0].get("stories_unavailable", False)

    async def get_views(self, chat_id: int, messages_ids: List[int]):
        peer = await self.client.get_input_entity(chat_id)
        return await self.client(
            functions.messages.GetMessagesViewsRequest(
                peer=peer,
                id=messages_ids,
                increment=False
            )
        )

    async def send_story(self, chat_id: int, filepath: str, options: StoryOptions):
        caption, entities = utils.html.parse(options.caption)
        peer = await self.client.get_input_entity(chat_id)

        with open(filepath, "rb") as f:
            file = await self.client.upload_file(f)

        if options.photo:
            media = types.InputMediaUploadedPhoto(file=file)
        else:
            media = types.InputMediaUploadedDocument(
                file=file,
                mime_type="video/mp4",
                attributes=[types.DocumentAttributeVideo(duration=15, w=720, h=1280, supports_streaming=True)]
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
                period=options.period
            )
        )


async def main():
    session_path = Path("sessions/session.session")
    async with SessionManager(session_path) as manager:
        # code_request = await manager.client.send_code_request(phone="+7 919 132 4846")
        # code = input("Code: ")
        # sign_in = await manager.client.sign_in("+7 919 132 4846", code, phone_code_hash=code_request.phone_code_hash)
        # print(sign_in)
        # return
        me = await manager.me()
        print(me[0].id)
        return
        # try:
        #     join = await manager.join(invite_url="https://t.me/+uo9rqgeXa5o0MTFi")
        #     print(join)
        # except (UserAlreadyParticipantError, FloodWaitError):
        #     pass

        stories_unavailable = await manager.can_send_stories(chat_id=2092409247)
        print(stories_unavailable)

        types.MessageViews()
        views = await manager.get_views(chat_id=2092409247, messages_ids=[952, 953])
        print(sum([i.views for i in views.views]))


if __name__ == '__main__':
    asyncio.run(main())
