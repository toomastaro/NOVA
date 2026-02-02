"""
Модуль инлайн-календаря для выбора даты и времени планирования поста.
"""

import calendar
from datetime import datetime, timedelta
from typing import List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main_bot.utils.lang.language import text
from main_bot.utils.recent_times import get_recent_times


class InlineCalendar(InlineKeyboardBuilder):
    """
    Класс для генерации клавиатуры-календаря с выбором времени.
    """

    @classmethod
    async def create(
        cls,
        year: int = None,
        month: int = None,
        selected_date: datetime = None,
        user_id: int = None,
        data: str = "ChoicePublicationDate",
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру календаря.

        Args:
            year: Год для отображения.
            month: Месяц для отображения.
            selected_date: Уже выбранная дата.
            user_id: ID пользователя для получения последних времен.
            data: Префикс для callback_data.

        Returns:
            InlineKeyboardMarkup
        """
        now = datetime.now()
        if year is None:
            year = now.year
        if month is None:
            month = now.month
        if selected_date is None:
            selected_date = now

        kb = cls()

        # 1. Шапка: Месяц и Год
        month_name = text("other_month").get(str(month))
        kb.row(
            InlineKeyboardButton(
                text="⬅️", callback_data=f"{data}|prev_month|{year}|{month}"
            ),
            InlineKeyboardButton(
                text=f"📅 {month_name} {year}", callback_data="ignore"
            ),
            InlineKeyboardButton(
                text="➡️", callback_data=f"{data}|next_month|{year}|{month}"
            ),
        )

        # 2. Дни недели
        weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        kb.row(*[InlineKeyboardButton(text=d, callback_data="ignore") for d in weekdays])

        # 3. Сетка календаря
        month_calendar = calendar.monthcalendar(year, month)
        for week in month_calendar:
            days = []
            for day in week:
                if day == 0:
                    days.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
                else:
                    # Помечаем текущий/выбранный день
                    is_today = (
                        year == now.year and month == now.month and day == now.day
                    )
                    is_selected = (
                        year == selected_date.year
                        and month == selected_date.month
                        and day == selected_date.day
                    )

                    btn_text = str(day)
                    if is_selected:
                        btn_text = f"🔸{day}🔸"
                    elif is_today:
                        btn_text = f"•{day}•"

                    days.append(
                        InlineKeyboardButton(
                            text=btn_text,
                            callback_data=f"{data}|select_day|{year}|{month}|{day}",
                        )
                    )
            kb.row(*days)

        # 4. Выбор времени (Рекомендуемые пресеты)
        time_presets = ["09:00", "12:00", "15:00", "18:00", "21:00"]
        kb.row(
            *[
                InlineKeyboardButton(
                    text=f"⏰ {t}", callback_data=f"ChoicePublicationTime|{t}"
                )
                for t in time_presets
            ]
        )

        # 5. Последние 3 времени из Redis
        if user_id:
            recent_times = await get_recent_times(user_id)
            if recent_times:
                kb.row(
                    *[
                        InlineKeyboardButton(
                            text=f"⏰ {t}", callback_data=f"ChoicePublicationTime|{t}"
                        )
                        for t in recent_times
                    ]
                )

        # 6. Кнопка Назад
        kb.row(
            InlineKeyboardButton(
                text=text("back:button"), callback_data="FinishPostParams|cancel"
            )
        )

        return kb.as_markup()
