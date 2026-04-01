"""
数字人路由模块
提供数字人的创建、查询、更新、删除接口
数字人的 prompt 完全基于用户填写的内容动态生成
新增：experiences 时间线经历字段、preview-prompt 接口
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, File, UploadFile
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from bson import ObjectId
import time
import os
from datetime import datetime

from ..database import get_database
from ..core.dependencies import get_current_user
from ..utils.response import success_response, error_response
from ..utils.helpers import get_current_time, serialize_doc
from ..services.prompt_service import PromptService
from ..services.memory_service import MemoryService
from ..services.ai_service import AIService
from ..services.video_service import VideoService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/digital-persons", tags=["数字人"])
_video_service = VideoService()


# ── 请求/响应模型 ────────────────────────────────────────────────────────────

class DigitalPersonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20, description="数字人名字")
    relationship: str = Field(..., min_length=1, max_length=20, description="与用户的关系")
    personality_traits: List[str] = Field(
        default=[], description="性格特征标签列表（不限数量）"
    )
    background_story: str = Field(
        default="", max_length=500, description="背景故事（用户自由填写）"
    )
    speaking_style: str = Field(
        default="", max_length=200, description="说话风格描述（用户自由填写）"
    )
    user_description: str = Field(
        default="", max_length=500, description="用户对数字人的自由描述"
    )
    avatar: Optional[str] = Field(default=None, description="头像 Base64 字符串")
    tts_config: Optional[Dict[str, Any]] = Field(default=None, description="TTS 个性化语音模型配置")
    experiences: List[Dict[str, Any]] = Field(
        default=[],
        description="数字人经历时间线，每条格式: {year: '2020', event: '...', type: 'career'}"
    )


class DigitalPersonUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=20)
    relationship: Optional[str] = Field(default=None, max_length=20)
    personality_traits: Optional[List[str]] = None
    background_story: Optional[str] = Field(default=None, max_length=500)
    speaking_style: Optional[str] = Field(default=None, max_length=200)
    user_description: Optional[str] = Field(default=None, max_length=500)
    avatar: Optional[str] = None
    tts_config: Optional[Dict[str, Any]] = None
    experiences: Optional[List[Dict[str, Any]]] = None
    # 用户自定义覆盖的 System Prompt（空字符串表示使用自动生成的）
    system_prompt_override: Optional[str] = Field(default=None, max_length=8000, description="用户自定义 System Prompt")


# ── 路由处理 ─────────────────────────────────────────────────────────────────

@router.post("/", summary="创建数字人", status_code=201)
async def create_digital_person(
    body: DigitalPersonCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    创建数字人
    所有字段均来自用户填写，后端基于这些内容动态生成个性化 prompt
    """
    now = get_current_time()
    doc = {
        "user_id": ObjectId(current_user["id"]),
        "name": body.name,
        "relationship": body.relationship,
        "personality_traits": body.personality_traits,
        "background_story": body.background_story,
        "speaking_style": body.speaking_style,
        "user_description": body.user_description,
        "avatar": body.avatar,
        "tts_config": body.tts_config or {},
        "experiences": body.experiences,
        "created_at": now,
        "updated_at": now,
    }

    result = await db["digital_persons"].insert_one(doc)
    person_id = str(result.inserted_id)

    if body.avatar:
        from .conversation import _trigger_video_generation
        background_tasks.add_task(
            _trigger_video_generation,
            user_id=current_user["id"],
            digital_person_id=person_id,
            db=db
        )

    logger.info(f"用户 {current_user['username']} 创建数字人: {body.name} (id={person_id})")
    return success_response(
        data={
            "id": person_id,
            "name": body.name,
            "relationship": body.relationship,
            "personality_traits": body.personality_traits,
            "background_story": body.background_story,
            "speaking_style": body.speaking_style,
            "user_description": body.user_description,
            "avatar": body.avatar,
            "tts_config": body.tts_config or {},
            "experiences": body.experiences,
            "created_at": now.isoformat(),
        },
        message="数字人创建成功",
        status_code=201,
    )


