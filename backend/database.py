import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/fault_localization")

pool = None

async def init_db_pool():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

async def close_db_pool():
    global pool
    if pool:
        await pool.close()

async def get_db():
    async with pool.acquire() as conn:
        yield conn
