"""
Базовые утилиты и хелперы для клавиатур.
"""


def _parse_button(button_text: str) -> tuple[str, str]:
    """Парсит кнопку, поддерживая разделители: —, --, -"""
    # Пробуем разделители в порядке приоритета: — (длинное тире), -- (двойной дефис), - (одинарный дефис)
    for separator in ["—", "--", "-"]:
        if separator in button_text:
            parts = button_text.split(separator, 1)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
    # Если ни один разделитель не найден, возвращаем пустую ссылку
    return button_text.strip(), ""
