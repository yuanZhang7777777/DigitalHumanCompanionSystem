"""
对话路由模块
提供消息发送（普通版/流式版）、对话查询、对话列表等接口
核心功能：发送消息时同步触发记忆提取（每条消息都触发）
"""
import asyncio
import json
import logging
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime

from ..database import get_database
from ..core.dependencies import get_current_user
from ..utils.response import success_response, error_response
from ..utils.helpers import get_current_time, sanitize_input, validate_object_id
from ..services.ai_service import AIService
from ..services.prompt_service import PromptService
from ..services.emotion_service import EmotionService
from ..services.memory_service import MemoryService
from ..services.video_service import VideoService
from ..services.embedding_service import EmbeddingService
from ..services.weather_service import WeatherService
from ..services.interview_service import InterviewService
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["对话"])

# 服务实例（单例）
_ai_service = AIService()
_prompt_service = PromptService()
_emotion_service = EmotionService()
_embedding_service = EmbeddingService()  # 向量嵌入服务（记忆语义检索用）
_memory_service = MemoryService(_ai_service, _embedding_service)  # 注入向量服务
_video_service = VideoService()
_weather_service = WeatherService()
_interview_service = InterviewService()

# ── 用户级并发控制 ────────────────────────────────────────────────────────────
_user_semaphores = {}

def get_user_semaphore(user_id: str):
    if user_id not in _user_semaphores:
        # 默认允许每个用户 2 个并发请求
        max_concurrent = getattr(settings, 'max_concurrent_per_user', 2)
        _user_semaphores[user_id] = asyncio.Semaphore(max_concurrent)
    return _user_semaphores[user_id]


# ── 请求模型 ─────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    digital_person_id: str = Field(..., description="数字人 ID")
    message: str = Field(default="", max_length=2000, description="用户消息")
    conversation_id: Optional[str] = Field(default=None, description="对话 ID（续接已有对话）")
    file_urls: Optional[list[str]] = Field(default=None, description="上传的图片或视频 URL 列表")
    is_jd_analysis: Optional[bool] = Field(default=False, description="是否强制开启 JD 深度分析模式")


# ── 后台任务 ─────────────────────────────────────────────────────────────────

async def _trigger_memory_extraction(
    user_id: str,
    digital_person_id: str,
    conversation_id: str,
    db,
):
    """
    后台触发记忆提取任务
    每条消息发送后都执行，只提取最新的用户消息
    """
    try:
        # 获取最近的消息用于提取（每次都触发，取最近 4 条保证上下文）
        messages = []
        cursor = (
            db["messages"]
            .find({"conversation_id": ObjectId(conversation_id)})
            .sort("timestamp", -1)
            .limit(4)
        )
        async for msg in cursor:
            messages.append(msg)
        messages.reverse()  # 恢复时间顺序

        if messages:
            count = await _memory_service.extract_and_store(
                user_id=user_id,
                digital_person_id=digital_person_id,
                conversation_id=conversation_id,
                messages=messages,
                db=db,
            )
            if count > 0:
                logger.info(f"后台记忆提取完成，新增 {count} 条记忆")
    except Exception as e:
        logger.error(f"后台记忆提取失败: {e}", exc_info=True)


# ── 路由处理 ─────────────────────────────────────────────────────────────────

async def _trigger_video_generation(
    user_id: str,
    digital_person_id: str,
    db
):
    """
    后台触发视频生成任务
    检测该数字人是否有上传的头像但没有生成视频，如果有，则启动阿里云视频生成并永久保存。
    """
    import os
    import base64
    import time
    try:
        person = await db["digital_persons"].find_one({"_id": ObjectId(digital_person_id)})
        if not person or not person.get("avatar"):
            return
            
        avatar_url = person["avatar"]
        
        # 核心逻辑改进：如果已经存在视频，且用于生成视频的头像没变，则跳过生成（复用）
        if person.get("speaking_video_url") and person.get("last_avatar_for_video") == avatar_url:
            logger.info(f"数字人 {digital_person_id} 的头像未变，复用已有动态视频。")
            return
            
        local_avatar_path = None
        
        # 处理本地静态路径
        if avatar_url.startswith("/static/"):
            local_avatar_path = os.path.join("app", avatar_url.lstrip("/"))
            
        # 处理 Base64 编码的图片
        elif avatar_url.startswith("data:image"):
            # 提取 base64 数据部分
            try:
                header, encoded = avatar_url.split(",", 1)
                img_data = base64.b64decode(encoded)
                # 临时文件路径
                os.makedirs(os.path.join("app", "static", "avatars"), exist_ok=True)
                temp_filename = f"temp_avatar_{digital_person_id}_{int(time.time())}.jpg"
                local_avatar_path = os.path.join("app", "static", "avatars", temp_filename)
                
                from PIL import Image
                import io
                
                # 读取并处理图片
                img = Image.open(io.BytesIO(img_data))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                    
                # LivePortrait 对图片要求严格，重置为 512x512
                img = img.resize((512, 512), Image.Resampling.LANCZOS)
                img.save(local_avatar_path, format="JPEG", quality=85)
            except Exception as e:
                logger.error(f"解析 Base64 头像失败: {e}")
                return
                
        if local_avatar_path and os.path.exists(local_avatar_path):
            # ✅ 提前检查视频生成开关（避免抛异常和报错日志）
            from ..config import settings
            if not settings.video_generation_enabled:
                logger.info(f"[视频生成] ⏭️ 功能已关闭，跳过数字人 {digital_person_id} 的视频生成")
                return
            
            local_audio_path = os.path.join("app", "static", "generic_speech.mp3")
            
            logger.info(f"检测到头像更新或初次生成，正在为数字人 {digital_person_id} 生成专属对话动态视频...")
            video_url = await _video_service.generate_generic_talking_head(
                user_id=user_id,
                avatar_local_path=local_avatar_path,
                audio_local_path=local_audio_path
            )
            
            # 更新到数据库，同时记录本次使用的头像 URL 用于以后比对
            await db["digital_persons"].update_one(
                {"_id": ObjectId(digital_person_id)},
                {"$set": {
                    "speaking_video_url": video_url,
                    "last_avatar_for_video": avatar_url
                }}
            )
            logger.info(f"数字人 {digital_person_id} 动态视频更新完毕: {video_url}")
            
    except Exception as e:
        logger.error(f"视频自动生成后台任务失败: {str(e)}", exc_info=True)

