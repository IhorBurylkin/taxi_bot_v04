import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.services.users_service.routes import router
from src.infra.database import DatabaseManager
from src.common.logger import log_info, TypeMsg
from src.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await log_info("Starting Users Service...", type_msg=TypeMsg.INFO)
    db = DatabaseManager()
    await db.connect(dsn=settings.database.dsn)
    
    yield
    
    # Shutdown
    await log_info("Shutting down Users Service...", type_msg=TypeMsg.INFO)
    await db.disconnect()

app = FastAPI(
    title="Users Service",
    description="Microservice for managing user profiles and drivers",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "users_service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.services.users_service.app:app",
        host="0.0.0.0",
        port=settings.system.USERS_SERVICE_PORT,
        reload=True
    )
