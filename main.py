"""
FastAPI 與自定義 MongoDB 客戶端整合範例
"""
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

# 引入之前定義的 MongoDB 客戶端類

from app.api.endpoints import user_router

from app.db import (
    MongoDBConfig, 
    MongoDBClientFactory, 
    MongoOperation,
    MongoDBRepository,
    IMongoDBClient
)



# 初始化 MongoDB 客戶端工廠和配置 (全局初始化)
mongo_factory = MongoDBClientFactory()
mongo_config = MongoDBConfig(
    uri="mongodb://localhost:27017",
    database="fastapi_demo",
    max_pool_size=20
)
mongo_factory.register_config("default", mongo_config)


# 啟動時連接數據庫，關閉時釋放連接
async def startup_db_client():
    """應用啟動時初始化數據庫連接"""
    mongo_client = mongo_factory.create_client("default")
    await mongo_client.connect()
    app.state.mongo_client = mongo_client
    print("MongoDB 連接已建立")



async def shutdown_db_client():
    """應用關閉時斷開數據庫連接"""
    if hasattr(app.state, "mongo_client"):
        await app.state.mongo_client.disconnect()
        print("MongoDB 連接已關閉")



@asynccontextmanager
async def lifespan(app:FastAPI):
    startup_db_client()
    yield
    shutdown_db_client()


app = FastAPI(title="FastAPI MongoDB 示例", lifespan=lifespan)
app.include_router(user_router)

# API 路由
@app.get("/")
async def root():
    """根路徑"""
    return {"message": "歡迎使用 FastAPI MongoDB 示例 API"}









if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)