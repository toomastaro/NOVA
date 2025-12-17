"""
Модуль операций базы данных для рекламных закупок.

Содержит класс `AdPurchaseCrud` для управления закупками,
маппингом ссылок, лидами и подписками.
"""

from sqlalchemy import insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.ad_purchase.model import AdPurchase, AdPurchaseLinkMapping


class AdPurchaseCrud(DatabaseMixin):
    """
    Класс для работы с рекламными закупками (AdPurchase)
    и связанными сущностями (LinkMappings, Leads, Subscriptions).
    """

    async def create_purchase(self, **kwargs) -> int:
        """
        Создает новую рекламную закупку.

        Аргументы:
            **kwargs: Поля модели AdPurchase.

        Возвращает:
            int: ID созданной закупки.
        """
        query = insert(AdPurchase).values(**kwargs).returning(AdPurchase.id)
        return await self.fetchrow(query, commit=True)

    async def get_purchase(self, purchase_id: int) -> AdPurchase | None:
        """
        Получает рекламную закупку по ID.

        Аргументы:
            purchase_id (int): ID закупки.

        Возвращает:
            AdPurchase | None: Объект закупки или None.
        """
        query = select(AdPurchase).where(AdPurchase.id == purchase_id)
        return await self.fetchrow(query)

    async def get_user_purchases(self, owner_id: int) -> list[AdPurchase]:
        """
        Получает список всех закупок пользователя (кроме удаленных).

        Аргументы:
            owner_id (int): ID владельца.

        Возвращает:
            list[AdPurchase]: Список закупок.
        """
        query = select(AdPurchase).where(
            AdPurchase.owner_id == owner_id, AdPurchase.status != "deleted"
        )
        return await self.fetch(query)

    async def upsert_link_mapping(
        self, ad_purchase_id: int, slot_id: int, **kwargs
    ) -> None:
        """
        Обновляет или создает привязку ссылки к слоту (UPSERT).

        Аргументы:
            ad_purchase_id (int): ID закупки.
            slot_id (int): ID слота.
            **kwargs: Остальные поля для обновления/вставки.
        """
        query = select(AdPurchaseLinkMapping).where(
            AdPurchaseLinkMapping.ad_purchase_id == ad_purchase_id,
            AdPurchaseLinkMapping.slot_id == slot_id,
        )
        existing = await self.fetchrow(query)

        if existing:
            query = (
                update(AdPurchaseLinkMapping)
                .where(AdPurchaseLinkMapping.id == existing.id)
                .values(**kwargs)
            )
        else:
            query = insert(AdPurchaseLinkMapping).values(
                ad_purchase_id=ad_purchase_id, slot_id=slot_id, **kwargs
            )
        await self.execute(query)

    async def get_link_mappings(
        self, ad_purchase_id: int
    ) -> list[AdPurchaseLinkMapping]:
        """
        Получает список всех привязок ссылок для конкретной закупки.

        Аргументы:
            ad_purchase_id (int): ID закупки.

        Возвращает:
            list[AdPurchaseLinkMapping]: Список привязок.
        """
        query = select(AdPurchaseLinkMapping).where(
            AdPurchaseLinkMapping.ad_purchase_id == ad_purchase_id
        )
        return await self.fetch(query)

    async def update_purchase_status(self, purchase_id: int, status: str) -> None:
        """
        Обновляет статус закупки.

        Аргументы:
            purchase_id (int): ID закупки.
            status (str): Новый статус.
        """
        query = (
            update(AdPurchase).where(AdPurchase.id == purchase_id).values(status=status)
        )
        await self.execute(query)

    async def ensure_invite_links(
        self, ad_purchase_id: int, bot
    ) -> tuple[list[AdPurchaseLinkMapping], list[str]]:
        """
        Гарантирует наличие пригласительных ссылок для всех каналов в закупке.

        Если ссылка отсутствует, создает новую постоянную ссылку через API Telegram.

        Аргументы:
            ad_purchase_id (int): ID закупки.
            bot: Экземпляр бота (aiogram).

        Возвращает:
            tuple[list, list]: (UpdatedMappings, Errors).
        """
        import logging

        from main_bot.database.db_types import AdTargetType

        logger = logging.getLogger(__name__)
        mappings = await self.get_link_mappings(ad_purchase_id)
        updated_mappings = []
        errors = []

        for m in mappings:
            if (
                m.target_type == AdTargetType.CHANNEL
                and m.track_enabled
                and m.target_channel_id
                and not m.invite_link
            ):
                try:
                    # Создаем ПОСТОЯННУЮ ссылку для отслеживания рекламы
                    invite = await bot.create_chat_invite_link(
                        chat_id=m.target_channel_id,
                        name=f"AdPurchase #{ad_purchase_id} Slot {m.slot_id}",
                        creates_join_request=True,
                        # БЕЗ member_limit - ссылка постоянная
                    )

                    # Обновляем БД
                    query = (
                        update(AdPurchaseLinkMapping)
                        .where(AdPurchaseLinkMapping.id == m.id)
                        .values(invite_link=invite.invite_link)
                    )
                    await self.execute(query)

                    # Обновляем локальный объект
                    m.invite_link = invite.invite_link
                    logger.info(
                        f"Создана ссылка для закупки {ad_purchase_id}, "
                        f"слот {m.slot_id}, канал {m.target_channel_id}: {invite.invite_link}"
                    )
                except Exception as e:
                    error_msg = f"Ошибка создания ссылки для канала {m.target_channel_id}: {str(e)}"
                    logger.error(
                        f"Ошибка создания ссылки для закупки {ad_purchase_id}, слот {m.slot_id}: {e}"
                    )
                    errors.append(error_msg)

            updated_mappings.append(m)

        return updated_mappings, errors

    async def add_lead(
        self, user_id: int, ad_purchase_id: int, slot_id: int, ref_param: str
    ) -> bool:
        """
        Регистрирует новый лид (переход по ссылке).

        Если лид уже существует, возвращает False.

        Аргументы:
            user_id (int): ID пользователя.
            ad_purchase_id (int): ID закупки.
            slot_id (int): ID слота.
            ref_param (str): Реферальный параметр.

        Возвращает:
            bool: True, если лид успешно создан.
        """
        from main_bot.database.ad_purchase.model import AdLead

        # Проверка дубликатов
        query = select(AdLead).where(
            AdLead.user_id == user_id, AdLead.ad_purchase_id == ad_purchase_id
        )
        existing = await self.fetchrow(query)

        if existing:
            return False

        # Создание нового лида
        query = insert(AdLead).values(
            user_id=user_id,
            ad_purchase_id=ad_purchase_id,
            slot_id=slot_id,
            ref_param=ref_param,
        )
        await self.execute(query)
        return True

    async def get_leads_count(self, ad_purchase_id: int) -> int:
        """
        Возвращает общее количество лидов для закупки.
        """
        from sqlalchemy import func

        from main_bot.database.ad_purchase.model import AdLead

        query = select(func.count(AdLead.id)).where(
            AdLead.ad_purchase_id == ad_purchase_id
        )
        result = await self.fetchrow(query)
        return result if result else 0

    async def get_leads_by_slot(self, ad_purchase_id: int, slot_id: int) -> list:
        """
        Возвращает список всех лидов для конкретного слота.
        """
        from main_bot.database.ad_purchase.model import AdLead

        query = select(AdLead).where(
            AdLead.ad_purchase_id == ad_purchase_id, AdLead.slot_id == slot_id
        )
        return await self.fetch(query)

    async def add_subscription(
        self,
        user_id: int,
        channel_id: int,
        ad_purchase_id: int,
        slot_id: int,
        invite_link: str,
    ) -> bool:
        """
        Добавляет или активирует подписку пользователя.

        Если подписка уже была (статус 'left'), она активируется заново.

        Возвращает:
            bool: True, если подписка добавлена или активирована.
        """

        from main_bot.database.ad_purchase.model import AdSubscription

        # Проверка существования
        query = select(AdSubscription).where(
            AdSubscription.user_id == user_id,
            AdSubscription.channel_id == channel_id,
            AdSubscription.ad_purchase_id == ad_purchase_id,
        )
        existing = await self.fetchrow(query)

        if existing:
            if existing.status != "active":
                # Реактивация
                query = (
                    update(AdSubscription)
                    .where(AdSubscription.id == existing.id)
                    .values(status="active", left_timestamp=None)
                )
                await self.execute(query)
                return True
            return False

        # Создание новой
        query = insert(AdSubscription).values(
            user_id=user_id,
            channel_id=channel_id,
            ad_purchase_id=ad_purchase_id,
            slot_id=slot_id,
            invite_link=invite_link,
            status="active",
        )
        await self.execute(query)
        return True

    async def update_subscription_status(
        self, user_id: int, channel_id: int, status: str
    ) -> None:
        """
        Обновляет статус подписки (например, при выходе пользователя).

        Аргументы:
            user_id (int): ID пользователя.
            channel_id (int): ID канала.
            status (str): Новый статус ('left', 'kicked', etc.).
        """
        import time

        from main_bot.database.ad_purchase.model import AdSubscription

        values = {"status": status}
        if status == "left":
            values["left_timestamp"] = int(time.time())

        query = (
            update(AdSubscription)
            .where(
                AdSubscription.user_id == user_id,
                AdSubscription.channel_id == channel_id,
            )
            .values(**values)
        )
        await self.execute(query)

    async def get_subscriptions_count(
        self, ad_purchase_id: int, from_ts: int = None, to_ts: int = None
    ) -> int:
        """
        Возвращает количество подписок для закупки, с опциональной фильтрацией по времени.
        """
        from sqlalchemy import func

        from main_bot.database.ad_purchase.model import AdSubscription

        query = select(func.count(AdSubscription.id)).where(
            AdSubscription.ad_purchase_id == ad_purchase_id
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        result = await self.fetchrow(query)
        return result if result else 0

    async def get_subscriptions_by_channel(
        self,
        ad_purchase_id: int,
        channel_id: int,
        from_ts: int = None,
        to_ts: int = None,
    ) -> list:
        """
        Возвращает список подписок для конкретного канала в рамках закупки.
        """
        from main_bot.database.ad_purchase.model import AdSubscription

        query = select(AdSubscription).where(
            AdSubscription.ad_purchase_id == ad_purchase_id,
            AdSubscription.channel_id == channel_id,
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        return await self.fetch(query)

    async def get_subscriptions_by_slot(
        self, ad_purchase_id: int, slot_id: int, from_ts: int = None, to_ts: int = None
    ) -> list:
        """
        Возвращает список подписок для конкретного слота.
        """
        from main_bot.database.ad_purchase.model import AdSubscription

        query = select(AdSubscription).where(
            AdSubscription.ad_purchase_id == ad_purchase_id,
            AdSubscription.slot_id == slot_id,
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        return await self.fetch(query)

    async def process_join_event(
        self, channel_id: int, user_id: int, invite_link: str
    ) -> bool:
        """
        Обрабатывает событие вступления и создает подписку, если ссылка соответствует закупке.
        Возвращает True, если подписка создана.
        """
        # Find mapping by invite_link
        query = select(AdPurchaseLinkMapping).where(
            AdPurchaseLinkMapping.invite_link == invite_link
        )
        mapping = await self.fetchrow(query)

        if not mapping:
            return False

        # Ensure Lead exists (for cases where ChatJoinRequest didn't fire or was missed)
        # We record a lead because a join implies intent (and success).
        await self.add_lead(
            user_id=user_id,
            ad_purchase_id=mapping.ad_purchase_id,
            slot_id=mapping.slot_id,
            ref_param=f"auto_{mapping.ad_purchase_id}_{mapping.slot_id}",  # Synthetic ref param for direct joins
        )

        # Add subscription
        return await self.add_subscription(
            user_id=user_id,
            channel_id=channel_id,
            ad_purchase_id=mapping.ad_purchase_id,
            slot_id=mapping.slot_id,
            invite_link=invite_link,
        )

    async def get_global_stats(self, from_ts: int = None, to_ts: int = None) -> dict:
        """
        Получает глобальную статистику по всем закупкам.

        Аргументы:
            from_ts (int): Начальная метка времени.
            to_ts (int): Конечная метка времени.

        Возвращает:
            dict: {active_purchases, total_leads, total_subscriptions}
        """
        from sqlalchemy import func

        from main_bot.database.ad_purchase.model import AdLead, AdSubscription

        # Count active purchases
        query = select(func.count(AdPurchase.id)).where(AdPurchase.status == "active")
        active_purchases = await self.fetchrow(query)

        # Count total leads
        query = select(func.count(AdLead.id))
        if from_ts:
            query = query.where(AdLead.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdLead.created_timestamp <= to_ts)
        total_leads = await self.fetchrow(query)

        # Count total subscriptions
        query = select(func.count(AdSubscription.id))
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        total_subs = await self.fetchrow(query)

        return {
            "active_purchases": active_purchases if active_purchases else 0,
            "total_leads": total_leads if total_leads else 0,
            "total_subscriptions": total_subs if total_subs else 0,
        }

    async def get_top_purchases(
        self, from_ts: int = None, to_ts: int = None, limit: int = 5
    ) -> list:
        """
        Получает топ закупок по количеству подписок.
        """
        from sqlalchemy import func

        from main_bot.database.ad_purchase.model import AdSubscription

        query = select(
            AdPurchase.id,
            AdPurchase.comment,
            func.count(AdSubscription.id).label("subs_count"),
        ).join(AdSubscription, AdPurchase.id == AdSubscription.ad_purchase_id)

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        query = (
            query.group_by(AdPurchase.id, AdPurchase.comment)
            .order_by(func.count(AdSubscription.id).desc())
            .limit(limit)
        )

        return await self.fetch(query)

    async def get_top_creatives(
        self, from_ts: int = None, to_ts: int = None, limit: int = 5
    ) -> list:
        """
        Получает топ креативов по количеству подписок.
        """
        from sqlalchemy import func

        from main_bot.database.ad_creative.model import AdCreative
        from main_bot.database.ad_purchase.model import AdSubscription

        query = (
            select(
                AdCreative.id,
                AdCreative.name,
                func.count(AdSubscription.id).label("subs_count"),
            )
            .join(AdPurchase, AdCreative.id == AdPurchase.creative_id)
            .join(AdSubscription, AdPurchase.id == AdSubscription.ad_purchase_id)
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        query = (
            query.group_by(AdCreative.id, AdCreative.name)
            .order_by(func.count(AdSubscription.id).desc())
            .limit(limit)
        )

        return await self.fetch(query)

    async def get_top_channels(
        self, from_ts: int = None, to_ts: int = None, limit: int = 5
    ) -> list:
        """
        Получает топ каналов по количеству подписок.
        """
        from sqlalchemy import func

        from main_bot.database.ad_purchase.model import AdSubscription

        query = select(
            AdSubscription.channel_id, func.count(AdSubscription.id).label("subs_count")
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        query = (
            query.group_by(AdSubscription.channel_id)
            .order_by(func.count(AdSubscription.id).desc())
            .limit(limit)
        )

        return await self.fetch(query)

    async def get_user_global_stats(
        self, user_id: int, from_ts: int = None, to_ts: int = None
    ) -> dict:
        """
        Получает глобальную статистику рекламных закупок пользователя.
        """
        from sqlalchemy import func

        from main_bot.database.ad_purchase.model import AdLead, AdSubscription

        # Count active purchases for this user
        query = select(func.count(AdPurchase.id)).where(
            AdPurchase.owner_id == user_id, AdPurchase.status == "active"
        )
        active_purchases = await self.fetchrow(query)

        # Count total leads for user's purchases
        query = (
            select(func.count(AdLead.id))
            .join(AdPurchase, AdLead.ad_purchase_id == AdPurchase.id)
            .where(AdPurchase.owner_id == user_id)
        )

        if from_ts:
            query = query.where(AdLead.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdLead.created_timestamp <= to_ts)
        total_leads = await self.fetchrow(query)

        # Count total subscriptions for user's purchases
        query = (
            select(func.count(AdSubscription.id))
            .join(AdPurchase, AdSubscription.ad_purchase_id == AdPurchase.id)
            .where(AdPurchase.owner_id == user_id)
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        total_subs = await self.fetchrow(query)

        return {
            "active_purchases": active_purchases if active_purchases else 0,
            "total_leads": total_leads if total_leads else 0,
            "total_subscriptions": total_subs if total_subs else 0,
        }

    async def get_user_top_purchases(
        self, user_id: int, from_ts: int = None, to_ts: int = None, limit: int = 5
    ) -> list:
        """
        Получает топ закупок пользователя по количеству подписок.
        """
        from sqlalchemy import func

        from main_bot.database.ad_purchase.model import AdSubscription

        query = (
            select(
                AdPurchase.id,
                AdPurchase.comment,
                func.count(AdSubscription.id).label("subs_count"),
            )
            .join(AdSubscription, AdPurchase.id == AdSubscription.ad_purchase_id)
            .where(AdPurchase.owner_id == user_id)
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        query = (
            query.group_by(AdPurchase.id, AdPurchase.comment)
            .order_by(func.count(AdSubscription.id).desc())
            .limit(limit)
        )

        return await self.fetch(query)

    async def get_user_top_creatives(
        self, user_id: int, from_ts: int = None, to_ts: int = None, limit: int = 5
    ) -> list:
        """
        Получает топ креативов пользователя по количеству подписок.
        """
        from sqlalchemy import func

        from main_bot.database.ad_creative.model import AdCreative
        from main_bot.database.ad_purchase.model import AdSubscription

        query = (
            select(
                AdCreative.id,
                AdCreative.name,
                func.count(AdSubscription.id).label("subs_count"),
            )
            .join(AdPurchase, AdCreative.id == AdPurchase.creative_id)
            .join(AdSubscription, AdPurchase.id == AdSubscription.ad_purchase_id)
            .where(AdCreative.owner_id == user_id)
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        query = (
            query.group_by(AdCreative.id, AdCreative.name)
            .order_by(func.count(AdSubscription.id).desc())
            .limit(limit)
        )

        return await self.fetch(query)

    async def get_user_top_channels(
        self, user_id: int, from_ts: int = None, to_ts: int = None, limit: int = 5
    ) -> list:
        """
        Получает топ каналов пользователя по количеству подписок.
        """
        from sqlalchemy import func

        from main_bot.database.ad_purchase.model import AdSubscription

        query = (
            select(
                AdSubscription.channel_id,
                func.count(AdSubscription.id).label("subs_count"),
            )
            .join(AdPurchase, AdSubscription.ad_purchase_id == AdPurchase.id)
            .where(AdPurchase.owner_id == user_id)
        )

        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)

        query = (
            query.group_by(AdSubscription.channel_id)
            .order_by(func.count(AdSubscription.id).desc())
            .limit(limit)
        )

        return await self.fetch(query)