@router.get("/", summary="获取当前用户的数字人列表")
async def list_digital_persons(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取当前登录用户的所有数字人"""
    logger.info(f"开始获取项目列表 - 用户 ID: {current_user['id']}")
    try:
        cursor = db["digital_persons"].find(
            {"user_id": ObjectId(current_user["id"])}
        ).sort("created_at", -1)

        persons = []
        async for doc in cursor:
            persons.append({
                "id": str(doc["_id"]),
                "name": doc.get("name", ""),
                "relationship": doc.get("relationship", ""),
                "personality_traits": doc.get("personality_traits", []),
                "background_story": doc.get("background_story", ""),
                "speaking_style": doc.get("speaking_style", ""),
                "user_description": doc.get("user_description", ""),
                "avatar": doc.get("avatar"),
                "speaking_video_url": doc.get("speaking_video_url"),
                "tts_config": doc.get("tts_config", {}),
                "experiences": doc.get("experiences", []),
                "created_at": doc["created_at"].isoformat()
                if isinstance(doc.get("created_at"), datetime)
                else doc.get("created_at"),
            })

        logger.info(f"成功获取项目列表 - 数量: {len(persons)}")
        return success_response(data=persons)
    except Exception as e:
        logger.error(f"获取数字人列表出错: {e}")
        return error_response(f"获取列表失败: {str(e)}", status_code=500)


@router.get("/{person_id}", summary="获取单个数字人详情")
async def get_digital_person(
    person_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取指定数字人的详细信息（必须属于当前用户）"""
    if not ObjectId.is_valid(person_id):
        return error_response("无效的数字人 ID", status_code=400)

    doc = await db["digital_persons"].find_one({
        "_id": ObjectId(person_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if not doc:
        return error_response("数字人不存在", status_code=404)

    return success_response(data={
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "relationship": doc.get("relationship", ""),
        "personality_traits": doc.get("personality_traits", []),
        "background_story": doc.get("background_story", ""),
        "speaking_style": doc.get("speaking_style", ""),
        "user_description": doc.get("user_description", ""),
        "avatar": doc.get("avatar"),
        "speaking_video_url": doc.get("speaking_video_url"),
        "tts_config": doc.get("tts_config", {}),
        "experiences": doc.get("experiences", []),
        "created_at": doc["created_at"].isoformat()
        if isinstance(doc.get("created_at"), datetime)
        else doc.get("created_at"),
        "updated_at": doc["updated_at"].isoformat()
        if isinstance(doc.get("updated_at"), datetime)
        else doc.get("updated_at"),
    })


@router.put("/{person_id}", summary="更新数字人信息")
async def update_digital_person(
    person_id: str,
    body: DigitalPersonUpdate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """更新数字人信息（只能更新属于当前用户的数字人）"""
    if not ObjectId.is_valid(person_id):
        return error_response("无效的数字人 ID", status_code=400)

    # 只更新非 None 的字段
    update_fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_fields:
        return error_response("没有提供需要更新的字段", status_code=400)

    update_fields["updated_at"] = get_current_time()

    update_doc: dict[str, dict] = {"$set": update_fields}
    
    # --- 修复逻辑：只有头像真正发生变化时才抹除视频 URL ---
    current_doc = await db["digital_persons"].find_one({"_id": ObjectId(person_id)})
    if not current_doc:
        return error_response("数字人不存在", status_code=404)

    if "avatar" in update_fields:
        new_avatar = update_fields["avatar"]
        old_avatar = current_doc.get("avatar")
        
        # 只有头像内容（Base64 或 URL）发生变化时才触发
        if new_avatar != old_avatar:
            update_doc["$unset"] = {"speaking_video_url": ""}
            from .conversation import _trigger_video_generation
            background_tasks.add_task(
                _trigger_video_generation,
                user_id=current_user["id"],
                digital_person_id=person_id,
                db=db
            )
        else:
            # 如果头像没变，我们不应该因为 update_fields 里带了 avatar 字段就删掉视频
            pass

    result = await db["digital_persons"].update_one(
        {"_id": ObjectId(person_id), "user_id": ObjectId(current_user["id"])},
        update_doc,
    )

    if result.matched_count == 0:
        return error_response("数字人不存在或无权限修改", status_code=404)

    logger.info(f"=== [数据变更] 数字人更新 ===")
    logger.info(f"操作用户 ID: {current_user['id']}")
    logger.info(f"被修改的数字人 ID: {person_id}")
    logger.info(f"更新的字段内容: {update_fields}")
    logger.info(f"===============================")

    return success_response(message="数字人信息更新成功")


@router.post("/{person_id}/video", summary="上传数字人视频")
async def upload_video(
    person_id: str,
    video: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    手动上传数字人播放视频，并永久保存至个人 OSS
    """
    if not ObjectId.is_valid(person_id):
        return error_response("无效的数字人 ID", status_code=400)

    # 1. 验证权限
    doc = await db["digital_persons"].find_one({
        "_id": ObjectId(person_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if not doc:
        return error_response("数字人不存在或无权限访问", status_code=404)

    # 2. 读取文件并上传 OSS
    try:
        content = await video.read()
        filename = f"manual_video_{person_id}_{int(time.time())}.mp4"
        oss_url = await _video_service.upload_file_to_oss(
            content, 
            filename, 
            content_type=video.content_type
        )

        # 3. 更新数据库
        await db["digital_persons"].update_one(
            {"_id": ObjectId(person_id)},
            {"$set": {
                "speaking_video_url": oss_url,
                "updated_at": get_current_time()
            }}
        )

        logger.info(f"用户 {current_user['id']} 为数字人 {person_id} 手动更新了视频: {oss_url}")
        return success_response(data={"video_url": oss_url}, message="视频上传成功")
    except Exception as e:
        logger.error(f"上传视频到 OSS 失败: {e}")
        return error_response(f"上传失败: {str(e)}", status_code=500)


@router.delete("/{person_id}", summary="删除数字人")
async def delete_digital_person(
    person_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """删除数字人及其关联的对话和记忆数据"""
    if not ObjectId.is_valid(person_id):
        return error_response("无效的数字人 ID", status_code=400)

    result = await db["digital_persons"].delete_one({
        "_id": ObjectId(person_id),
        "user_id": ObjectId(current_user["id"]),
    })

    if result.deleted_count == 0:
        return error_response("数字人不存在或无权限删除", status_code=404)

    # 级联删除关联数据
    await db["user_memories"].delete_many({"digital_person_id": ObjectId(person_id)})

    # 查找并删除相关对话及消息
    conv_ids = []
    async for conv in db["conversations"].find(
        {"digital_person_id": ObjectId(person_id)}, {"_id": 1}
    ):
        conv_ids.append(conv["_id"])

    if conv_ids:
        await db["messages"].delete_many({"conversation_id": {"$in": conv_ids}})
        await db["conversations"].delete_many({"_id": {"$in": conv_ids}})

    logger.info(f"用户 {current_user['username']} 删除数字人 {person_id}")
    return success_response(message="数字人及关联数据已删除")


@router.get("/{person_id}/preview-prompt", summary="预览数字人的完整System Prompt")
async def preview_prompt(
    person_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取指定数字人当前的完整 System Prompt（用于前端透明化展示）"""
    if not ObjectId.is_valid(person_id):
        return error_response("无效的数字人 ID", status_code=400)

    doc = await db["digital_persons"].find_one({
        "_id": ObjectId(person_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if not doc:
        return error_response("数字人不存在", status_code=404)

    # 获取记忆（用于更完整的 prompt 预览）
    memories = []
    cursor = (
        db["user_memories"]
        .find({"user_id": ObjectId(current_user["id"]), "digital_person_id": ObjectId(person_id)})
        .sort("importance_score", -1)
        .limit(15)
    )
    async for mem in cursor:
        memories.append({
            "category": mem.get("category", "personal"),
            "content": mem.get("content", ""),
            "importance_score": mem.get("importance_score", 0.5),
        })

    prompt_text = PromptService.preview_prompt(digital_person=doc, memories=memories or None)

    return success_response(data={
        "prompt": prompt_text,
        "person_name": doc.get("name", ""),
        "memory_count": len(memories),
    })