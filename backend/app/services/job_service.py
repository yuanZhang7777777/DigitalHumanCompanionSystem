"""
岗位服务模块
功能：
  1. 解析用户粘贴的JD文本 → 结构化岗位信息
  2. 基于用户能力档案进行岗位匹配打分
  3. 从简历文本中提取用户技能
"""
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class JobService:
    """岗位解析与推荐匹配服务"""

    def __init__(self, ai_service):
        self._ai = ai_service

    async def parse_jd(self, jd_text: str) -> Dict:
        """
        使用 AI 解析用户粘贴的招聘JD文本
        返回结构化的岗位信息字典
        """
        system_prompt = """你是一个专业的招聘信息解析助手。
请从以下招聘JD文本中提取结构化信息，以 JSON 格式返回。

返回格式：
{
  "title": "岗位名称",
  "company": "公司名称（如未提及填null）",
  "location": "工作城市（如多个城市用逗号分隔）",
  "salary_min": 最低月薪数字（单位:元，如未提及填null）,
  "salary_max": 最高月薪数字（单位:元，如未提及填null）,
  "skills_required": ["技能1", "技能2", ...],
  "experience_years": 要求工作年限数字（0表示应届可，如未提及填0）,
  "education_level": "学历要求（本科/专科/不限/硕士等）",
  "is_fresh_grad_friendly": true或false（是否接受应届生）,
  "description": "岗位核心职责简述（100字以内）",
  "source_platform": "来源平台（如用户说是BOSS/智联等，否则填手动录入）"
}

只返回JSON，不要其他文字。"""

        messages = [{"role": "user", "content": f"招聘信息：\n{jd_text}"}]
        try:
            raw = await self._ai.chat(messages, system_prompt, temperature=0.1)
            # 清理可能存在的 markdown 代码块标记
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            result = json.loads(raw)
            return result
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"JD解析失败: {e}")
            return {
                "title": "未能识别岗位",
                "company": None,
                "location": "",
                "salary_min": None,
                "salary_max": None,
                "skills_required": [],
                "experience_years": 0,
                "education_level": "不限",
                "is_fresh_grad_friendly": True,
                "description": jd_text[:200],
                "source_platform": "手动录入",
            }

    async def extract_skills_from_resume(self, resume_text: str) -> Dict:
        """
        使用 AI 从简历文本中提取用户技能和个人信息
        """
        system_prompt = """你是一个简历解析助手。
请从以下简历文本中提取关键信息，以 JSON 格式返回。

返回格式：
{
  "skills": ["技能1", "技能2", ...],
  "education": "最高学历（本科/专科/硕士等）",
  "major": "专业",
  "experience_years": 工作年限数字（0表示应届）,
  "preferred_locations": ["偏好城市1", "偏好城市2"],
  "summary": "个人简介（100字以内）"
}

只返回JSON，不要其他文字。"""

        messages = [{"role": "user", "content": f"简历内容：\n{resume_text}"}]
        try:
            raw = await self._ai.chat(messages, system_prompt, temperature=0.1)
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            return json.loads(raw)
        except Exception as e:
            logger.error(f"简历解析失败: {e}")
            return {
                "skills": [],
                "education": "不限",
                "major": "",
                "experience_years": 0,
                "preferred_locations": [],
                "summary": "",
            }

    async def recommend_jobs(
        self,
        user_profile: Dict,
        jobs: List[Dict],
        limit: int = 10,
    ) -> List[Dict]:
        """
        基于用户能力档案对岗位列表进行智能匹配打分
        使用 AI 生成匹配理由，使用技能Jaccard相似度初筛
        """
        if not jobs:
            return []

        # 第一步：基于技能重叠度快速打分
        user_skills = set(s.lower() for s in user_profile.get("skills", []))
        scored = []

        for job in jobs:
            job_skills = set(s.lower() for s in job.get("skills_required", []))
            # 计算技能匹配分
            if user_skills and job_skills:
                intersection = len(user_skills & job_skills)
                union = len(user_skills | job_skills)
                skill_score = intersection / union if union > 0 else 0
            else:
                skill_score = 0.3  # 技能信息不足时给基础分

            # 薪资匹配分
            salary_score = self._calc_salary_score(
                user_profile.get("expected_salary_min"),
                user_profile.get("expected_salary_max"),
                job.get("salary_min"),
                job.get("salary_max"),
            )

            # 经验匹配分
            user_exp = user_profile.get("experience_years", 0)
            job_exp = job.get("experience_years", 0)
            exp_diff = abs(user_exp - job_exp)
            exp_score = 1.0 if exp_diff == 0 else max(0, 1 - exp_diff * 0.2)

            # 综合分（技能权重最高）
            total_score = skill_score * 0.5 + salary_score * 0.3 + exp_score * 0.2

            # 应届生友好加分
            if user_exp == 0 and job.get("is_fresh_grad_friendly"):
                total_score = min(1.0, total_score + 0.15)

            scored.append({
                **job,
                "match_score": round(total_score * 100),
                "matched_skills": list(user_skills & job_skills),
            })

        # 按匹配分降序排列，取前 limit 个
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        top_jobs = scored[:limit]

        # 第二步：调用 AI 为 top3 生成匹配理由
        if top_jobs:
            await self._generate_match_reasons(user_profile, top_jobs[:3])

        return top_jobs

    async def _generate_match_reasons(
        self, user_profile: Dict, jobs: List[Dict]
    ) -> None:
        """
        为前几个推荐岗位生成 AI 匹配理由，直接修改 job 字典
        """
        user_skills_str = "、".join(user_profile.get("skills", [])[:8]) or "暂无技能信息"
        job_list_str = "\n".join(
            f"{i+1}. {job.get('title')} - {job.get('company', '某公司')} "
            f"（匹配技能：{', '.join(job.get('matched_skills', []))[:50] or '综合匹配'}）"
            for i, job in enumerate(jobs)
        )

        system_prompt = """你是一个职业规划顾问，请为求职者生成简短的岗位匹配理由。
每条理由限30字以内，要具体，不要废话。
以 JSON 数组格式返回，每个元素是一个理由字符串，顺序与岗位列表一致。
只返回JSON数组，不要其他文字。"""

        messages = [{
            "role": "user",
            "content": f"求职者技能：{user_skills_str}\n\n岗位列表：\n{job_list_str}\n\n请为每个岗位生成匹配理由。"
        }]

        try:
            raw = await self._ai.chat(messages, system_prompt, temperature=0.3)
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            reasons = json.loads(raw)
            for i, job in enumerate(jobs):
                if i < len(reasons):
                    job["match_reason"] = reasons[i]
        except Exception as e:
            logger.error(f"生成匹配理由失败: {e}")
            for job in jobs:
                job["match_reason"] = f"技能匹配度 {job.get('match_score', 0)}%"

    def _calc_salary_score(
        self,
        user_min: Optional[float],
        user_max: Optional[float],
        job_min: Optional[float],
        job_max: Optional[float],
    ) -> float:
        """计算薪资匹配分（0~1）"""
        if not user_min or not job_min:
            return 0.5  # 信息不足时给中等分
        job_mid = (job_min + (job_max or job_min)) / 2
        user_mid = (user_min + (user_max or user_min)) / 2
        diff_ratio = abs(job_mid - user_mid) / user_mid if user_mid > 0 else 0
        return max(0, 1 - diff_ratio)