async def _update_conversation_summary(
    conversation_id: str,
    user_id: str,
    db
):
    """后台触发：当消息过长时自动压缩前面的对话为摘要，并存入 conversations 表中"""
    try:
        conversation = await db["conversations"].find_one({
            "_id": ObjectId(conversation_id),
            "user_id": ObjectId(user_id)
        })
        if not conversation:
            return
            
        message_count = conversation.get("message_count", 0)
        threshold = settings.history_summary_threshold
        keep = settings.recent_messages_keep
        
        if message_count > threshold:
            cursor = (
                db["messages"]
                .find({"conversation_id": ObjectId(conversation_id)})
                .sort("timestamp", 1)
            )
            all_messages = []
            async for msg in cursor:
                all_messages.append(msg)
                
            if len(all_messages) <= keep:
                return
                
            messages_to_summarize = all_messages[:-keep]
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages_to_summarize])
            
            exist_summary = conversation.get("summary", "")
            if exist_summary:
                history_text = f"【原有摘要】\n{exist_summary}\n\n【最新历史】\n{history_text}"
                
            new_summary = await _ai_service.summarize_history(history_text)
            
            if new_summary:
                await db["conversations"].update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": {"summary": new_summary}}
                )
                
                msg_ids_to_del = [m["_id"] for m in messages_to_summarize]
                if msg_ids_to_del:
                    await db["messages"].delete_many({"_id": {"$in": msg_ids_to_del}})
                
                await db["conversations"].update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$inc": {"message_count": -len(msg_ids_to_del)}}
                )
                logger.info(f"对话 {conversation_id} 摘要更新完毕，压缩了 {len(msg_ids_to_del)} 条消息")
    except Exception as e:
        logger.error(f"更新对话摘要失败: {e}", exc_info=True)


def format_jd_analysis_to_markdown(jd_result: dict) -> str:
    """
    将JD分析结果格式化为可读的Markdown文本
    用于在聊天中直接展示结构化面试准备方案
    """
    if not jd_result or "error" in jd_result:
        return "❌ JD 分析失败，请稍后重试"
    
    lines = []
    
    # 标题
    job_info = jd_result.get("job_analysis", {})
    position = job_info.get("position", "未知岗位")
    difficulty = job_info.get("interview_difficulty", "中等")
    
    # 难度映射
    diff_emoji = {"简单": "🟢", "中等": "🟡", "困难": "🟠", "极难": "🔴"}
    
    lines.append(f"## 📋 【{position}】面试准备方案\n")
    lines.append(f"**面试难度：** {diff_emoji.get(difficulty, '🟡')} {difficulty}\n")
    
    # 核心要求
    if job_info.get("core_requirements"):
        lines.append("### 🎯 核心要求\n")
        for req in job_info["core_requirements"]:
            lines.append(f"- {req}")
        lines.append("")
    
    # 关键技能
    if job_info.get("key_skills"):
        lines.append("### 💡 关键技能\n")
        skills = " | ".join([f"`{s}`" for s in job_info["key_skills"]])
        lines.append(skills + "\n")
    
    # 行为面试题（STAR法则）
    if jd_result.get("behavioral_questions"):
        lines.append("\n---\n")
        lines.append("### 🌟 行为面试题（STAR 法则）\n")
        for i, q in enumerate(jd_result["behavioral_questions"], 1):
            lines.append(f"**Q{i}:** {q.get('question', '')}")
            if q.get("hint"):
                lines.append(f"  💡 *提示：{q['hint']}*")
            lines.append("")
    
    # 技术深度提问
    if jd_result.get("technical_questions"):
        lines.append("---\n")
        lines.append("### 🔧 技术深度提问\n")
        for i, q in enumerate(jd_result["technical_questions"], 1):
            lines.append(f"**Q{i}:** {q.get('question', '')}")
            if q.get("follow_up"):
                lines.append(f"  🔄 *追问方向：{q['follow_up']}*")
            lines.append("")
    
    # 情景模拟题
    if jd_result.get("scenario_questions"):
        lines.append("---\n")
        lines.append("### 🎭 情景模拟题\n")
        for i, s in enumerate(jd_result["scenario_questions"], 1):
            lines.append(f"**情景 {i}:** {s.get('scenario', '')}")
            lines.append(f"  ❓ **问题：**{s.get('question', '')}")
            if s.get("expected_approach"):
                lines.append(f"  💡 **期望思路：**{s.get('expected_approach', '')}")
            lines.append("")
    
    # 反问建议
    if jd_result.get("suggested_follow_up_questions"):
        lines.append("---\n")
        lines.append("### ❓ 反问建议（展示深度思考）\n")
        for q in jd_result["suggested_follow_up_questions"]:
            lines.append(f"- {q}")
        lines.append("")
    
    # 备考建议
    if jd_result.get("preparation_tips"):
        lines.append("---\n")
        lines.append("### 📚 备考建议\n")
        for tip in jd_result["preparation_tips"]:
            lines.append(f"- {tip}")
        lines.append("")
    
    lines.append("\n---\n")
    lines.append("*💡 你可以针对任意一道题让我帮你模拟练习或提供更详细的回答思路！*")
    
    return "\n".join(lines)


