#!/usr/bin/env python3
import asyncio
import asyncpg
import os
import sys

async def wait_for_db():
    max_retries = 30
    retry_count = 0

    pg_user = os.getenv('PG_USER', 'postgres')
    pg_pass = os.getenv('PG_PASS', '')
    pg_db = os.getenv('PG_DATABASE', 'nova_bot_db')
    pg_host = os.getenv('PG_HOST', 'db')
    pg_port = int(os.getenv('PG_PORT', 5432))

    while retry_count < max_retries:
        try:
            conn = await asyncpg.connect(
                user=pg_user,
                password=pg_pass,
                database=pg_db,
                host=pg_host,
                port=pg_port
            )
            await conn.close()
            print("✅ Database is ready!")
            return True
        except Exception as e:
            retry_count += 1
            print(f"⏳ Waiting for database... ({retry_count}/{max_retries}): {e}")
            await asyncio.sleep(2)

    print("❌ Database is not ready after maximum retries")
    return False


if __name__ == "__main__":
    success = asyncio.run(wait_for_db())
    sys.exit(0 if success else 1)
