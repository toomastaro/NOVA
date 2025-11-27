from main_bot.database.bot_post.crud import BotPostCrud
from main_bot.database.channel.crud import ChannelCrud
from main_bot.database.channel_bot_captcha.crud import ChannelCaptchaMessageCrud
from main_bot.database.channel_bot_hello.crud import ChannelHelloMessageCrud
from main_bot.database.channel_bot_settings.crud import ChannelBotSettingCrud
from main_bot.database.payment.crud import PaymentCrud
from main_bot.database.promo.crud import PromoCrud
from main_bot.database.purchase.crud import PurchaseCrud
from main_bot.database.stats.crud import StatsCrud
from main_bot.database.user.crud import UserCrud
from main_bot.database.ad_tag.crud import AdTagCrud
from main_bot.database.user_bot.crud import UserBotCrud
from main_bot.database.user_folder.crud import UserFolderCrud
from main_bot.database.post.crud import PostCrud
from main_bot.database.published_post.crud import PublishedPostCrud
from main_bot.database.story.crud import StoryCrud
from main_bot.database import engine, Base


class Database(
    AdTagCrud,
    UserFolderCrud,
    UserCrud,
    PromoCrud,
    PaymentCrud,
    PurchaseCrud,
    StatsCrud,
    PostCrud,
    BotPostCrud,
    PublishedPostCrud,
    StoryCrud,
    UserBotCrud,
    ChannelCrud,

    # Bot Settings
    ChannelBotSettingCrud,
    ChannelHelloMessageCrud,
    ChannelCaptchaMessageCrud,
):
    @staticmethod
    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


db = Database()
