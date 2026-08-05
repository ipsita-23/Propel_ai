import asyncio
from backend import database
from backend.redis_client import init_redis, close_redis
from backend.topology import topology_manager
from backend.localization import evaluate_dt
import logging

logging.basicConfig(level=logging.INFO)

async def run():
    await database.init_db_pool()
    await init_redis()
    await topology_manager.load_from_db(database.pool)
    print("Evaluating DT-001...")
    await evaluate_dt("DT-001")
    print("SUCCESS")
    await database.close_db_pool()
    await close_redis()

if __name__ == "__main__":
    import os
    os.environ["DATABASE_URL"] = "postgresql://user:password@localhost:5432/fault_localization"
    os.environ["REDIS_URL"] = "redis://localhost:6380/0" # Based on docker-compose.yml host port for redis is 6380
    asyncio.run(run())
