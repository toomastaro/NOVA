import os
import random
import string
import logging

from aiogram import types
from PIL import Image, ImageDraw, ImageFilter

from instance_bot import bot

logger = logging.getLogger(__name__)


async def create_emoji(user_id: int, photo_bytes=None):
    emoji_id = '5393222813345663485'

    if not photo_bytes:
        photo_bytes = 'main_bot/utils/no_photo.jpg'

    try:
        with Image.open(photo_bytes) as img:
            new_image = img.resize((100, 100))
            mask = Image.new("L", new_image.size)
            draw = ImageDraw.Draw(mask)
            draw.ellipse(
                xy=(4, 4, new_image.size[0] - 4, new_image.size[1] - 4),
                fill=255
            )
            mask = mask.filter(ImageFilter.GaussianBlur(2))

            output_path = f"main_bot/utils/temp/{user_id}.png"
            result = new_image.copy()
            result.putalpha(mask)
            result.save(output_path)

            set_id = ''.join(random.sample(string.ascii_letters, k=10)) + '_by_' + (await bot.get_me()).username

        try:
            await bot.create_new_sticker_set(
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
            r = await bot.get_sticker_set(set_id)
            # await bot.session.close()  # CRITICAL FIX: Do not close global bot session!
            emoji_id = r.stickers[0].custom_emoji_id
        except Exception:
            logger.error("Error creating sticker set", exc_info=True)

        os.remove(output_path)

    except Exception:
        logger.error("Error in create_emoji", exc_info=True)

    return emoji_id
