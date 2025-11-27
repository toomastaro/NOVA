"""
Standalone test script for exchange_rates module
Run this to test the exchange rate fetching without the bot
"""

import asyncio
import sys
import json
from datetime import datetime

# Import the exchange rates module
# Make sure exchange_rates.py is in the same directory or adjust the path
from exchange_rates import ExchangeRates


async def test_individual_sources():
    """Test each source individually"""
    print("=" * 70)
    print("Testing Individual Sources")
    print("=" * 70)

    # Test BestChange
    print("\n[1/3] Testing BestChange...")
    try:
        rate = await ExchangeRates.get_bestchange_rate()
        if rate:
            print(f"✅ BestChange: {rate:.2f} RUB per USDT")
        else:
            print("⚠️  BestChange: No rate returned")
    except Exception as e:
        print(f"❌ BestChange Error: {e}")

    # Test Crypto Bot
    print("\n[2/3] Testing Crypto Bot...")
    try:
        rate = await ExchangeRates.get_crypto_bot_rate()
        if rate:
            print(f"✅ Crypto Bot: {rate:.2f} RUB per USDT")
        else:
            print("⚠️  Crypto Bot: No rate returned")
    except Exception as e:
        print(f"❌ Crypto Bot Error: {e}")

    # Test P2P Army
    print("\n[3/3] Testing P2P Army...")
    try:
        rate = await ExchangeRates.get_p2p_army_rate()
        if rate:
            print(f"✅ P2P Army: {rate:.2f} RUB per USDT")
        else:
            print("⚠️  P2P Army: No rate returned")
    except Exception as e:
        print(f"❌ P2P Army Error: {e}")


async def test_all_rates():
    """Test fetching all rates at once"""
    print("\n" + "=" * 70)
    print("Testing All Rates Together")
    print("=" * 70)

    try:
        rates = await ExchangeRates.get_all_rates()

        print("\n📊 Results:")
        print(json.dumps(rates, indent=2))

        print("\n" + "=" * 70)
        print("Formatted Output (for Telegram):")
        print("=" * 70)
        formatted = ExchangeRates.format_rates(rates)
        print(formatted)

    except Exception as e:
        print(f"❌ Error: {e}")


async def test_with_timing():
    """Test and show how long each request takes"""
    print("\n" + "=" * 70)
    print("Testing with Timing")
    print("=" * 70)

    import time

    # Test all sources with timing
    sources = {
        "BestChange": ExchangeRates.get_bestchange_rate,
        "Crypto Bot": ExchangeRates.get_crypto_bot_rate,
        "P2P Army": ExchangeRates.get_p2p_army_rate,
    }

    for name, func in sources.items():
        start = time.time()
        try:
            rate = await func()
            elapsed = time.time() - start
            status = "✅" if rate else "⚠️"
            print(f"{status} {name:15} | Rate: {str(rate):10} | Time: {elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - start
            print(f"❌ {name:15} | Error: {str(e)[:40]:40} | Time: {elapsed:.2f}s")


async def main():
    """Main test function"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Exchange Rates Test Suite" + " " * 29 + "║")
    print("║" + f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " " * 33 + "║")
    print("╚" + "=" * 68 + "╝")

    # Run tests
    await test_individual_sources()
    await test_all_rates()
    await test_with_timing()

    print("\n" + "=" * 70)
    print("✅ Test Complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Run the async tests
    asyncio.run(main())