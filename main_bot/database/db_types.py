"""
Модуль общих типов и перечислений базы данных.

Содержит перечисления (Enum) для статусов, типов оплаты, сервисов
и других сущностей, используемых в моделях и бизнес-логике.
"""

from enum import Enum


class FolderType(str, Enum):
    """Тип папки пользователя."""

    BOT = "BOTS"
    CHANNEL = "CHANNELS"

    def __str__(self):
        return self.value


class PaymentMethod(str, Enum):
    """Способ оплаты."""

    CRYPTO_BOT = "CRYPTO_BOT"
    STARS = "STARS"
    BALANCE = "BALANCE"
    PLATEGA = "PLATEGA"

    def __str__(self):
        return self.value


class Service(str, Enum):
    """Тип услуги."""

    POSTING = "POSTING"
    STORIES = "STORIES"
    BOTS = "BOTS"

    def __str__(self):
        return self.value


class Status(str, Enum):
    """Общий статус сущности."""

    READY = "READY"
    PENDING = "PENDING"
    FINISH = "FINISH"
    ERROR = "ERROR"
    DELETED = "DELETED"

    def __str__(self):
        return self.value


class AdPricingType(str, Enum):
    """Тип оплаты рекламы."""

    CPL = "CPL"  # Cost Per Lead (за подписчика)
    CPS = "CPS"  # Cost Per Sale (за продажу) - резерв
    FIXED = "FIXED"

    def __str__(self):
        return self.value


class AdTargetType(str, Enum):
    """Тип цели рекламы."""

    CHANNEL = "CHANNEL"
    BOT = "BOT"
    EXTERNAL = "EXTERNAL"
    UNTOUCHED = "UNTOUCHED"

    def __str__(self):
        return self.value
