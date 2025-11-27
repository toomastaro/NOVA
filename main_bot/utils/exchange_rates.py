import asyncio
from datetime import datetime
import json
import os
from itertools import product

import aiohttp
from dotenv import load_dotenv
import requests

from main_bot.database.db import db

load_dotenv()

root_dir = "/app/main_bot/utils"


async def get_crypto_bot_usdt_rub_rate():
    api_token = os.getenv('CRYPTO_BOT_API_TOKEN')
    url = "https://pay.crypt.bot/api/getExchangeRates"

    headers = {
        "Crypto-Pay-API-Token": api_token,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()

            if data.get('ok'):
                for rate in data.get('result', []):
                    if rate.get('source') == 'USDT' and rate.get('target') == 'RUB':
                        return float(rate.get('rate'))

    return 0


async def get_best_change_usdt_rub_rate() -> dict[str, float | None]:
    """
    Get USDT/RUB exchange rates from BestChange API
    Returns: {
        'sell': average of all USDT->RUB rates,
        'buy': average of all RUB->USDT rates,
        'average': (sell + buy) / 2
    }
    """

    api_key = os.getenv('BEST_EXCHANGE_API')
    sources_data = get_rates_sources_from_json()

    usdt, rub = sources_data[2]["api_data"].values()
    usdt_ids = [x["id"] for x in usdt]
    rub_ids = [x["id"] for x in rub]

    # Create pairs: USDT->RUB (sell) and RUB->USDT (buy)
    sell_pairs = [f"{usdt_id}-{rub_id}" for usdt_id in usdt_ids for rub_id in rub_ids]
    buy_pairs = [f"{rub_id}-{usdt_id}" for rub_id in rub_ids for usdt_id in usdt_ids]

    pairs_str = "+".join(sell_pairs + buy_pairs)
    url = f"https://bestchange.app/v2/{api_key}/rates/{pairs_str}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                data = await response.json()

                if isinstance(data, dict) and "rates" in data:
                    rates_data = data["rates"]

                    # Extract rates for sell pairs (USDT->RUB)
                    sell_rates = []
                    for pair_key in sell_pairs:
                        if pair_key in rates_data:
                            pair_rates = rates_data[pair_key]
                            if isinstance(pair_rates, list) and len(pair_rates) > 0:
                                # Extract rate from each changer
                                sell_rates.extend([float(item["rate"]) for item in pair_rates if "rate" in item])

                    # Extract rates for buy pairs (RUB->USDT)
                    buy_rates = []
                    for pair_key in buy_pairs:
                        if pair_key in rates_data:
                            pair_rates = rates_data[pair_key]
                            if isinstance(pair_rates, list) and len(pair_rates) > 0:
                                # Extract rate from each changer
                                buy_rates.extend([float(item["rate"]) for item in pair_rates if "rate" in item])

                    # Calculate averages

                    sell = 1 / (sum(sell_rates) / len(sell_rates)) if sell_rates else None
                    buy = sum(buy_rates) / len(buy_rates) if buy_rates else None
                    average = ((sell + buy) / 2) if sell and buy else None

                    return {
                        'sell': sell,
                        'buy': buy,
                        'average': average
                    }

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError):
            pass

    return {'sell': 0, 'buy': 0, 'average': 0}


async def get_p2p_bybit_usdt_rub_rate() -> dict[str, float | None]:
    """Get USDT/RUB P2P rates from Bybit API"""

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
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
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


async def get_update_of_exchange_rates():
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


async def format_exchange_rate_from_db(exchange_rates):
    rtn = {}
    for er in exchange_rates:
        rtn[er.id] = round(er.rate, 2)
    return rtn


def get_exchange_rates_from_json():
    with open(f"{root_dir}/exchange_rate_data/exchange_rates.json", "r") as file:
        return json.load(file)


def get_rates_sources_from_json():
    with open(f"{root_dir}/exchange_rate_data/rates_sources.json", "r") as file:
        return json.load(file)


if __name__ == "__main__":
    import asyncio


    async def test():
        rate = await get_p2p_bybit_usdt_rub_rate()
        print(rate)


    asyncio.run(test())
