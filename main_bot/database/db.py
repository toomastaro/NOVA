from main_bot.database import Base, DatabaseMixin, engine
from main_bot.database.ad_creative.crud import AdCreativeCrud
from main_bot.database.ad_purchase.crud import AdPurchaseCrud
from main_bot.database.ad_tag.crud import AdTagCrud
from main_bot.database.bot_post.crud import BotPostCrud
from main_bot.database.channel.crud import ChannelCrud
from main_bot.database.channel_bot_captcha.crud import ChannelCaptchaMessageCrud
from main_bot.database.channel_bot_hello.crud import ChannelHelloMessageCrud
from main_bot.database.channel_bot_settings.crud import ChannelBotSettingCrud
from main_bot.database.exchange_rate.crud import ExchangeRateCrud
from main_bot.database.mt_client.crud import MtClientCrud
from main_bot.database.mt_client_channel.crud import MtClientChannelCrud
from main_bot.database.novastat.crud import NovaStatCrud
from main_bot.database.novastat_cache.crud import NovaStatCacheCrud
from main_bot.database.payment.crud import PaymentCrud
from main_bot.database.payment_link.crud import PaymentLinkCrud
from main_bot.database.post.crud import PostCrud
from main_bot.database.promo.crud import PromoCrud
from main_bot.database.published_post.crud import PublishedPostCrud
from main_bot.database.purchase.crud import PurchaseCrud
from main_bot.database.stats.crud import StatsCrud
from main_bot.database.story.crud import StoryCrud
from main_bot.database.user.crud import UserCrud
from main_bot.database.user_bot.crud import UserBotCrud
from main_bot.database.user_folder.crud import UserFolderCrud


class Database(DatabaseMixin):
    """
    Основной класс базы данных, использующий композицию для доступа к CRUD-компонентам.
    Пример: db.user.get_users(), db.post.add_post()
    """

    def __init__(self):
        self.ad_creative: AdCreativeCrud = AdCreativeCrud()
        self.ad_purchase: AdPurchaseCrud = AdPurchaseCrud()
        self.ad_tag: AdTagCrud = AdTagCrud()
        self.bot_post: BotPostCrud = BotPostCrud()
        self.channel: ChannelCrud = ChannelCrud()
        self.channel_bot_captcha: ChannelCaptchaMessageCrud = ChannelCaptchaMessageCrud()
        self.channel_bot_hello: ChannelHelloMessageCrud = ChannelHelloMessageCrud()
        self.channel_bot_settings: ChannelBotSettingCrud = ChannelBotSettingCrud()
        self.exchange_rate: ExchangeRateCrud = ExchangeRateCrud()
        self.mt_client: MtClientCrud = MtClientCrud()
        self.mt_client_channel: MtClientChannelCrud = MtClientChannelCrud()
        self.novastat: NovaStatCrud = NovaStatCrud()
        self.novastat_cache: NovaStatCacheCrud = NovaStatCacheCrud()
        self.payment: PaymentCrud = PaymentCrud()
        self.payment_link: PaymentLinkCrud = PaymentLinkCrud()
        self.post: PostCrud = PostCrud()
        self.promo: PromoCrud = PromoCrud()
        self.published_post: PublishedPostCrud = PublishedPostCrud()
        self.purchase: PurchaseCrud = PurchaseCrud()
        self.stats: StatsCrud = StatsCrud()
        self.story: StoryCrud = StoryCrud()
        self.user: UserCrud = UserCrud()
        self.user_bot: UserBotCrud = UserBotCrud()
        self.user_folder: UserFolderCrud = UserFolderCrud()

    @staticmethod
    async def create_tables():
        """
        Создает таблицы в базе данных, если они не существуют.
        """
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


db = Database()
