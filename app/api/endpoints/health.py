

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.db import IMongoDBClient
from app.api.dependencies import get_user_repository, get_mongo_client

health_router = APIRouter()

@health_router.get("/health")
async def health_check(client: IMongoDBClient = Depends(get_mongo_client)):
    """健康檢查端點"""
    try:
        is_connected = await client.is_connected()
        return {
            "status": "healthy" if is_connected else "unhealthy",
            "database_connected": is_connected
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "detail": str(e)}
        )