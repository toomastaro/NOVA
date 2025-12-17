from aiogram import Bot
from main_bot.database.user.model import User
from main_bot.utils.lang.language import text


async def get_report_signatures(user: User, report_type: str, bot: Bot) -> str:
    """
    Генерирует текст подписей для отчетов.

    :param user: Объект пользователя
    :param report_type: 'cpm' или 'exchange'
    :param bot: Объект бота (нужен для username)
    :return: Текст подписей (с отступами)
    """
    signatures = []

    # 1. Подпись CPM / Обмена
    if report_type == "cpm":
        if user.cpm_signature_active:
            sig_text = user.cpm_signature_text or text("default:cpm_signature")
            signatures.append(sig_text)

    elif report_type == "exchange":
        if user.exchange_signature_active:
            sig_text = user.exchange_signature_text or text(
                "default:exchange_signature"
            )
            signatures.append(sig_text)

    # 2. Реферальная подпись (общая для обоих типов)
    if user.referral_signature_active:
        ref_text = user.referral_signature_text or text("default:referral_signature")

        # Получаем username бота
        bot_info = await bot.get_me()
        bot_username = bot_info.username

        ref_link = f"https://t.me/{bot_username}?start={user.id}"

        # Формируем ссылку - оборачиваем текст в HTML ссылку
        signatures.append(f"<a href='{ref_link}'>{ref_text}</a>")

    if not signatures:
        return ""

    # Объединяем подписи, добавляя отступ сверху
    return "\n\n" + "\n\n".join(signatures)
