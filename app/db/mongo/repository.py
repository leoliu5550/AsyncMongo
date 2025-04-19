

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from app.db.mongo.operations import MongoOperation



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
