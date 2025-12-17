"""
Модуль для получения курсов валют (USDT/RUB) из различных источников (Crypto Bot, BestChange, Bybit).
"""

import asyncio
import json
import logging
import os
import pathlib
from typing import Any, Dict, List

import aiohttp
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Используем относительный путь от текущего файла
current_dir = pathlib.Path(__file__).parent.resolve()


async def get_crypto_bot_usdt_rub_rate() -> float:
    """
    Получает актуальный курс USDT/RUB через API Crypto Bot.

    Возвращает:
        float: Курс обмена. 0 при ошибке.
    """
    api_token = os.getenv('CRYPTO_BOT_API_TOKEN') or os.getenv('CRYPTO_BOT_TOKEN')

    if not api_token:
        logger.error("CRYPTO_BOT_API_TOKEN не найден в переменных окружения")
        return 0

    url = "https://pay.crypt.bot/api/getExchangeRates"

    headers = {
        "Crypto-Pay-API-Token": api_token,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                data = await response.json()

                if data.get('ok'):
                    for rate in data.get('result', []):
                        if rate.get('source') == 'USDT' and rate.get('target') == 'RUB':
                            return float(rate.get('rate'))
    except Exception as e:
        logger.error(f"Ошибка получения курсов Crypto Bot: {e}", exc_info=True)

    return 0


async def get_best_change_usdt_rub_rate() -> Dict[str, float]:
    """
    Получает курсы обмена USDT/RUB с API BestChange.

    Возвращает:
        Dict[str, float]: Словарь с ключами:
            - 'sell': средний курс продажи (USDT->RUB)
            - 'buy': средний курс покупки (RUB->USDT)
            - 'average': (sell + buy) / 2
    """
    api_key = os.getenv('BEST_EXCHANGE_API')
    if not api_key:
        logger.warning("BEST_EXCHANGE_API не найден в переменных окружения")
        return {'sell': 0, 'buy': 0, 'average': 0}

    sources_data = get_rates_sources_from_json()
    if not sources_data:
        return {'sell': 0, 'buy': 0, 'average': 0}

    # Безопасное получение данных, предполагая структуру JSON
    try:
        # sources_data[2] предполагается как USDT-RUB или подобное, лучше бы по ключу, но оставляем логику
        usdt, rub = sources_data[2]["api_data"].values()
        usdt_ids = [x["id"] for x in usdt]
        rub_ids = [x["id"] for x in rub]
    except (IndexError, KeyError, ValueError) as e:
        logger.error(f"Ошибка парсинга rates_sources.json: {e}")
        return {'sell': 0, 'buy': 0, 'average': 0}

    # Создаем пары: USDT->RUB (продажа) и RUB->USDT (покупка)
    sell_pairs = [f"{usdt_id}-{rub_id}" for usdt_id in usdt_ids for rub_id in rub_ids]
    buy_pairs = [f"{rub_id}-{usdt_id}" for rub_id in rub_ids for usdt_id in usdt_ids]

    pairs_str = "+".join(sell_pairs + buy_pairs)
    url = f"https://bestchange.app/v2/{api_key}/rates/{pairs_str}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.warning(f"BestChange API вернул статус: {response.status}")
                    return {'sell': 0, 'buy': 0, 'average': 0}

                data = await response.json()

                if isinstance(data, dict) and "rates" in data:
                    rates_data = data["rates"]

                    # Извлекаем курсы для пар продажи (USDT->RUB)
                    sell_rates = []
                    for pair_key in sell_pairs:
                        if pair_key in rates_data:
                            pair_rates = rates_data[pair_key]
                            if isinstance(pair_rates, list) and len(pair_rates) > 0:
                                # Извлекаем курс от каждого обменника
                                sell_rates.extend([float(item["rate"]) for item in pair_rates if "rate" in item])

                    # Извлекаем курсы для пар покупки (RUB->USDT)
                    buy_rates = []
                    for pair_key in buy_pairs:
                        if pair_key in rates_data:
                            pair_rates = rates_data[pair_key]
                            if isinstance(pair_rates, list) and len(pair_rates) > 0:
                                # Извлекаем курс от каждого обменника
                                buy_rates.extend([float(item["rate"]) for item in pair_rates if "rate" in item])

                    # Вычисляем средние значения

                    # Примечание: тут логика может быть специфичной для обратных курсов
                    sell = 1 / (sum(sell_rates) / len(sell_rates)) if sell_rates else 0
                    buy = sum(buy_rates) / len(buy_rates) if buy_rates else 0
                    average = ((sell + buy) / 2) if sell and buy else 0

                    return {
                        'sell': sell,
                        'buy': buy,
                        'average': average
                    }

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
            logger.error(f"Ошибка получения курсов BestChange: {e}")
            pass

    return {'sell': 0, 'buy': 0, 'average': 0}


async def get_p2p_bybit_usdt_rub_rate() -> Dict[str, float]:
    """
    Получает P2P курсы USDT/RUB с API Bybit.

    Возвращает:
        Dict[str, float]: Словарь с курсами (sell, buy, average).
    """

    url = "https://api2.bybit.com/fiat/otc/item/online"
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

    base_payload = {
        "userId": "", "tokenId": "USDT", "currencyId": "RUB",
        "payment": [], "size": "20", "page": "1", "amount": "10000",
        "authMaker": False, "canTrade": False, "itemRegion": 2
    }

    async def fetch_rates(side: str) -> list[float]:
        payload = {**base_payload, "side": side}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [float(ad["price"]) for ad in data.get("result", {}).get("items", [])
                                if isinstance(ad.get("price"), (int, float, str))]
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            logger.error(f"Ошибка получения курсов Bybit (side={side}): {e}")
            pass
        return []

    sell_rates = await fetch_rates("0")
    buy_rates = await fetch_rates("1")

    sell = sum(sell_rates) / len(sell_rates) if sell_rates else 0
    buy = sum(buy_rates) / len(buy_rates) if buy_rates else 0

    return {
        'sell': sell,
        'buy': buy,
        'average': ((sell + buy) / 2) if sell and buy else 0
    }


async def get_update_of_exchange_rates() -> Dict[int, float]:
    """
    Агрегирует курсы с разных источников.

    Возвращает:
        Dict[int, float]: Словарь с ID типа курса и значением.
    """
    best_change_data = await get_best_change_usdt_rub_rate()
    bybit_data = await get_p2p_bybit_usdt_rub_rate()

    return {
        0: round(await get_crypto_bot_usdt_rub_rate(), 2),
        1: round(bybit_data["buy"], 2),
        2: round(bybit_data["sell"], 2),
        3: round(bybit_data["average"], 2),
        4: round(best_change_data["buy"], 2),
        5: round(best_change_data["sell"], 2),
        6: round(best_change_data["average"], 2),
    }


async def format_exchange_rate_from_db(exchange_rates: List[Any]) -> Dict[int, float]:
    """
    Форматирует курсы из БД в словарь.

    Аргументы:
        exchange_rates (List[ExchangeRate]): Список объектов курса.

    Возвращает:
        Dict[int, float]: Словарь {id: rate}.
    """
    rtn = {}
    for er in exchange_rates:
        rtn[er.id] = round(er.rate, 2)
    return rtn


def get_exchange_rates_from_json() -> Any:
    """
    Чтение файла обменных курсов (exchange_rates.json).

    Возвращает:
        Any: Загруженные данные (список или словарь).
    """
    try:
        with open(current_dir / "exchange_rate_data/exchange_rates.json", "r", encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Ошибка чтения exchange_rates.json: {e}")
        return []


def get_rates_sources_from_json() -> Any:
    """
    Чтение настройки источников (rates_sources.json).

    Возвращает:
        Any: Загруженные данные (список или словарь).
    """
    try:
        with open(current_dir / "exchange_rate_data/rates_sources.json", "r", encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Ошибка чтения rates_sources.json: {e}")
        return []


if __name__ == "__main__":
    # Для локального теста
    logging.basicConfig(level=logging.INFO)

    async def test():
        rate_bybit = await get_p2p_bybit_usdt_rub_rate()
        logger.info(f"Bybit: {rate_bybit}")

        rate_crypto = await get_crypto_bot_usdt_rub_rate()
        logger.info(f"CryptoBot: {rate_crypto}")

        rate_bc = await get_best_change_usdt_rub_rate()
        logger.info(f"BestChange: {rate_bc}")


    asyncio.run(test())
