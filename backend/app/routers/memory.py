"""
记忆路由模块
提供用户记忆的完整 CRUD 接口：查询、创建、更新内容、删除
记忆是 AI 对话的核心参考要素之一（与 System Prompt 配合使用）
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone

from ..database import get_database
from ..core.dependencies import get_current_user
from ..utils.response import success_response, error_response
from ..utils.helpers import validate_object_id, get_current_time
from ..services.ai_service import AIService
from ..services.memory_service import MemoryService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memories", tags=["记忆"])

_memory_service = MemoryService(AIService())


# ── 请求模型 ─────────────────────────────────────────────────────────────────

class MemoryCreate(BaseModel):
    """手动创建记忆"""
    digital_person_id: str = Field(..., description="绑定的数字人 ID")
    content: str = Field(..., min_length=1, max_length=500, description="记忆内容")
    category: str = Field(default="personal", description="分类：career/emotion/personal/goal/event")
    importance_score: float = Field(default=0.7, ge=0.0, le=1.0, description="重要性分数 0~1")


class MemoryUpdate(BaseModel):
    """更新记忆内容"""
    content: Optional[str] = Field(default=None, min_length=1, max_length=500, description="记忆内容")
    category: Optional[str] = Field(default=None, description="记忆分类")
    importance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="重要性分数")


# ── 路由 ─────────────────────────────────────────────────────────────────────

@router.get("/{digital_person_id}", summary="获取数字人的记忆列表")
async def get_memories(
    digital_person_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取当前用户对指定数字人的所有记忆（按重要性降序）"""
    if not validate_object_id(digital_person_id):
        return error_response("无效的数字人 ID", status_code=400)

    memories = await _memory_service.get_memories(
        user_id=current_user["id"],
        digital_person_id=digital_person_id,
        db=db,
        limit=100,
    )

    # 按分类分组
    grouped = {}
    for mem in memories:
        cat = mem["category"]
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(mem)

    return success_response(data={
        "memories": memories,
        "grouped": grouped,
        "total": len(memories),
    })


@router.post("/", summary="手动创建记忆")
async def create_memory(
    body: MemoryCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """用户手动添加一条记忆，自动关联到指定数字人"""
    if not validate_object_id(body.digital_person_id):
        return error_response("无效的数字人 ID", status_code=400)

    # 验证数字人属于当前用户
    dp = await db["digital_persons"].find_one({
        "_id": ObjectId(body.digital_person_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if not dp:
        return error_response("数字人不存在或无权限", status_code=404)

    now = get_current_time()
    memory_doc = {
        "user_id": ObjectId(current_user["id"]),
        "digital_person_id": ObjectId(body.digital_person_id),
        "content": body.content.strip(),
        "category": body.category,
        "importance_score": body.importance_score,
        "source": "manual",          # 手动创建标记
        "created_at": now,
        "updated_at": now,
    }

    result = await db["memories"].insert_one(memory_doc)
    memory_id = str(result.inserted_id)

    # ==========================
    # 在 111 行前的 create_memory 插入
    # ==========================
    logger.info(f"=== [数据变更] 手动新增记忆 ===")
    logger.info(f"操作用户: {current_user['username']} ({current_user['id']})")
    logger.info(f"关联分身 ID: {body.digital_person_id}")
    logger.info(f"记忆内容: [{body.category}] {body.content}")
    logger.info(f"===============================")
    
    return success_response(
        data={"id": memory_id, **body.model_dump(), "created_at": now.isoformat()},
        message="记忆创建成功",
    )

@router.put("/{memory_id}", summary="更新记忆内容")
async def update_memory(
    memory_id: str,
    body: MemoryUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """修改指定记忆的内容、分类或重要性分数"""
    if not validate_object_id(memory_id):
        return error_response("无效的记忆 ID", status_code=400)

    # 验证所有权
    mem = await db["memories"].find_one({
        "_id": ObjectId(memory_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if not mem:
        return error_response("记忆不存在或无权限", status_code=404)

    update_fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_fields:
        return error_response("没有提供需要更新的字段", status_code=400)

    update_fields["updated_at"] = get_current_time()
    await db["memories"].update_one(
        {"_id": ObjectId(memory_id)},
        {"$set": update_fields},
    )

    logger.info(f"=== [数据变更] 记忆更新 ===")
    logger.info(f"操作用户: {current_user['username']} ({current_user['id']})")
    logger.info(f"修改记忆 ID: {memory_id}")
    logger.info(f"被改动字段: {update_fields}")
    logger.info(f"===========================")

    return success_response(message="记忆已更新")


@router.delete("/{memory_id}", summary="删除指定记忆")
async def delete_memory(
    memory_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """删除指定的记忆条目（验证所有权）"""
    if not validate_object_id(memory_id):
        return error_response("无效的记忆 ID", status_code=400)

    success = await _memory_service.delete_memory(
        memory_id=memory_id,
        user_id=current_user["id"],
        db=db,
    )

    if not success:
        return error_response("记忆不存在或无权限删除", status_code=404)

    logger.info(f"=== [数据变更] 记忆删除 ===")
    logger.info(f"操作用户: {current_user['username']} ({current_user['id']})")
    logger.info(f"已删除记忆 ID: {memory_id}")
    logger.info(f"===========================")

    return success_response(message="记忆已删除")
