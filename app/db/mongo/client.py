
import time
import asyncio
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from pymongo.errors import ConnectionFailure
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from app.logger import logger


class MongoDBConfig:
    """MongoDB 連接配置類"""
    
    def __init__(self, 
                 uri: str, 
                 max_pool_size: int = 10,
                 min_pool_size: int = 1,
                 max_idle_time_ms: int = 60000,
                 connect_timeout_ms: int = 5000,
                 server_selection_timeout_ms: int = 5000,
                 database: str = "default_db"):
        self.uri = uri
        self.max_pool_size = max_pool_size
        self.min_pool_size = min_pool_size
        self.max_idle_time_ms = max_idle_time_ms
        self.connect_timeout_ms = connect_timeout_ms
        self.server_selection_timeout_ms = server_selection_timeout_ms
        self.database = database
    
    def get_connection_options(self) -> Dict[str, Any]:
        """返回連接選項字典"""
        return {
            "maxPoolSize": self.max_pool_size,
            "minPoolSize": self.min_pool_size,
            "maxIdleTimeMS": self.max_idle_time_ms,
            "connectTimeoutMS": self.connect_timeout_ms,
            "serverSelectionTimeoutMS": self.server_selection_timeout_ms
        }

class IMongoDBClient(ABC):
    """MongoDB 客戶端抽象基類"""
    
    @abstractmethod
    async def connect(self) -> None:
        """連接到 MongoDB"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """斷開與 MongoDB 的連接"""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """檢查是否已連接到 MongoDB"""
        pass
    
    @abstractmethod
    def get_database(self, database_name: Optional[str] = None) -> Any:
        """獲取數據庫"""
        pass
    
    @abstractmethod
    def get_collection(self, collection_name: str, database_name: Optional[str] = None) -> Any:
        """獲取集合"""
        pass
    
    @abstractmethod
    async def refresh_connection(self) -> None:
        """刷新連接"""
        pass
    
    @asynccontextmanager
    async def session(self):
        """提供會話上下文管理器"""
        pass

class MongoDBClient(IMongoDBClient):
    """MongoDB 客戶端實現類"""
    
    def __init__(self, config: MongoDBConfig):
        self.config = config
        self.client: Optional[AsyncIOMotorClient] = None
        self.is_ready = False
        self.last_refresh_time = 0
        self._refresh_interval = 300  # 秒
        self._lock = threading.RLock()
        self._health_check_task = None
    
    async def connect(self) -> None:
        """連接到 MongoDB"""
        if self.client is not None:
            return
        
        logger.info(f"連接到 MongoDB: {self.config.uri}")
        try:
            self.client = AsyncIOMotorClient(
                self.config.uri,
                **self.config.get_connection_options()
            )
            # 驗證連接
            await self.client.admin.command('ping')
            self.is_ready = True
            self.last_refresh_time = time.time()
            logger.info("MongoDB 連接成功")
            
            # 啟動健康檢查任務
            self._start_health_check()
        except ConnectionFailure as e:
            self.is_ready = False
            logger.error(f"MongoDB 連接失敗: {str(e)}")
            raise
    
    async def disconnect(self) -> None:
        """斷開與 MongoDB 的連接"""
        if self.client:
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
                self._health_check_task = None
                
            self.client.close()
            self.client = None
            self.is_ready = False
            logger.info("MongoDB 連接已關閉")
    
    async def is_connected(self) -> bool:
        """檢查是否已連接到 MongoDB"""
        if not self.client or not self.is_ready:
            return False
        
        try:
            await self.client.admin.command('ping')
            return True
        except Exception:
            self.is_ready = False
            return False
    
    def get_database(self, database_name: Optional[str] = None) -> AsyncIOMotorDatabase:
        """獲取數據庫"""
        if not self.client:
            raise ConnectionError("MongoDB 客戶端未初始化")
        
        db_name = database_name or self.config.database
        return self.client[db_name]
    
    def get_collection(self, collection_name: str, database_name: Optional[str] = None) -> AsyncIOMotorCollection:
        """獲取集合"""
        database = self.get_database(database_name)
        return database[collection_name]
    
    async def refresh_connection(self) -> None:
        """刷新連接"""
        logger.info("刷新 MongoDB 連接")
        with self._lock:
            await self.disconnect()
            await self.connect()
        self.last_refresh_time = time.time()
    
    @asynccontextmanager
    async def session(self):
        """提供會話上下文管理器"""
        if not self.client:
            await self.connect()
            
        async with await self.client.start_session() as session:
            yield session
    
    def _start_health_check(self) -> None:
        """啟動連接健康檢查"""
        async def health_check_routine():
            while True:
                try:
                    # 檢查是否需要刷新連接
                    if time.time() - self.last_refresh_time > self._refresh_interval:
                        await self.refresh_connection()
                    
                    # 每30秒檢查一次連接健康狀況
                    await asyncio.sleep(30)
                    
                    # 執行健康檢查
                    is_healthy = await self.is_connected()
                    if not is_healthy:
                        logger.warning("MongoDB 連接不健康，嘗試刷新")
                        await self.refresh_connection()
                        
                except asyncio.CancelledError:
                    logger.info("MongoDB 健康檢查任務被取消")
                    break
                except Exception as e:
                    logger.error(f"MongoDB 健康檢查錯誤: {str(e)}")
                    await asyncio.sleep(5)  # 短暫延遲後重試
        
        self._health_check_task = asyncio.create_task(health_check_routine())
        logger.info("MongoDB 健康檢查任務已啟動")
