from fastapi import APIRouter
from localization import evaluate_dt
from redis_client import get_redis

router = APIRouter(prefix="/debug")


@router.post("/evaluate/{dt_id}")
async def force_evaluate(dt_id: str):
    """Bypass the 3-minute debounce and run fault localisation immediately.
    For simulator / demo use only."""
    await evaluate_dt(dt_id)
    return {"status": "evaluated", "dt_id": dt_id}


@router.post("/scheduled_outage/{dt_id}")
async def set_scheduled_outage(dt_id: str, active: bool = True):
    """Toggle a simulated scheduled-outage flag in Redis for a DT.
    When active=true, evaluate_dt suppresses fault-ticket creation."""
    redis = get_redis()
    key = f"scheduled_outage:{dt_id}"
    if active:
        await redis.setex(key, 3600, "1")   # auto-expires in 1 hour
    else:
        await redis.delete(key)
    return {"status": "ok", "dt_id": dt_id, "active": active}
