import threading
from abc import ABC, abstractmethod
from typing import Dict
from app.db.mongo.client import IMongoDBClient, MongoDBConfig, MongoDBClient

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