from fastapi import FastAPI
from contextlib import asynccontextmanager
import database
from redis_client import init_redis, close_redis
from topology import topology_manager
from ingest import router as ingest_router
from tickets import router as tickets_router
from ai import router as ai_router
from topology_api import router as topology_router
from debug_api import router as debug_router
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await database.init_db_pool()
    await init_redis()
    await topology_manager.load_from_db(database.pool)
    yield
    # Shutdown
    await database.close_db_pool()
    await close_redis()

app = FastAPI(title="Fault Localization API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(tickets_router)
app.include_router(ai_router)
app.include_router(topology_router)
app.include_router(debug_router)

@app.get("/")
def read_root():
    return {"status": "ok"}
