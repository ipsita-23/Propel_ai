import os
import asyncpg
import asyncio

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/fault_localization")

pool = None

async def init_db_pool():
    global pool
    max_retries = 5
    for attempt in range(max_retries):
        try:
            pool = await asyncpg.create_pool(DATABASE_URL)
            break
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"Database connection failed ({e}), retrying in 2 seconds... ({attempt+1}/{max_retries})")
            await asyncio.sleep(2)

async def close_db_pool():
    global pool
    if pool:
        await pool.close()

async def get_db():
    async with pool.acquire() as conn:
        yield conn
