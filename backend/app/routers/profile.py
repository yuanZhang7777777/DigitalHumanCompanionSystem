"""
用户能力档案路由模块
管理用户的技能、学历、薪资期望等求职档案信息
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from bson import ObjectId
from datetime import datetime

from ..database import get_database
from ..core.dependencies import get_current_user
from ..utils.response import success_response, error_response
from ..utils.helpers import get_current_time
from ..services.ai_service import AIService
from ..services.job_service import JobService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["用户档案"])

# 服务实例
_ai_service = AIService()
_job_service = JobService(_ai_service)


# ── 请求模型 ─────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    skills: Optional[List[str]] = Field(default=None, description="技能标签列表")
    education: Optional[str] = Field(default=None, max_length=20, description="学历")
    major: Optional[str] = Field(default=None, max_length=50, description="专业")
    # experience_years 支持字符串（如"应届"）或数字字符串
    experience_years: Optional[str] = Field(default=None, max_length=10, description="工作年限")
    experience_summary: Optional[str] = Field(default=None, max_length=1000, description="实习/工作经历描述")
    preferred_locations: Optional[List[str]] = Field(default=None, description="偏好城市")
    expected_salary_min: Optional[float] = Field(default=None, ge=0, description="最低期望月薪（元）")
    expected_salary_max: Optional[float] = Field(default=None, ge=0, description="最高期望月薪（元）")
    preferred_company_size: Optional[str] = Field(default=None, description="偏好公司规模")
    is_fresh_graduate: Optional[bool] = Field(default=None, description="是否应届生")
    self_description: Optional[str] = Field(default=None, max_length=500, description="自我描述")


class ResumeUpload(BaseModel):
    resume_text: str = Field(..., min_length=50, max_length=5000, description="简历文本内容")


# ── 路由处理 ─────────────────────────────────────────────────────────────────

@router.get("/", summary="获取用户能力档案")
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取当前用户的能力档案，如果不存在则返回空档案"""
    user_id = current_user["id"]
    doc = await db["user_profiles"].find_one({"user_id": ObjectId(user_id)})
    if not doc:
        # 返回默认空档案
        return success_response(data={
            "skills": [],
            "education": "",
            "major": "",
            "experience_years": 0,
            "preferred_locations": [],
            "expected_salary_min": None,
            "expected_salary_max": None,
            "preferred_company_size": "不限",
            "updated_at": None,
        })

    return success_response(data={
        "skills": doc.get("skills", []),
        "education": doc.get("education", ""),
        "major": doc.get("major", ""),
        "experience_years": doc.get("experience_years", 0),
        "preferred_locations": doc.get("preferred_locations", []),
        "expected_salary_min": doc.get("expected_salary_min"),
        "expected_salary_max": doc.get("expected_salary_max"),
        "preferred_company_size": doc.get("preferred_company_size", "不限"),
        "updated_at": doc["updated_at"].isoformat()
        if isinstance(doc.get("updated_at"), datetime)
        else doc.get("updated_at"),
    })


@router.put("/", summary="更新用户能力档案")
async def update_profile(
    body: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """创建或更新用户能力档案（upsert）"""
    user_id = current_user["id"]
    now = get_current_time()

    # 只更新非 None 的字段
    update_fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_fields:
        return error_response("没有提供需要更新的字段", status_code=400)

    update_fields["updated_at"] = now

    await db["user_profiles"].update_one(
        {"user_id": ObjectId(user_id)},
        {"$set": update_fields, "$setOnInsert": {"user_id": ObjectId(user_id), "created_at": now}},
        upsert=True,
    )

    logger.info(f"=== [数据变更] 能力档案更新 ===")
    logger.info(f"操作用户: {current_user['username']} ({user_id})")
    logger.info(f"更新的档案数据: {update_fields}")
    logger.info(f"=============================")

    return success_response(message="档案更新成功")


@router.post("/resume", summary="上传简历文本，AI自动提取技能")
async def upload_resume(
    body: ResumeUpload,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    接收简历文本，调用 AI 提取技能/学历/经验等信息
    自动同步到用户档案
    """
    user_id = current_user["id"]

    # AI 解析简历
    parsed = await _job_service.extract_skills_from_resume(body.resume_text)

    now = get_current_time()
    update_fields = {k: v for k, v in parsed.items() if v}
    update_fields["resume_text"] = body.resume_text[:2000]  # 保存简历原文（截断）
    update_fields["updated_at"] = now

    await db["user_profiles"].update_one(
        {"user_id": ObjectId(user_id)},
        {"$set": update_fields, "$setOnInsert": {"user_id": ObjectId(user_id), "created_at": now}},
        upsert=True,
    )

    logger.info(f"用户 {current_user['username']} 上传简历，提取技能: {parsed.get('skills', [])}")
    return success_response(
        data=parsed,
        message=f"简历解析成功，提取到 {len(parsed.get('skills', []))} 项技能",
    )
