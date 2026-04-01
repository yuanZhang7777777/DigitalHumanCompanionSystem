"""
FastAPI 应用主入口
挂载所有路由，配置 CORS 中间件，注册启动/关闭事件
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .config import settings
from .database import connect_to_mongo, close_mongo_connection
from .routers import auth, digital_person, conversation, memory, profile, tts, extraction

# 配置日志格式 (force=True 强制覆盖 uvicorn 默认的 root handler配置，避免日志丢失)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True, 
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时连接数据库，关闭时断开"""
    logger.info(f"启动 {settings.app_name} v{settings.app_version}")
    await connect_to_mongo()
    yield
    await close_mongo_connection()
    logger.info("应用已关闭")


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="数字人情感陪伴系统 API - 为大学毕业生提供情感支持和职业建议",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 配置 CORS 中间件（开发环境允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(auth.router)
app.include_router(digital_person.router)
app.include_router(conversation.router)
app.include_router(memory.router)
app.include_router(profile.router)
app.include_router(tts.router)
app.include_router(extraction.router, prefix="/api", tags=["Extraction"])

@app.get("/", tags=["系统"])
async def root():
    """API 根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "message": "系统运行正常"}