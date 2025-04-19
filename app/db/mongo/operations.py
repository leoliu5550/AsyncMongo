from typing import Dict, Any, List, Optional
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorCollection,
)
from app.db.mongo.client import MongoDBClient


class MongoOperation:
    """封裝 MongoDB 操作的類"""

    def __init__(
        self,
        client: MongoDBClient,
        collection_name: str,
        database_name: Optional[str] = None,
    ):
        self.client = client
        self.collection_name = collection_name
        self.database_name = database_name

    def get_collection(self) -> AsyncIOMotorCollection:
        """獲取集合"""
        return self.client.get_collection(self.collection_name, self.database_name)

    async def find_one(
        self, query: Dict[str, Any], **kwargs
    ) -> Optional[Dict[str, Any]]:
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

    async def update_one(
        self, query: Dict[str, Any], update: Dict[str, Any], **kwargs
    ) -> int:
        """更新單個文檔"""
        collection = self.get_collection()
        result = await collection.update_one(query, update, **kwargs)
        return result.modified_count

    async def update_many(
        self, query: Dict[str, Any], update: Dict[str, Any], **kwargs
    ) -> int:
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

    async def aggregate(
        self, pipeline: List[Dict[str, Any]], **kwargs
    ) -> List[Dict[str, Any]]:
        """執行聚合操作"""
        collection = self.get_collection()
        cursor = collection.aggregate(pipeline, **kwargs)
        return await cursor.to_list(length=None)
