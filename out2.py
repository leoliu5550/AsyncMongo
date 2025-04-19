"""
MongoDB 客戶端 - 具有連線池、異步操作、刷新機制和抽象工廠模式
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, Type
from abc import ABC, abstractmethod
import time
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import ConnectionFailure, OperationFailure
import threading
from contextlib import asynccontextmanager

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mongo_client')

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


class MongoOperation:
    """封裝 MongoDB 操作的類"""
    
    def __init__(self, client: MongoDBClient, collection_name: str, database_name: Optional[str] = None):
        self.client = client
        self.collection_name = collection_name
        self.database_name = database_name
    
    def get_collection(self) -> AsyncIOMotorCollection:
        """獲取集合"""
        return self.client.get_collection(self.collection_name, self.database_name)
    
    async def find_one(self, query: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        """查找單個文檔"""
        collection = self.get_collection()
        return await collection.find_one(query, **kwargs)
    
    async def find_many(self, query: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """查找多個文檔"""
        collection = self.get_collection()
        cursor = collection.find(query, **kwargs)
        return await cursor.to_list(length=None)
    
    async def insert_one(self, document: Dict[str, Any], **kwargs) -> str:
        """插入單個文檔"""
        collection = self.get_collection()
        result = await collection.insert_one(document, **kwargs)
        return str(result.inserted_id)
    
    async def insert_many(self, documents: List[Dict[str, Any]], **kwargs) -> List[str]:
        """插入多個文檔"""
        collection = self.get_collection()
        result = await collection.insert_many(documents, **kwargs)
        return [str(id) for id in result.inserted_ids]
    
    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], **kwargs) -> int:
        """更新單個文檔"""
        collection = self.get_collection()
        result = await collection.update_one(query, update, **kwargs)
        return result.modified_count
    
    async def update_many(self, query: Dict[str, Any], update: Dict[str, Any], **kwargs) -> int:
        """更新多個文檔"""
        collection = self.get_collection()
        result = await collection.update_many(query, update, **kwargs)
        return result.modified_count
    
    async def delete_one(self, query: Dict[str, Any], **kwargs) -> int:
        """刪除單個文檔"""
        collection = self.get_collection()
        result = await collection.delete_one(query, **kwargs)
        return result.deleted_count
    
    async def delete_many(self, query: Dict[str, Any], **kwargs) -> int:
        """刪除多個文檔"""
        collection = self.get_collection()
        result = await collection.delete_many(query, **kwargs)
        return result.deleted_count
    
    async def count_documents(self, query: Dict[str, Any], **kwargs) -> int:
        """計算文檔數量"""
        collection = self.get_collection()
        return await collection.count_documents(query, **kwargs)
    
    async def aggregate(self, pipeline: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """執行聚合操作"""
        collection = self.get_collection()
        cursor = collection.aggregate(pipeline, **kwargs)
        return await cursor.to_list(length=None)


class IMongoDBClientFactory(ABC):
    """MongoDB 客戶端工廠接口"""
    
    @abstractmethod
    def create_client(self, config_name: str = "default") -> IMongoDBClient:
        """創建 MongoDB 客戶端"""
        pass
    
    @abstractmethod
    def register_config(self, config_name: str, config: MongoDBConfig) -> None:
        """註冊配置"""
        pass
    

class MongoDBClientFactory(IMongoDBClientFactory):
    """MongoDB 客戶端工廠實現類"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MongoDBClientFactory, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not getattr(self, '_initialized', False):
            self._configs: Dict[str, MongoDBConfig] = {}
            self._clients: Dict[str, IMongoDBClient] = {}
            self._initialized = True
    
    def register_config(self, config_name: str, config: MongoDBConfig) -> None:
        """註冊配置"""
        self._configs[config_name] = config
    
    def create_client(self, config_name: str = "default") -> IMongoDBClient:
        """創建或獲取 MongoDB 客戶端"""
        if config_name not in self._configs:
            raise ValueError(f"未找到配置: {config_name}")
        
        if config_name not in self._clients:
            config = self._configs[config_name]
            client = MongoDBClient(config)
            self._clients[config_name] = client
        
        return self._clients[config_name]


class IMongoDBRepository(ABC):
    """MongoDB 儲存庫抽象類"""
    
    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def find_all(self) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def save(self, entity: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    async def update(self, id: str, entity: Dict[str, Any]) -> bool:
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        pass


class MongoDBRepository(IMongoDBRepository):
    """MongoDB 儲存庫實現類"""
    
    def __init__(self, mongo_operation: MongoOperation):
        self.mongo_operation = mongo_operation
    
    async def find_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查找"""
        from bson.objectid import ObjectId
        return await self.mongo_operation.find_one({"_id": ObjectId(id)})
    
    async def find_all(self) -> List[Dict[str, Any]]:
        """查找所有"""
        return await self.mongo_operation.find_many({})
    
    async def save(self, entity: Dict[str, Any]) -> str:
        """保存實體"""
        return await self.mongo_operation.insert_one(entity)
    
    async def update(self, id: str, entity: Dict[str, Any]) -> bool:
        """更新實體"""
        from bson.objectid import ObjectId
        # 移除 _id 以避免更新錯誤
        if "_id" in entity:
            del entity["_id"]
        result = await self.mongo_operation.update_one(
            {"_id": ObjectId(id)},
            {"$set": entity}
        )
        return result > 0
    
    async def delete(self, id: str) -> bool:
        """刪除實體"""
        from bson.objectid import ObjectId
        result = await self.mongo_operation.delete_one({"_id": ObjectId(id)})
        return result > 0


# 使用範例
async def example_usage():
    # 建立工廠
    factory = MongoDBClientFactory()
    
    # 註冊配置
    config = MongoDBConfig(
        uri="mongodb://localhost:27017",
        database="example_db",
        max_pool_size=20
    )
    factory.register_config("default", config)
    
    # 建立客戶端
    client = factory.create_client("default")
    
    # 連接到 MongoDB
    await client.connect()
    
    try:
        # 建立操作對象
        user_operation = MongoOperation(client, "users")
        
        # 使用儲存庫模式
        user_repository = MongoDBRepository(user_operation)
        
        # 執行一些操作
        user_id = await user_repository.save({
            "name": "測試用戶",
            "email": "test@example.com",
            "created_at": time.time()
        })
        
        print(f"已創建用戶，ID: {user_id}")
        
        user = await user_repository.find_by_id(user_id)
        print(f"找到用戶: {user}")
        
        # 直接使用操作類
        product_operation = MongoOperation(client, "products")
        await product_operation.insert_one({
            "name": "測試產品",
            "price": 99.99,
            "created_at": time.time()
        })
        
        products = await product_operation.find_many({"price": {"$gt": 50}})
        print(f"找到產品: {products}")
        
    finally:
        # 關閉連接
        await client.disconnect()


if __name__ == "__main__":
    # 運行示例
    asyncio.run(example_usage())