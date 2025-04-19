"""
FastAPI 與自定義 MongoDB 客戶端整合範例
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
from bson import ObjectId
import uvicorn
import json
from datetime import datetime

# 引入之前定義的 MongoDB 客戶端類
from mongo_client import (
    MongoDBConfig, 
    MongoDBClientFactory, 
    MongoOperation,
    MongoDBRepository,
    IMongoDBClient
)

# Pydantic 模型
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("無效的 ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    email: str
    age: Optional[int] = None
    created_at: Optional[datetime] = None
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }


class UserCreateModel(BaseModel):
    name: str
    email: str
    age: Optional[int] = None


class UserUpdateModel(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None


# 建立 FastAPI 應用
app = FastAPI(title="FastAPI MongoDB 示例")

# 初始化 MongoDB 客戶端工廠和配置 (全局初始化)
mongo_factory = MongoDBClientFactory()
mongo_config = MongoDBConfig(
    uri="mongodb://localhost:27017",
    database="fastapi_demo",
    max_pool_size=20
)
mongo_factory.register_config("default", mongo_config)


# 啟動時連接數據庫，關閉時釋放連接
@app.on_event("startup")
async def startup_db_client():
    """應用啟動時初始化數據庫連接"""
    mongo_client = mongo_factory.create_client("default")
    await mongo_client.connect()
    app.state.mongo_client = mongo_client
    print("MongoDB 連接已建立")


@app.on_event("shutdown")
async def shutdown_db_client():
    """應用關閉時斷開數據庫連接"""
    if hasattr(app.state, "mongo_client"):
        await app.state.mongo_client.disconnect()
        print("MongoDB 連接已關閉")


# 依賴注入函數：獲取 MongoDB 客戶端
async def get_mongo_client() -> IMongoDBClient:
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


# API 路由
@app.get("/")
async def root():
    """根路徑"""
    return {"message": "歡迎使用 FastAPI MongoDB 示例 API"}


@app.get("/health")
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


@app.post("/users", response_model=UserModel, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreateModel,
    repo: MongoDBRepository = Depends(get_user_repository)
):
    """創建新用戶"""
    user_dict = user.dict()
    user_dict["created_at"] = datetime.now()
    
    user_id = await repo.save(user_dict)
    
    # 獲取創建的用戶
    created_user = await repo.find_by_id(user_id)
    if not created_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用戶創建失敗"
        )
    
    return created_user


@app.get("/users", response_model=List[UserModel])
async def get_all_users(repo: MongoDBRepository = Depends(get_user_repository)):
    """獲取所有用戶"""
    users = await repo.find_all()
    return users


@app.get("/users/{user_id}", response_model=UserModel)
async def get_user(
    user_id: str,
    repo: MongoDBRepository = Depends(get_user_repository)
):
    """根據 ID 獲取用戶"""
    try:
        user = await repo.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用戶 ID {user_id} 不存在"
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"無效的用戶 ID: {str(e)}"
        )


@app.put("/users/{user_id}", response_model=UserModel)
async def update_user(
    user_id: str,
    user_update: UserUpdateModel,
    client: IMongoDBClient = Depends(get_mongo_client),
    repo: MongoDBRepository = Depends(get_user_repository)
):
    """更新用戶信息"""
    try:
        # 檢查用戶是否存在
        existing_user = await repo.find_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用戶 ID {user_id} 不存在"
            )
        
        # 過濾掉未提供的字段
        update_data = {k: v for k, v in user_update.dict().items() if v is not None}
        if not update_data:
            return existing_user  # 沒有更新數據
        
        # 更新用戶
        success = await repo.update(user_id, update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="用戶更新失敗"
            )
        
        # 獲取更新後的用戶
        updated_user = await repo.find_by_id(user_id)
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"更新用戶失敗: {str(e)}"
        )


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    repo: MongoDBRepository = Depends(get_user_repository)
):
    """刪除用戶"""
    try:
        # 檢查用戶是否存在
        existing_user = await repo.find_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用戶 ID {user_id} 不存在"
            )
        
        # 刪除用戶
        success = await repo.delete(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="用戶刪除失敗"
            )
        
        # 204 No Content 回應不需要返回正文
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"刪除用戶失敗: {str(e)}"
        )


# 進階查詢範例：自定義操作
@app.get("/users/search/by-email/{email}", response_model=UserModel)
async def find_user_by_email(
    email: str,
    client: IMongoDBClient = Depends(get_mongo_client)
):
    """根據電子郵件查找用戶"""
    operation = MongoOperation(client, "users")
    user = await operation.find_one({"email": email})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到電子郵件為 {email} 的用戶"
        )
    
    return user


@app.get("/users/stats/age-groups")
async def get_age_group_stats(client: IMongoDBClient = Depends(get_mongo_client)):
    """按年齡段統計用戶數量"""
    operation = MongoOperation(client, "users")
    
    pipeline = [
        {
            "$bucket": {
                "groupBy": "$age",
                "boundaries": [0, 18, 30, 50, 100],
                "default": "unknown",
                "output": {
                    "count": {"$sum": 1},
                    "users": {"$push": {"name": "$name", "email": "$email"}}
                }
            }
        }
    ]
    
    results = await operation.aggregate(pipeline)
    return {"age_groups": results}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)