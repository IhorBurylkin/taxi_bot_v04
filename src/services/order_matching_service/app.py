from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.infra.database import init_db, close_db
from src.infra.event_bus import init_event_bus, close_event_bus, get_event_bus
from src.infra.redis_client import RedisClient
from src.services.order_matching_service.consumer import OrderMatchingConsumer
from src.services.order_matching_service.utils import GeoUtils
from src.config import settings

consumer: OrderMatchingConsumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init Infrastructure
    await init_db()
    await init_event_bus()
    
    redis = RedisClient()
    await redis.connect()
    
    # Init Consumer
    global consumer
    geo_utils = GeoUtils(redis)
    consumer = OrderMatchingConsumer(get_event_bus(), geo_utils)
    await consumer.start()
    
    yield
    
    # Cleanup
    await close_db()
    await close_event_bus()
    await redis.disconnect()

app = FastAPI(
    title="Order Matching Service",
    version="0.5.2",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "order_matching_service"}
