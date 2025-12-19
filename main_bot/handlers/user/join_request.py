"""
Модуль обработки заявок на вступление.

Содержит:
- Отслеживание рекламных лидов через заявки на вступление
- Проверку маппинга инвайт-ссылок к рекламным закупкам
"""

import logging

from aiogram import Router, types
from sqlalchemy import select

from main_bot.database.ad_purchase.model import AdPurchaseLinkMapping
from main_bot.database.db import db
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Заявка на вступление: трекинг лида")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def on_join_request(request: types.ChatJoinRequest) -> None:
    """
    Обработка заявок на вступление для отслеживания рекламных лидов.
    Проверяет invite_link заявки и сопоставляет его с рекламной закупкой.

    Аргументы:
        request (types.ChatJoinRequest): Объект заявки на вступление.
    """
    if not request.invite_link:
        return

    user_id = request.from_user.id
    invite_link = request.invite_link.invite_link

    logger.info(
        "Получена заявка на вступление от %s по ссылке %s", user_id, invite_link
    )

    try:
        # Поиск маппинга ссылки к рекламной закупке
        query = select(AdPurchaseLinkMapping).where(
            AdPurchaseLinkMapping.invite_link == invite_link
        )
        mapping = await db.fetchrow(query)

        if mapping:
            logger.info(
                "Найден маппинг для ссылки %s: Закупка %s, Слот %s",
                invite_link,
                mapping.ad_purchase_id,
                mapping.slot_id,
            )
            result = await db.ad_purchase.add_lead(
                user_id=user_id,
                ad_purchase_id=mapping.ad_purchase_id,
                slot_id=mapping.slot_id,
                ref_param=f"req_{mapping.ad_purchase_id}_{mapping.slot_id}",
            )
            if result:
                logger.info("Лид ДОБАВЛЕН для пользователя %s", user_id)
            else:
                logger.info("Лид ПРОПУЩЕН (Дубликат) для пользователя %s", user_id)
        else:
            logger.info("Не найден маппинг для ссылки %s", invite_link)

    except Exception:
        logger.exception("Ошибка обработки заявки на вступление для трекинга лидов")


def get_router() -> Router:
    """
    Регистрация роутера для обработки заявок на вступление.

    Возвращает:
        Router: Роутер с зарегистрированным хендлером.
    """
    router = Router()
    router.chat_join_request.register(on_join_request)
    return router
