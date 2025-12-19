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


async def _fetch_json(
    url: str,
    method: str = "GET",
    headers: Dict[str, str] = None,
    json_data: Any = None,
    timeout: int = 10,
) -> Any:
    """Вспомогательная функция для выполнения HTTP запросов."""
    try:
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        return await response.json()
            elif method.upper() == "POST":
                async with session.post(
                    url,
                    headers=headers,
                    json=json_data,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as response:
                    if response.status == 200:
                        return await response.json()
            logger.warning(f"API {url} вернул статус: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка при запросе к {url}: {e}")
    return None


async def get_crypto_bot_usdt_rub_rate() -> float:
    """
    Получает актуальный курс USDT/RUB через API Crypto Bot.

    Возвращает:
        float: Курс обмена. 0 при ошибке.
    """
    api_token = os.getenv("CRYPTO_BOT_API_TOKEN") or os.getenv("CRYPTO_BOT_TOKEN")

    if not api_token:
        logger.error("CRYPTO_BOT_API_TOKEN не найден в переменных окружения")
        return 0

    url = "https://pay.crypt.bot/api/getExchangeRates"
    headers = {"Crypto-Pay-API-Token": api_token}

    data = await _fetch_json(url, headers=headers)
    if data and data.get("ok"):
        for rate in data.get("result", []):
            if rate.get("source") == "USDT" and rate.get("target") == "RUB":
                return float(rate.get("rate"))

    return 0


async def get_best_change_usdt_rub_rate() -> Dict[str, float]:
    """
    Получает курсы обмена USDT/RUB с API BestChange.

    Возвращает:
        Dict[str, float]: Словарь с курсами (sell, buy, average).
    """
    api_key = os.getenv("BEST_EXCHANGE_API")
    if not api_key:
        logger.warning("BEST_EXCHANGE_API не найден")
        return {"sell": 0, "buy": 0, "average": 0}

    sources_data = get_rates_sources_from_json()
    if not sources_data:
        return {"sell": 0, "buy": 0, "average": 0}

    try:
        # Пытаемся найти данные для USDT/RUB более надежно
        usdt_rub_source = next(
            (s for s in sources_data if s.get("name") == "USDT-RUB"), sources_data[2]
        )
        usdt, rub = usdt_rub_source["api_data"].values()
        usdt_ids = [x["id"] for x in usdt]
        rub_ids = [x["id"] for x in rub]
    except Exception as e:
        logger.error(f"Ошибка парсинга источников BestChange: {e}")
        return {"sell": 0, "buy": 0, "average": 0}

    sell_pairs = [f"{usdt_id}-{rub_id}" for usdt_id in usdt_ids for rub_id in rub_ids]
    buy_pairs = [f"{rub_id}-{usdt_id}" for rub_id in rub_ids for usdt_id in usdt_ids]
    pairs_str = "+".join(sell_pairs + buy_pairs)
    url = f"https://bestchange.app/v2/{api_key}/rates/{pairs_str}"

    data = await _fetch_json(url)
    if data and "rates" in data:
        rates_data = data["rates"]

        def calc_avg_rate(pairs):
            vals = []
            for p in pairs:
                if p in rates_data and isinstance(rates_data[p], list):
                    vals.extend([float(it["rate"]) for it in rates_data[p] if "rate" in it])
            return sum(vals) / len(vals) if vals else 0

        sell_raw = calc_avg_rate(sell_pairs)
        sell = 1 / sell_raw if sell_raw else 0
        buy = calc_avg_rate(buy_pairs)

        return {
            "sell": sell,
            "buy": buy,
            "average": ((sell + buy) / 2) if sell and buy else 0,
        }

    return {"sell": 0, "buy": 0, "average": 0}


async def get_p2p_bybit_usdt_rub_rate() -> Dict[str, float]:
    """
    Получает P2P курсы USDT/RUB с API Bybit.

    Возвращает:
        Dict[str, float]: Словарь с курсами (sell, buy, average).
    """
    url = "https://api2.bybit.com/fiat/otc/item/online"
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    base_payload = {
        "tokenId": "USDT",
        "currencyId": "RUB",
        "size": "20",
        "page": "1",
        "amount": "10000",
        "itemRegion": 2,
    }

    async def fetch_side(side: str):
        payload = {**base_payload, "side": side}
        data = await _fetch_json(url, method="POST", headers=headers, json_data=payload)
        if data:
            return [
                float(ad["price"])
                for ad in data.get("result", {}).get("items", [])
                if "price" in ad
            ]
        return []

    # Запускаем запросы для обеих сторон параллельно
    sell_rates, buy_rates = await asyncio.gather(fetch_side("0"), fetch_side("1"))

    sell = sum(sell_rates) / len(sell_rates) if sell_rates else 0
    buy = sum(buy_rates) / len(buy_rates) if buy_rates else 0

    return {
        "sell": sell,
        "buy": buy,
        "average": ((sell + buy) / 2) if sell and buy else 0,
    }


async def get_update_of_exchange_rates() -> Dict[int, float]:
    """
    Агрегирует курсы с разных источников параллельно.

    Возвращает:
        Dict[int, float]: Словарь с ID типа курса и значением.
    """
    results = await asyncio.gather(
        get_crypto_bot_usdt_rub_rate(),
        get_p2p_bybit_usdt_rub_rate(),
        get_best_change_usdt_rub_rate(),
    )

    crypto_rate, bybit_data, bc_data = results

    return {
        0: round(crypto_rate, 2),
        1: round(bybit_data["buy"], 2),
        2: round(bybit_data["sell"], 2),
        3: round(bybit_data["average"], 2),
        4: round(bc_data["buy"], 2),
        5: round(bc_data["sell"], 2),
        6: round(bc_data["average"], 2),
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
        with open(
            current_dir / "exchange_rate_data/exchange_rates.json",
            "r",
            encoding="utf-8",
        ) as file:
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
        with open(
            current_dir / "exchange_rate_data/rates_sources.json", "r", encoding="utf-8"
        ) as file:
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
