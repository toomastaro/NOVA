from enum import Enum


class FolderType(str, Enum):
    BOT = "BOTS"
    CHANNEL = "CHANNELS"

    def __str__(self):
        return self.value


class PaymentMethod(str, Enum):
    CRYPTO_BOT = "CRYPTO_BOT"
    STARS = "STARS"
    BALANCE = "BALANCE"
    PLATEGA = "PLATEGA"

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


class AdPricingType(str, Enum):
    CPL = "CPL"
    CPS = "CPS"
    FIXED = "FIXED"

    def __str__(self):
        return self.value


class AdTargetType(str, Enum):
    CHANNEL = "CHANNEL"
    BOT = "BOT"
    EXTERNAL = "EXTERNAL"
    UNTOUCHED = "UNTOUCHED"

    def __str__(self):
        return self.value