@router.post("/message", summary="发送消息")
async def send_message(
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    发送消息并获取 AI 回复
    流程：
    1. 验证数字人归属
    2. 获取或创建对话
    3. 获取用户记忆（用于构建 prompt）
    4. 调用 AI 生成回复
    5. 保存消息到 messages 集合
    6. 后台触发记忆提取（不阻塞响应）
    """
    user_id = current_user["id"]

    # 验证并发
    semaphore = get_user_semaphore(user_id)
    if semaphore.locked():
        return error_response("您的请求太频繁，请稍候再试 (最多 2 个并发)", status_code=429)

    # 验证数字人
    if not validate_object_id(body.digital_person_id):
        return error_response("无效的数字人 ID", status_code=400)

    digital_person = await db["digital_persons"].find_one({
        "_id": ObjectId(body.digital_person_id),
        "user_id": ObjectId(user_id),
    })
    if not digital_person:
        return error_response("数字人不存在或无权限访问", status_code=404)

    from ..services.vision_service import VisionService

    # 清理用户输入
    cleaned_message = sanitize_input(body.message) if body.message else ""
    if not cleaned_message and not body.file_urls:
        return error_response("消息内容或文件不能为空", status_code=400)

    # 获取或创建对话
    conversation_id = body.conversation_id
    if conversation_id and validate_object_id(conversation_id):
        conversation = await db["conversations"].find_one({
            "_id": ObjectId(conversation_id),
            "user_id": ObjectId(user_id),
        })
        if not conversation:
            conversation_id = None  # 对话不存在，重新创建

    if not conversation_id:
        now = get_current_time()
        conv_doc = {
            "user_id": ObjectId(user_id),
            "digital_person_id": ObjectId(body.digital_person_id),
            "title": f"与{digital_person['name']}的对话",
            "message_count": 0,
            "last_message_at": now,
            "created_at": now,
            "updated_at": now,
        }
        result = await db["conversations"].insert_one(conv_doc)
        conversation_id = str(result.inserted_id)

    # 获取最近对话历史（用于 AI 上下文）
    # 若已有历史摘要，则只取最新 N 条（由 recent_messages_keep 控制）
    conversation_obj = None
    if conversation_id and validate_object_id(conversation_id):
        conversation_obj = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    has_summary = bool(conversation_obj and conversation_obj.get("summary"))
    msg_limit = settings.recent_messages_keep if has_summary else 12

    recent_msgs = []
    cursor = (
        db["messages"]
        .find({"conversation_id": ObjectId(conversation_id)})
        .sort("timestamp", -1)
        .limit(msg_limit)
    )
    async for msg in cursor:
        recent_msgs.append({"role": msg["role"], "content": msg["content"]})
    recent_msgs.reverse()

    # 获取与当前用户输入最相关的记忆（向量化语义检索，top5）
    memories = await _memory_service.get_relevant_memories(
        user_id=user_id,
        digital_person_id=body.digital_person_id,
        query_text=cleaned_message,
        db=db,
        top_k=5,
    )

    # 获取用户职业档案（融入 prompt）
    user_profile = await db["user_profiles"].find_one({"user_id": ObjectId(user_id)})

    # 分析用户情感
    emotion_data = _emotion_service.analyze_emotion(cleaned_message)

    # 识别场景
    scene = _prompt_service.detect_scene(cleaned_message, emotion_data["emotion"])
    interview_knowledge = ""
    weather_info = ""
    
    if scene == "interview":
        # 组合最近历史 + 记忆，用于推断用户专业
        history_text = " ".join([m["content"] for m in recent_msgs]) + " " + cleaned_message
        major = _interview_service.detect_major(history_text, memories)
        # 检测面试阶段（面试前/中/后）
        stage = _interview_service.detect_stage(cleaned_message)
        interview_knowledge = _interview_service.get_interview_knowledge(major, stage)

    # 天气查询：独立于场景，只要提取到城市就查询天气
    target_city = _weather_service.extract_city(cleaned_message)
    if target_city:
        try:
            w_info = await _weather_service.get_weather(target_city)
            if w_info:
                weather_info = w_info
        except Exception as e:
            logger.warning(f"天气查询失败（降级跳过）: {e}")

    # 取出之前存储的摘要
    history_summary = conversation_obj.get("summary", "") if conversation_obj else ""

    # 构建个性化 system prompt
    system_prompt = _prompt_service.build_persona_prompt(
        digital_person=digital_person,
        memories=memories,
        recent_messages=recent_msgs,
        user_profile=user_profile,
        scene=scene,
        history_summary=history_summary,
        weather_info=weather_info,
        interview_knowledge=interview_knowledge
    )


    # 构建 AI 消息列表
    ai_messages = list(recent_msgs)
    ai_messages.append({"role": "user", "content": cleaned_message})

    print("\n" + "="*50, flush=True)
    print(f"=== [对话流] 新消息 ===", flush=True)
    print(f"数字人ID: {body.digital_person_id}", flush=True)
    print(f"用户输入: {cleaned_message}", flush=True)
    print(f"System Prompt:\n{system_prompt}", flush=True)
    print(f"=========================", flush=True)
    print("="*50 + "\n", flush=True)

    # 调用 AI 生成回复
    if body.file_urls:
         vision_service = VisionService()
         vision_messages = vision_service.process_vision_message(cleaned_message, body.file_urls)
         
         # 检测是否是JD图片（自动识别模式）
         is_jd_image = False
         jd_text_content = ""
         
         # 如果用户没有输入文字，只上传了图片，则尝试识别是否是JD
         if not cleaned_message or len(cleaned_message) < 5:
             try:
                 # 使用视觉模型识别图片内容
                 jd_recognition_prompt = """请仔细观察这张图片，判断它是否是一份职位描述（JD/Job Description）或招聘信息。
                 
如果它是JD或招聘信息，请返回：YES|职位名称|核心内容摘要（100字以内）
如果不是JD，请返回：NO|图片类型描述"""
                 
                 jd_check_result = await _ai_service.chat_with_vision(
                     messages=[{"role": "user", "content": [{"type": "text", "text": jd_recognition_prompt}] + [msg["content"] for msg in vision_messages[0]["content"][1:] if isinstance(msg.get("content"), dict) and msg["content"].get("type") == "image_url"]}],
                     system_prompt="你是一个图像识别专家，专门识别招聘信息和职位描述。"
                 )
                 
                 logger.info(f"[JD检测] 视觉模型返回: {jd_check_result[:200]}")
                 
                 if jd_check_result and jd_check_result.upper().startswith("YES"):
                     is_jd_image = True
                     # 提取JD文本内容用于后续分析
                     parts = jd_check_result.split("|")
                     if len(parts) >= 3:
                         jd_text_content = parts[2]
                         position_name = parts[1] if len(parts) > 1 else "未知岗位"
                         logger.info(f"[JD检测] ✅ 识别为JD: {position_name}")
             except Exception as e:
                 logger.warning(f"[JD检测] 检测失败，走正常流程: {e}")
         
         if is_jd_image:
             # JD模式：先询问用户是否需要生成面试准备方案
             logger.info(f"[JD模式] 检测到JD，询问用户是否生成面试题...")
             
             try:
                 # 先获取JD基本信息
                 jd_basic_prompt = """这是一张职位描述（JD）截图。请简要提取以下信息：
- 岗位名称
- 公司名称（如有）
- 核心要求（3-5条）

请用简洁的格式返回，不要长篇大论。"""
                 
                 jd_basic_info = await _ai_service.chat_with_vision(
                     messages=[{"role": "user", "content": [{"type": "text", "text": jd_basic_prompt}] + [msg["content"] for msg in vision_messages[0]["content"][1:] if isinstance(msg.get("content"), dict) and msg["content"].get("type") == "image_url"]}],
                     system_prompt="你是一个专业的OCR文字识别助手，准确提取图片中的关键信息。"
                 )
                 
                 # 返回询问消息，不直接生成面试题
                 ai_reply = f"""📋 **我识别到这是一份职位描述（JD）**

{jd_basic_info}

---

**是否需要我为你生成完整的面试准备方案？** 包括：
- 🎯 核心要求分析
- 🌟 行为面试题（STAR法则）
- 🔧 技术深度提问
- 🎭 情景模拟题
- ❓ 反问建议
- 📚 备考建议

**回复"是"或"需要"即可生成，或者你可以先告诉我你想了解哪个方面。**"""
                 
                 # 在用户消息中标记包含JD图片
                 user_msg_doc = {
                     "conversation_id": ObjectId(conversation_id),
                     "role": "user",
                     "content": cleaned_message,
                     "emotion": emotion_data["emotion"],
                     "emotion_polarity": emotion_data["polarity"],
                     "timestamp": now,
                     "file_urls": body.file_urls,
                     "contains_jd_image": True  # 标记包含JD图片
                 }
                 await db["messages"].insert_one(user_msg_doc)
                 
                 # 保存AI回复
                 ai_emotion = _emotion_service.analyze_emotion(ai_reply)
                 ai_msg_doc = {
                     "conversation_id": ObjectId(conversation_id),
                     "role": "assistant",
                     "content": ai_reply,
                     "emotion": ai_emotion["emotion"],
                     "emotion_polarity": ai_emotion["polarity"],
                     "timestamp": get_current_time(),
                 }
                 await db["messages"].insert_one(ai_msg_doc)
                 
                 # 更新对话元数据
                 await db["conversations"].update_one(
                     {"_id": ObjectId(conversation_id)},
                     {
                         "$set": {"last_message_at": now, "updated_at": now},
                         "$inc": {"message_count": 2},
                     },
                 )
                 
                 # 后台触发记忆提取
                 background_tasks.add_task(
                     _trigger_memory_extraction,
                     user_id=user_id,
                     digital_person_id=body.digital_person_id,
                     conversation_id=conversation_id,
                     db=db,
                 )
                 
                 logger.info(f"[JD模式] ✅ 已询问用户，等待确认")
                 
                 return success_response(
                     data={
                         "reply": ai_reply,
                         "conversation_id": conversation_id,
                         "emotion": emotion_data["emotion"],
                         "emotion_polarity": emotion_data["polarity"],
                         "timestamp": now.isoformat(),
                     },
                     message="消息发送成功",
                 )
                 
             except Exception as e:
                 logger.error(f"[JD模式] ❌ 询问失败: {e}")
                 # 降级为普通对话
                 vision_history = list(recent_msgs)
                 vision_history.extend(vision_messages)
                 ai_reply = await _ai_service.chat_with_vision(vision_history, system_prompt)
         else:
             # 普通图片对话模式
             vision_history = list(recent_msgs)
             vision_history.extend(vision_messages)
             ai_reply = await _ai_service.chat_with_vision(vision_history, system_prompt)
    else:
        ai_reply = await _ai_service.chat(ai_messages, system_prompt)
        
    print(f"[对话流] AI 回复: {ai_reply}", flush=True)

    # 保存用户消息
    now = get_current_time()
    user_msg_doc = {
        "conversation_id": ObjectId(conversation_id),
        "role": "user",
        "content": cleaned_message,
        "emotion": emotion_data["emotion"],
        "emotion_polarity": emotion_data["polarity"],
        "timestamp": now,
        "file_urls": body.file_urls
    }
    await db["messages"].insert_one(user_msg_doc)

    # 保存 AI 回复
    ai_emotion = _emotion_service.analyze_emotion(ai_reply)
    ai_msg_doc = {
        "conversation_id": ObjectId(conversation_id),
        "role": "assistant",
        "content": ai_reply,
        "emotion": ai_emotion["emotion"],
        "emotion_polarity": ai_emotion["polarity"],
        "timestamp": get_current_time(),
    }
    await db["messages"].insert_one(ai_msg_doc)

    # 更新对话元数据
    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$set": {"last_message_at": now, "updated_at": now},
            "$inc": {"message_count": 2},
        },
    )

    # 后台触发记忆提取（不阻塞响应）
    background_tasks.add_task(
        _trigger_memory_extraction,
        user_id=user_id,
        digital_person_id=body.digital_person_id,
        conversation_id=conversation_id,
        db=db,
    )
    
    # 后台触发视频动态生成（懒加载模式）
    background_tasks.add_task(
        _trigger_video_generation,
        user_id=user_id,
        digital_person_id=body.digital_person_id,
        db=db,
    )
    
    # 后台触发摘要检测
    background_tasks.add_task(
        _update_conversation_summary,
        conversation_id=conversation_id,
        user_id=user_id,
        db=db,
    )

    return success_response(
        data={
            "reply": ai_reply,
            "conversation_id": conversation_id,
            "emotion": emotion_data["emotion"],
            "emotion_polarity": emotion_data["polarity"],
            "timestamp": now.isoformat(),
        },
        message="消息发送成功",
    )


@router.post("/message/stream", summary="流式发送消息（SSE）")
async def send_message_stream(
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    流式发送消息，通过 SSE（text/event-stream）逐块返回 AI 回复
    流程：
    1. 验证数字人归属
    2. 获取或创建对话
    3. 获取用户记忆构建 prompt
    4. 开启 AI 流式生成
    5. 边生成边返回给客户端
    6. 完成后保存消息 + 后台触发记忆提取
    """
    user_id = current_user["id"]

    semaphore = get_user_semaphore(user_id)
    if semaphore.locked():
        return error_response("您的请求太频繁，请稍候再试 (最多 2 个并发)", status_code=429)

    # 为了能进入流式，不在这里用 async with 阻塞整个响应。我们用 context manager 包装 generator

    # 验证数字人
    if not validate_object_id(body.digital_person_id):
        return error_response("无效的数字人 ID", status_code=400)

    digital_person = await db["digital_persons"].find_one({
        "_id": ObjectId(body.digital_person_id),
        "user_id": ObjectId(user_id),
    })
    if not digital_person:
        return error_response("数字人不存在或无权限访问", status_code=404)

    from ..services.vision_service import VisionService

    cleaned_message = sanitize_input(body.message) if body.message else ""
    if not cleaned_message and not body.file_urls:
        return error_response("消息内容或文件不能为空", status_code=400)

    # 获取或创建对话
    conversation_id = body.conversation_id
    if conversation_id and validate_object_id(conversation_id):
        conversation = await db["conversations"].find_one({
            "_id": ObjectId(conversation_id),
            "user_id": ObjectId(user_id),
        })
        if not conversation:
            conversation_id = None

    if not conversation_id:
        now = get_current_time()
        conv_doc = {
            "user_id": ObjectId(user_id),
            "digital_person_id": ObjectId(body.digital_person_id),
            "title": f"与{digital_person['name']}的对话",
            "message_count": 0,
            "last_message_at": now,
            "created_at": now,
            "updated_at": now,
        }
        result = await db["conversations"].insert_one(conv_doc)
        conversation_id = str(result.inserted_id)

    # 获取最近对话历史
    # 若已有历史摘要，则只取最新 N 条（由 recent_messages_keep 控制）
    conversation_obj = None
    if conversation_id and validate_object_id(conversation_id):
        conversation_obj = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    has_summary = bool(conversation_obj and conversation_obj.get("summary"))
    msg_limit = settings.recent_messages_keep if has_summary else 12

    recent_msgs = []
    cursor = (
        db["messages"]
        .find({"conversation_id": ObjectId(conversation_id)})
        .sort("timestamp", -1)
        .limit(msg_limit)
    )
    async for msg in cursor:
        recent_msgs.append({"role": msg["role"], "content": msg["content"]})
    recent_msgs.reverse()

    # 获取与当前用户输入最相关的记忆（向量化语义检索，top5）
    memories = await _memory_service.get_relevant_memories(
        user_id=user_id,
        digital_person_id=body.digital_person_id,
        query_text=cleaned_message,
        db=db,
        top_k=5,
    )
    user_profile = await db["user_profiles"].find_one({"user_id": ObjectId(user_id)})

    # 分析用户情感
    emotion_data = _emotion_service.analyze_emotion(cleaned_message)

    # 识别场景
    scene = _prompt_service.detect_scene(cleaned_message, emotion_data["emotion"])
    interview_knowledge = ""
    weather_info = ""
    
    if scene == "interview":
        # 组合最近历史 + 记忆，用于推断用户专业
        history_text = " ".join([m["content"] for m in recent_msgs]) + " " + cleaned_message
        major = _interview_service.detect_major(history_text, memories)
        # 检测面试阶段（面试前/中/后）
        stage = _interview_service.detect_stage(cleaned_message)
        interview_knowledge = _interview_service.get_interview_knowledge(major, stage)

    # 深度结合：如果是 JD 分析场景
    if scene == "jd_analysis" or body.is_jd_analysis:
        jd_prompt = _interview_service.generate_jd_analysis_prompt(cleaned_message)
        # 将其合并到面试知识中，或者作为独立的片段
        interview_knowledge = (interview_knowledge + "\n\n" + jd_prompt).strip()

    # 天气查询：独立于场景，只要提取到城市就查询天气
    target_city = _weather_service.extract_city(cleaned_message)
    if target_city:
        try:
            w_info = await _weather_service.get_weather(target_city)
            if w_info:
                weather_info = w_info
        except Exception as e:
            logger.warning(f"天气查询失败（降级跳过）: {e}")

    # 取出之前存储的摘要
    history_summary = conversation_obj.get("summary", "") if conversation_obj else ""

    # 构建 system prompt
    system_prompt = _prompt_service.build_persona_prompt(
        digital_person=digital_person,
        memories=memories,
        recent_messages=recent_msgs,
        user_profile=user_profile,
        scene=scene,
        history_summary=history_summary,
        weather_info=weather_info,
        interview_knowledge=interview_knowledge
    )

    # 构建 AI 消息列表
    ai_messages = list(recent_msgs)
    ai_messages.append({"role": "user", "content": cleaned_message})

    # 先保存用户消息
    now = get_current_time()
    user_msg_doc = {
        "conversation_id": ObjectId(conversation_id),
        "role": "user",
        "content": cleaned_message,
        "emotion": emotion_data["emotion"],
        "emotion_polarity": emotion_data["polarity"],
        "timestamp": now,
        "file_urls": body.file_urls
    }
    await db["messages"].insert_one(user_msg_doc)

    async def event_generator() -> AsyncGenerator[str, None]:
        """SSE 事件生成器，逐块返回 AI 回复文本"""
        # 进入流时正式获取信号量
        await semaphore.acquire()
        try:
            full_reply = []
            
            meta_payload = {
                "conversation_id": conversation_id,
                "emotion": emotion_data["emotion"],
                "emotion_polarity": emotion_data["polarity"],
                "scene": scene  # 透传场景给前端，激活特殊 UI
            }
            if scene == "interview":
                meta_payload["interview_tips"] = _interview_service.get_interview_tips_array()
            if scene == "crisis":
                meta_payload["hotlines"] = ["北京: 010-82951332", "全国: 400-161-9995"]
            if weather_info:
                meta_payload["weather_info"] = weather_info  # 透传天气数据供前端渲染天气卡片

            # 先发送 conversation_id 供客户端续接
            meta_start = json.dumps({"meta_start": meta_payload}, ensure_ascii=False)
            yield f"data: {meta_start}\n\n"

            # 流式输出 AI 回复
            if body.file_urls:
                vision_service = VisionService()
                vision_messages = vision_service.process_vision_message(cleaned_message, body.file_urls)
                # 因为多模态的消息结构不再是简单的 "role": "user", "content": "text" 
                # 我们需要组合最近的历史和当前的多模态消息
                vision_history = list(recent_msgs)
                vision_history.extend(vision_messages)

                # 将多模态消息转换为内部历史，因为这里 qwen-vl-plus 不支持 stream 我们先直接取回复
                # 然后模拟 stream 发送
                vision_reply = await _ai_service.chat_with_vision(vision_history, system_prompt)
                full_reply.append(vision_reply)
                
                # 由于我们这里是模拟流式，给客户端一点感觉
                chunk_json = json.dumps({"chunk": vision_reply}, ensure_ascii=False)
                yield f"data: {chunk_json}\n\n"
            else:
                # ✅ 真正的流式输出：每个chunk都立即发送给前端
                async for chunk_text in _ai_service.chat_stream(ai_messages, system_prompt):
                    full_reply.append(chunk_text)
                    chunk_json = json.dumps({"chunk": chunk_text}, ensure_ascii=False)
                    yield f"data: {chunk_json}\n\n"  # ← 必须在循环内yield！

            # 所有 chunk 发完后，保存 AI 回复并返回 done 信号
            ai_reply = "".join(full_reply)
            ai_emotion = _emotion_service.analyze_emotion(ai_reply)
            ai_msg_doc = {
                "conversation_id": ObjectId(conversation_id),
                "role": "assistant",
                "content": ai_reply,
                "emotion": ai_emotion["emotion"],
                "emotion_polarity": ai_emotion["polarity"],
                "timestamp": get_current_time(),
            }
            await db["messages"].insert_one(ai_msg_doc)

            # 更新对话元数据
            t_now = get_current_time()
            await db["conversations"].update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$set": {"last_message_at": t_now, "updated_at": t_now},
                    "$inc": {"message_count": 2},
                },
            )

            # 危机场景：流结束后额外推送 crisis 帧，触发前端弹窗
            if scene == "crisis":
                crisis_json = json.dumps({
                    "type": "crisis",
                    "hotlines": ["北京: 010-82951332", "全国: 400-161-9995"],
                    "message": "如果你正在经历痛苦，请记住你并不孤单。以下是专业心理援助热线，随时可以拨打。"
                }, ensure_ascii=False)
                yield f"data: {crisis_json}\n\n"

            # 结束标志（附带最终情感数据）
            done_json = json.dumps({
                "done": True,
                "emotion": ai_emotion["emotion"],
                "timestamp": t_now.isoformat(),
            }, ensure_ascii=False)
            yield f"data: {done_json}\n\n"

            # 后台触发记忆提取
            asyncio.ensure_future(_trigger_memory_extraction(
                user_id=user_id,
                digital_person_id=body.digital_person_id,
                conversation_id=conversation_id,
                db=db,
            ))
            # 后台触发视频生成
            asyncio.ensure_future(_trigger_video_generation(
                user_id=user_id,
                digital_person_id=body.digital_person_id,
                db=db,
            ))
            # 后台触发摘要检测
            asyncio.ensure_future(_update_conversation_summary(
                conversation_id=conversation_id,
                user_id=user_id,
                db=db,
            ))

        except Exception as e:
            logger.error(f"流式响应生成异常: {e}", exc_info=True)
            err_json = json.dumps({"error": "AI 服务出错，请重试"}, ensure_ascii=False)
            yield f"data: {err_json}\n\n"
        finally:
            semaphore.release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/", summary="获取当前用户的对话列表")
