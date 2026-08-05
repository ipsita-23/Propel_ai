import asyncio
import logging
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from redis_client import get_redis
from topology import topology_manager
from localization import evaluate_dt

logger = logging.getLogger(__name__)

router = APIRouter()

class TelemetryPayload(BaseModel):
    device_id: str
    pole_id: str
    event: str
    energized: bool
    ts: str
    seq: int
    battery_mv: int = None
    rssi: int = None
    fw: str = None

async def delayed_evaluation(dt_id: str):
    await asyncio.sleep(180) # 3-minute debounce
    logger.info(f"Debounce expired for DT {dt_id}, running localization.")
    await evaluate_dt(dt_id)
    # Clear the debounce flag
    redis = get_redis()
    await redis.delete(f"debounce:{dt_id}")

@router.post("/telemetry")
async def ingest_telemetry(payload: TelemetryPayload, background_tasks: BackgroundTasks):
    redis = get_redis()
    
    # 1. Dedup and Ordering
    device_key = f"device:{payload.device_id}"
    
    # We use a Redis transaction (pipeline) or just simple gets
    state_str = await redis.hgetall(device_key)
    
    if payload.event == "boot":
        # Reset sequence on boot
        pass 
    else:
        if state_str and "last_seq" in state_str:
            last_seq = int(state_str["last_seq"])
            if payload.seq < last_seq:
                # Out of order or duplicate, ignore
                return {"status": "ignored_out_of_order"}
                
    # 2. Update State
    await redis.hset(device_key, mapping={
        "last_seq": payload.seq,
        "energized": "1" if payload.energized else "0",
        "last_ts": payload.ts,
        "pole_id": payload.pole_id
    })
    
    # 3. Check transition
    previously_energized = state_str.get("energized") == "1" if state_str else True
    
    if previously_energized and not payload.energized:
        # Power lost transition
        dt_id = topology_manager.get_dt_for_pole(payload.pole_id)
        if dt_id:
            debounce_key = f"debounce:{dt_id}"
            is_debouncing = await redis.get(debounce_key)
            if not is_debouncing:
                await redis.setex(debounce_key, 180, "1")
                background_tasks.add_task(delayed_evaluation, dt_id)
    elif not previously_energized and payload.energized:
        # Power restored transition
        dt_id = topology_manager.get_dt_for_pole(payload.pole_id)
        if dt_id:
            # For restoration, we can trigger evaluation immediately (or after a short debounce)
            # We'll just evaluate immediately in the background
            background_tasks.add_task(evaluate_dt, dt_id)

    return {"status": "accepted"}
