import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.services.pricing_service.routes import router
from src.common.logger import log_info, TypeMsg
from src.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await log_info("Starting Pricing Service...", type_msg=TypeMsg.INFO)
    yield
    # Shutdown
    await log_info("Shutting down Pricing Service...", type_msg=TypeMsg.INFO)

app = FastAPI(
    title="Pricing Service",
    description="Microservice for calculating trip prices",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "pricing_service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.services.pricing_service.app:app",
        host="0.0.0.0",
        port=settings.system.PRICING_SERVICE_PORT,
        reload=True
    )