async def list_conversations(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取当前用户的所有对话（按最后更新时间降序）"""
    conversations = []
    cursor = (
        db["conversations"]
        .find({"user_id": ObjectId(current_user["id"])})
        .sort("updated_at", -1)
        .limit(50)
    )

    async for conv in cursor:
        conversations.append({
            "id": str(conv["_id"]),
            "digital_person_id": str(conv["digital_person_id"]),
            "title": conv.get("title", "对话"),
            "message_count": conv.get("message_count", 0),
            "last_message_at": conv["last_message_at"].isoformat()
            if isinstance(conv.get("last_message_at"), datetime)
            else conv.get("last_message_at"),
            "created_at": conv["created_at"].isoformat()
            if isinstance(conv.get("created_at"), datetime)
            else conv.get("created_at"),
        })

    return success_response(data=conversations)


@router.get("/{conversation_id}", summary="获取对话详情及消息历史")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取指定对话的详情和消息历史"""
    if not validate_object_id(conversation_id):
        return error_response("无效的对话 ID", status_code=400)

    conversation = await db["conversations"].find_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if not conversation:
        return error_response("对话不存在", status_code=404)

    # 获取消息列表
    messages = []
    
    if conversation.get("summary"):
        messages.append({
            "id": "summary_msg",
            "role": "system",
            "content": f"【前情提要】\n{conversation['summary']}",
            "emotion": "平静",
            "emotion_polarity": "neutral",
            "timestamp": conversation["created_at"].isoformat() if isinstance(conversation.get("created_at"), datetime) else conversation.get("created_at"),
        })

    cursor = (
        db["messages"]
        .find({"conversation_id": ObjectId(conversation_id)})
        .sort("timestamp", 1)
        # 不限制消息数量，加载全部历史消息
    )
    messages = []
    async for msg in cursor:
        messages.append({
            "id": str(msg["_id"]),
            "role": msg["role"],
            "content": msg["content"],
            "emotion": msg.get("emotion", "平静"),
            "emotion_polarity": msg.get("emotion_polarity", "neutral"),
            "timestamp": msg["timestamp"].isoformat()
            if isinstance(msg.get("timestamp"), datetime)
            else msg.get("timestamp"),
            # 包含附件URL列表（图片/视频）
            "file_urls": msg.get("file_urls", []),
        })

    return success_response(data={
        "id": str(conversation["_id"]),
        "digital_person_id": str(conversation["digital_person_id"]),
        "title": conversation.get("title", "对话"),
        "message_count": conversation.get("message_count", 0),
        "messages": messages,
        "created_at": conversation["created_at"].isoformat()
        if isinstance(conversation.get("created_at"), datetime)
        else conversation.get("created_at"),
    })


@router.delete("/{conversation_id}/messages/{message_id}", summary="删除单条消息")
async def delete_message(
    conversation_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """删除对话中的单条消息"""
    if not validate_object_id(conversation_id) or not validate_object_id(message_id):
        return error_response("无效的ID", status_code=400)

    # 验证对话归属
    conversation = await db["conversations"].find_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if not conversation:
        return error_response("对话不存在或无权限访问", status_code=404)

    # 删除消息
    result = await db["messages"].delete_one({
        "_id": ObjectId(message_id),
        "conversation_id": ObjectId(conversation_id),
    })
    
    if result.deleted_count == 0:
        return error_response("消息不存在", status_code=404)

    # 更新对话的消息计数
    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {"$inc": {"message_count": -1}}
    )

    logger.info(f"用户 {current_user['id']} 删除了消息 {message_id}")
    return success_response(message="消息已删除")


@router.delete("/{conversation_id}", summary="删除对话")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """删除对话及其所有消息"""
    if not validate_object_id(conversation_id):
        return error_response("无效的对话 ID", status_code=400)

    result = await db["conversations"].delete_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if result.deleted_count == 0:
        return error_response("对话不存在", status_code=404)

    # 删除关联消息
    await db["messages"].delete_many({"conversation_id": ObjectId(conversation_id)})

    return success_response(message="对话已删除")

from fastapi import UploadFile, File
import os
import time
import shutil

@router.post("/upload", summary="上传聊天图片/视频附件")
async def upload_chat_file_endpoint(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    if not file:
        return error_response("未上传文件", status_code=400)
        
    try:
        # 定义上传目录为内部 static 目录
        upload_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "chat")
        os.makedirs(upload_dir, exist_ok=True)
        
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi"]:
             return error_response(f"不支持的文件类型: {file_ext}", status_code=400)
             
        # 文件大小校验简单处理（实际应在后端接收时截断，此处为简略防范）
        # config.py 中有限制，这里可以直接依赖前端校验或后续流式读取校验
        
        safe_filename = f"chat_{current_user['id']}_{int(time.time())}{file_ext}"
        filepath = os.path.join(upload_dir, safe_filename)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_url = f"/static/uploads/chat/{safe_filename}"
        
        return success_response(
            data={"url": file_url, "type": "video" if file_ext in [".mp4", ".mov", ".avi"] else "image"},
            message="上传成功"
        )
    except Exception as e:
        logger.error(f"聊天附件上传失败: {e}", exc_info=True)
        return error_response(f"文件上传内部错误: {str(e)}", status_code=500)


class AnalyzeJDRequest(BaseModel):
    jd_text: str = Field(default="", description="JD 职位描述文本")
    digital_person_id: str = Field(..., description="数字人 ID")
    include_mock_plan: Optional[bool] = Field(default=True, description="是否包含模拟面试计划")
    file_urls: Optional[list[str]] = Field(default=None, description="上传的JD截图URL列表")


@router.post("/analyze-jd", summary="分析 JD 并生成面试辅助方案")
async def analyze_jd_endpoint(
    body: AnalyzeJDRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    JD 智能分析 API
    接收 JD 文本，返回结构化面试辅助数据：
    1. 岗位解析（核心要求、关键技能、难度评估）
    2. 企业级行为面试题（STAR 法则）
    3. 技术栈深度提问
    4. 情景模拟题
    5. 反问建议
    6. （可选）模拟面试计划
    """
    user_id = current_user["id"]

    # 验证数字人归属
    if not validate_object_id(body.digital_person_id):
        return error_response("无效的数字人 ID", status_code=400)

    digital_person = await db["digital_persons"].find_one({
        "_id": ObjectId(body.digital_person_id),
        "user_id": ObjectId(user_id),
    })
    if not digital_person:
        return error_response("数字人不存在或无权限访问", status_code=404)

    try:
        jd_text = sanitize_input(body.jd_text)
        
        # 如果有上传的JD图片，使用视觉模型直接分析（比OCR更智能）
        if body.file_urls and len(body.file_urls) > 0:
            logger.info(f"检测到JD截图，使用视觉模型直接分析: {body.file_urls}")
            
            try:
                from ..services.vision_service import VisionService
                vision_service = VisionService()
                
                # 构建视觉消息：让AI直接从图片中提取并分析JD内容
                vision_messages = vision_service.process_vision_message(
                    text="""你是一位专业的HR和面试辅导专家。请仔细分析这张职位描述(JD)截图，完成以下任务：
1. 提取完整的岗位信息（公司、岗位名称、职责、要求等）
2. 分析核心技能要求和面试难度
3. 识别关键关键词

请以结构化的JSON格式返回分析结果。""",
                    file_urls=body.file_urls
                )
                
                # 使用视觉模型获取JD分析结果
                system_prompt = """你是专业的面试辅导AI助手。用户上传了职位描述(JD)截图，你需要：
1. 准确识别图片中的所有文字信息
2. 分析岗位职责和任职要求
3. 提取核心技能标签
4. 评估面试难度
5. 给出针对性的面试准备建议"""
                
                jd_analysis_from_image = await _ai_service.chat_with_vision(
                    messages=vision_messages,
                    system_prompt=system_prompt
                )
                
                # 将视觉分析结果附加到jd_text中
                if jd_analysis_from_image and jd_analysis_from_image != "抱歉，由于网络或模型问题，我现在无法识别多模态消息，请稍后再试。":
                    if jd_text:
                        jd_text = f"{jd_text}\n\n【AI视觉模型对JD截图的分析】:\n{jd_analysis_from_image}"
                    else:
                        jd_text = jd_analysis_from_image
                    
                    logger.info(f"视觉模型成功分析JD截图，结果长度: {len(jd_text)}")
                else:
                    logger.warning("视觉模型分析失败，将尝试使用原始文本")
                    
            except Exception as e:
                logger.error(f"视觉模型处理JD图片失败: {e}", exc_info=True)
        
        # 验证最终是否有可用的JD内容
        if not jd_text or len(jd_text.strip()) < 10:
            return error_response("请提供有效的JD内容（文字或截图）", status_code=400)
        
        # 1. 生成完整的面试题方案
        interview_data = await _interview_service.generate_jd_interview_questions(
            jd_text=jd_text,
            ai_service=_ai_service
        )

        if "error" in interview_data:
            return error_response(interview_data["error"], status_code=500)

        result = {
            "job_analysis": interview_data.get("job_analysis", {}),
            "behavioral_questions": interview_data.get("behavioral_questions", []),
            "technical_questions": interview_data.get("technical_questions", []),
            "scenario_questions": interview_data.get("scenario_questions", []),
            "suggested_follow_up_questions": interview_data.get("suggested_follow_up_questions", []),
            "preparation_tips": interview_data.get("preparation_tips", []),
        }

        # 2. 如果有技术栈，额外生成深度技术题
        tech_stack = []
        job_analysis = interview_data.get("job_analysis", {})
        if job_analysis.get("key_skills"):
            tech_stack = job_analysis["key_skills"][:8]  # 取前8个关键技能

        if tech_stack and len(tech_stack) >= 3:
            tech_questions = await _interview_service.generate_tech_stack_questions(
                tech_stack=tech_stack,
                ai_service=_ai_service
            )
            result["tech_stack_deep_dive"] = tech_questions

        # 3. 可选：生成模拟面试计划
        if body.include_mock_plan:
            mock_plan = await _interview_service.generate_mock_interview_plan(
                jd_text=jd_text,
                ai_service=_ai_service,
                duration_minutes=30
            )
            if "error" not in mock_plan:
                result["mock_interview_plan"] = mock_plan

        logger.info(f"JD 分析完成，用户: {user_id}, 岗位: {job_analysis.get('position', '未知')}")

        return success_response(
            data=result,
            message="JD 分析完成"
        )

    except Exception as e:
        logger.error(f"JD 分析失败: {e}", exc_info=True)
        return error_response(f"JD 分析内部错误: {str(e)}", status_code=500)


@router.get("/video-generation/status", summary="查询视频生成功能状态")
async def get_video_generation_status():
    """
    查询视频生成功能的开关状态
    返回：
    - enabled: 是否开启
    - reason: 关闭原因（如果关闭）
    - how_to_enable: 如何开启的说明
    """
    from ..config import settings
    
    return success_response(
        data={
            "enabled": settings.video_generation_enabled,
            "reason": settings.video_generation_reason if not settings.video_generation_enabled else "功能已开启",
            "how_to_enable": "在 .env 文件中添加：VIDEO_GENERATION_ENABLED=True，然后重启后端服务"
        },
        message="查询成功"
    )
