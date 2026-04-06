"""
应用配置模块
使用 pydantic-settings 管理所有环境变量配置
"""
from pydantic_settings import BaseSettings
from pydantic import Field
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # ── 数据库配置 ──────────────────────────────────────────────────────────
    database_url: str = Field(default="mongodb://localhost:27017", alias="DATABASE_URL")
    database_name: str = Field(default="digital_companion", alias="DATABASE_NAME")

    # ── AI 模型配置 ─────────────────────────────────────────────────────────
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_model: str = Field(default="qwen-plus", alias="AI_MODEL")
    ai_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="AI_BASE_URL"
    )
    ai_max_tokens: int = Field(default=1500, alias="AI_MAX_TOKENS")
    ai_temperature: float = Field(default=0.75, alias="AI_TEMPERATURE")
    gpt_sovits_api_url: str = Field(default="http://127.0.0.1:9880/tts", alias="GPT_SOVITS_API_URL")

    # ── 视觉多模态模型配置（图片/视频理解）─────────────────────────────────
    vision_model: str = Field(default="qwen-vl-plus", alias="VISION_MODEL")  # 阿里云视觉语言模型
    vision_max_image_size_mb: int = Field(default=2, alias="VISION_MAX_IMAGE_SIZE_MB") # 缩小至 2MB 控制成本
    vision_max_video_size_mb: int = Field(default=10, alias="VISION_MAX_VIDEO_SIZE_MB") # 缩小至 10MB 控制成本

    # ── 智能语音识别配置（DashScope Paraformer 实时 ASR）────────────────────
    dashscope_asr_model: str = Field(default="paraformer-realtime-v2", alias="DASHSCOPE_ASR_MODEL")

    # ── 高德天气 API 配置 ────────────────────────────────────────────────────
    amap_api_key: str = Field(default="", alias="AMAP_API_KEY")  # 高德开放平台 Web 服务 Key
    amap_weather_url: str = Field(
        default="https://restapi.amap.com/v3/weather/weatherInfo",
        alias="AMAP_WEATHER_URL"
    )
    amap_geocode_url: str = Field(
        default="https://restapi.amap.com/v3/geocode/geo",
        alias="AMAP_GEOCODE_URL"
    )

    # ── JWT 认证配置 ────────────────────────────────────────────────────────
    secret_key: str = Field(default="change-me-in-production-32chars!!", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, alias="ACCESS_TOKEN_EXPIRE_MINUTES")  # 7天

    # ── 记忆提取配置 ────────────────────────────────────────────────────────
    memory_extract_threshold: int = Field(default=10, alias="MEMORY_EXTRACT_THRESHOLD")  # 每N条消息触发提取
    memory_similarity_threshold: float = Field(default=0.85, alias="MEMORY_SIMILARITY_THRESHOLD")  # 去重阈值

    # ── 历史消息摘要配置 ─────────────────────────────────────────────────────
    history_summary_threshold: int = Field(default=20, alias="HISTORY_SUMMARY_THRESHOLD")  # 超过N条触发摘要
    recent_messages_keep: int = Field(default=8, alias="RECENT_MESSAGES_KEEP")  # 摘要后保留最新N条

    # ── 限流配置 ─────────────────────────────────────────────────────────────
    max_concurrent_per_user: int = Field(default=2, alias="MAX_CONCURRENT_PER_USER")  # 每用户最大并发数

    # ── 视频生成配置 ────────────────────────────────────────────────────────
    video_generation_enabled: bool = Field(default=False, alias="VIDEO_GENERATION_ENABLED")  # 视频生成开关（默认关闭）
    video_generation_reason: str = "因近期视频生成费用较高，系统默认关闭视频生成功能。如需开启，请修改 .env 文件设置 VIDEO_GENERATION_ENABLED=True"

    # ── 应用配置 ────────────────────────────────────────────────────────────
    app_name: str = "在 · 数字人情感陪伴系统"
    app_version: str = "2.0.0"
    debug: bool = Field(default=False, alias="DEBUG")
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://localhost:3000",
    ]

    class Config:
        env_file = ".env"
        populate_by_name = True


# 全局单例配置对象
settings = Settings()