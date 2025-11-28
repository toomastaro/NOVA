from enum import Enum


# Упрощаем FolderType - теперь только для каналов
# Для обратной совместимости оставляем enum, но используем только CHANNEL
class FolderType(str, Enum):
    CHANNEL = "CHANNELS"
    # BOT = "BOTS"  # Убрано - теперь папки только для каналов

    def __str__(self):
        return self.value


class PaymentMethod(str, Enum):
    CRYPTO_BOT = "CRYPTO_BOT"
    STARS = "STARS"
    BALANCE = "BALANCE"

    def __str__(self):
        return self.value


class Service(str, Enum):
    POSTING = "POSTING"
    STORIES = "STORIES"
    BOTS = "BOTS"

    def __str__(self):
        return self.value


class Status(str, Enum):
    READY = "READY"
    PENDING = "PENDING"
    FINISH = "FINISH"
    ERROR = "ERROR"

    def __str__(self):
        return self.value