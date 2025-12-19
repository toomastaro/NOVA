"""
Модуль клавиатур для панели администратора.
Обеспечивает навигацию и управление сессиями, каналами и промокодами.
"""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.utils.lang.language import text


class InlineAdmin(InlineKeyboardBuilder):
    """Клавиатуры для административных функций бота"""

    @classmethod
    def admin(cls):
        """
        Главное меню администратора.
        Все кнопки выстроены в один столбик.
        """
        kb = cls()

        kb.button(text="👤 Сессии", callback_data="Admin|session")
        kb.button(text="📺 Каналы", callback_data="AdminChannels|list|0")
        kb.button(text="📩 Рассылка", callback_data="Admin|mail")
        kb.button(text="🤖 Боты", callback_data="AdminBots|list|0")
        kb.button(text="👥 Админы", callback_data="AdminUsers|list|0")
        kb.button(text="🎁 Создать промокод", callback_data="Admin|promo")
        kb.button(text="🦋 Рекламные ссылки", callback_data="Admin|ads")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_sessions(cls, clients: list = None, orphaned_sessions: list = None):
        """
        Меню управления сессиями MTProto.

        Аргументы:
            clients (list): Список активных клиентов.
            orphaned_sessions (list): Список файлов сессий без записи в БД.
        """
        kb = cls()

        if clients or orphaned_sessions:
            if orphaned_sessions:
                for session_file in orphaned_sessions:
                    kb.button(
                        text=f"❓ {session_file}",
                        callback_data=f"AdminSession|add_orphan|{session_file}",
                    )

            if clients:
                for client in clients:
                    status_emoji = "✅" if client.is_active else "🔴"
                    if client.status == "RESETTING":
                        status_emoji = "🔄"
                    elif client.status == "TEMP_BLOCKED":
                        status_emoji = "⏳"

                    kb.button(
                        text=f"{status_emoji} {client.alias or client.id}",
                        callback_data=f"AdminSession|manage|{client.id}",
                    )
            kb.adjust(1)

            kb.row(
                InlineKeyboardButton(
                    text=text("back:button"), callback_data="Admin|session"
                )
            )
        else:
            kb.button(text="Свои", callback_data="AdminSession|internal")
            kb.button(text="Внешние", callback_data="AdminSession|external")
            kb.button(text="🔍 Сканировать", callback_data="AdminSession|scan")
            kb.button(text=text("add:button"), callback_data="AdminSession|add")
            kb.button(text=text("back:button"), callback_data="Admin|back")
            kb.adjust(1)

        return kb.as_markup()

    @classmethod
    def admin_client_manage(cls, client_id: int):
        """
        Меню управления конкретным клиентом.

        Аргументы:
            client_id (int): Идентификатор клиента.
        """
        kb = cls()
        kb.button(
            text="🔄 Проверить состояние / Активировать",
            callback_data=f"AdminSession|check_health|{client_id}",
        )
        kb.button(
            text="🔄 Сбросить клиента", callback_data=f"AdminSession|reset_ask|{client_id}"
        )
        kb.button(text=text("back:button"), callback_data="AdminSession|back_to_list")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_client_reset_confirm(cls, client_id: int):
        """
        Подтверждение сброса клиента.

        Аргументы:
            client_id (int): Идентификатор клиента.
        """
        kb = cls()
        kb.button(
            text="⚠️ Подтвердить сброс",
            callback_data=f"AdminSession|reset_confirm|{client_id}",
        )
        kb.button(text="Отмена", callback_data=f"AdminSession|manage|{client_id}")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_session_pool_select(cls):
        """Выбор пула для новой сессии"""
        kb = cls()
        kb.button(
            text="Свой клиент (Внутренний)",
            callback_data="AdminSession|pool_select|internal",
        )
        kb.button(
            text="Внешний (NovaStat)", callback_data="AdminSession|pool_select|external"
        )
        kb.button(text=text("back:button"), callback_data="AdminSession|cancel")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_orphan_pool_select(cls, session_file: str):
        """
        Выбор пула для найденного файла сессии.

        Аргументы:
            session_file (str): Имя файла сессии.
        """
        kb = cls()
        kb.button(
            text="Свой клиент (Внутренний)",
            callback_data=f"AdminSession|orphan_pool|internal|{session_file}",
        )
        kb.button(
            text="Внешний (NovaStat)",
            callback_data=f"AdminSession|orphan_pool|external|{session_file}",
        )
        kb.button(text=text("back:button"), callback_data="AdminSession|back_to_main")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_channels_list(cls, channels: list, offset: int, total: int):
        """
        Клавиатура со списком каналов и пагинацией.

        Аргументы:
            channels (list): Список каналов для текущей страницы.
            offset (int): Смещение для пагинации.
            total (int): Общее количество каналов.
        """
        kb = cls()

        # Кнопки каналов
        for channel in channels:
            status_emoji = "✅" if channel.subscribe else "❌"
            kb.button(
                text=f"{status_emoji} {channel.title[:30]}",
                callback_data=f"AdminChannels|view|{channel.id}",
            )

        kb.adjust(1)

        # Навигация
        nav_buttons = []

        # Кнопка "Назад" (предыдущая страница)
        if offset > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"AdminChannels|list|{max(0, offset - 10)}",
                )
            )

        # Кнопка "Вперед" (следующая страница)
        if offset + 10 < total:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ➡️", callback_data=f"AdminChannels|list|{offset + 10}"
                )
            )

        if nav_buttons:
            kb.row(*nav_buttons)

        # Кнопки действий
        kb.row(
            InlineKeyboardButton(text="🔍 Поиск", callback_data="AdminChannels|search")
        )
        kb.row(InlineKeyboardButton(text="◀️ В меню", callback_data="Admin|back"))

        return kb.as_markup()

    @classmethod
    def admin_channel_details(cls, channel_id: int):
        """
        Клавиатура для деталей канала.

        Аргументы:
            channel_id (int): Идентификатор канала.
        """
        kb = cls()

        kb.button(text="◀️ К списку", callback_data="AdminChannels|list|0")

        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_bots_list(cls, bots: list, offset: int, total: int):
        """Список всех ботов системы."""
        kb = cls()
        for bot in bots:
            kb.button(
                text=f"{bot.title} (@{bot.username})",
                callback_data=f"AdminBots|view|{bot.id}",
            )
        kb.adjust(1)
        
        nav = []
        if offset > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"AdminBots|list|{max(0, offset-10)}"))
        if offset + 10 < total:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"AdminBots|list|{offset+10}"))
        if nav:
            kb.row(*nav)
        
        kb.row(InlineKeyboardButton(text="◀️ В меню", callback_data="Admin|back"))
        return kb.as_markup()

    @classmethod
    def admin_bot_details(cls, bot_id: int):
        """Детали бота."""
        kb = cls()
        kb.button(text="◀️ К списку", callback_data="AdminBots|list|0")
        kb.adjust(1)
        return kb.as_markup()

    @classmethod
    def admin_users_list(cls, users: list, offset: int, total: int):
        """Список всех пользователей."""
        kb = cls()
        for user in users:
            kb.button(
                text=f"ID: {user.id}",
                callback_data=f"AdminUsers|view|{user.id}",
            )
        kb.adjust(1)

        nav = []
        if offset > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"AdminUsers|list|{max(0, offset-10)}"))
        if offset + 10 < total:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"AdminUsers|list|{offset+10}"))
        if nav:
            kb.row(*nav)

        kb.row(InlineKeyboardButton(text="◀️ В меню", callback_data="Admin|back"))
        return kb.as_markup()

    @classmethod
    def admin_user_details(cls, user_id: int):
        """Детали пользователя."""
        kb = cls()
        kb.button(text="◀️ К списку", callback_data="AdminUsers|list|0")
        kb.adjust(1)
        return kb.as_markup()
