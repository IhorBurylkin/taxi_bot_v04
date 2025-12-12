from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.services.trip_service.routes import router
from src.infra.database import init_db, close_db
from src.infra.event_bus import init_event_bus, close_event_bus
from src.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_event_bus()
    yield
    await close_db()
    await close_event_bus()

app = FastAPI(
    title="Trip Service",
    version="0.5.2",
    lifespan=lifespan
)

app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "trip_service"}
