import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = None

async def init_redis():
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()

def get_redis():
    return redis_client
