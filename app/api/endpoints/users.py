from typing import List
from datetime import datetime


from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_user_repository, get_mongo_client

from app.db import MongoDBRepository, IMongoDBClient, MongoOperation

from app.schema import UserCreateModel, UserUpdateModel, UserModel

user_router = APIRouter()


@user_router.post(
    "/users", response_model=UserModel, status_code=status.HTTP_201_CREATED
)
async def create_user(
    user: UserCreateModel, repo: MongoDBRepository = Depends(get_user_repository)
):
    """創建新用戶"""
    user_dict = user.model_dump()
    user_dict["created_at"] = datetime.now()

    user_id = await repo.save(user_dict)

    # 獲取創建的用戶
    created_user = await repo.find_by_id(user_id)
    if not created_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="用戶創建失敗"
        )

    return created_user


@user_router.get("/users", response_model=List[UserModel])
async def get_all_users(repo: MongoDBRepository = Depends(get_user_repository)):
    """獲取所有用戶"""
    users = await repo.find_all()
    return users


@user_router.get("/users/{user_id}", response_model=UserModel)
async def get_user(
    user_id: str, repo: MongoDBRepository = Depends(get_user_repository)
):
    """根據 ID 獲取用戶"""
    try:
        user = await repo.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用戶 ID {user_id} 不存在",
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"無效的用戶 ID: {str(e)}"
        )


@user_router.put("/users/{user_id}", response_model=UserModel)
async def update_user(
    user_id: str,
    user_update: UserUpdateModel,
    client: IMongoDBClient = Depends(get_mongo_client),
    repo: MongoDBRepository = Depends(get_user_repository),
):
    """更新用戶信息"""
    try:
        # 檢查用戶是否存在
        existing_user = await repo.find_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用戶 ID {user_id} 不存在",
            )

        # 過濾掉未提供的字段
        update_data = {
            k: v for k, v in user_update.model_dump().items() if v is not None
        }
        if not update_data:
            return existing_user  # 沒有更新數據

        # 更新用戶
        success = await repo.update(user_id, update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="用戶更新失敗"
            )

        # 獲取更新後的用戶
        updated_user = await repo.find_by_id(user_id)
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"更新用戶失敗: {str(e)}"
        )


@user_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str, repo: MongoDBRepository = Depends(get_user_repository)
):
    """刪除用戶"""
    try:
        # 檢查用戶是否存在
        existing_user = await repo.find_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用戶 ID {user_id} 不存在",
            )

        # 刪除用戶
        success = await repo.delete(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="用戶刪除失敗"
            )

        # 204 No Content 回應不需要返回正文
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"刪除用戶失敗: {str(e)}"
        )


# 進階查詢範例：自定義操作
@user_router.get("/users/search/by-email/{email}", response_model=UserModel)
async def find_user_by_email(
    email: str, client: IMongoDBClient = Depends(get_mongo_client)
):
    """根據電子郵件查找用戶"""
    operation = MongoOperation(client, "users")
    user = await operation.find_one({"email": email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到電子郵件為 {email} 的用戶",
        )

    return user


@user_router.get("/users/stats/age-groups")
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
                    "users": {"$push": {"name": "$name", "email": "$email"}},
                },
            }
        }
    ]

    results = await operation.aggregate(pipeline)
    return {"age_groups": results}
