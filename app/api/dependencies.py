from fastapi import FastAPI, Depends, HTTPException, status
from app.db.mongo.factory import IMongoDBClient
from app.db import (MongoOperation, MongoDBRepository)

# 依賴注入函數：獲取 MongoDB 客戶端
async def get_mongo_client(app:FastAPI) -> IMongoDBClient:
    """獲取 MongoDB 客戶端依賴"""
    if not hasattr(app.state, "mongo_client"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="數據庫連接未初始化"
        )
    mongo_client = app.state.mongo_client
    if not await mongo_client.is_connected():
        # 嘗試刷新連接
        try:
            await mongo_client.refresh_connection()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"數據庫連接失敗: {str(e)}"
            )
    return mongo_client


# 依賴注入函數：獲取用戶倉庫
async def get_user_repository(client: IMongoDBClient = Depends(get_mongo_client)) -> MongoDBRepository:
    """獲取用戶倉庫依賴"""
    operation = MongoOperation(client, "users")
    return MongoDBRepository(operation)
