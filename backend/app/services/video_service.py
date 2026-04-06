# TIMESTAMP: 2026-02-23 19:42:00 (v4.0-rest-beijing-fix)
import json
import os
import time
import asyncio
import logging
import httpx
import oss2

from ..config import settings

logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self):
        print("=== [CRITICAL INFO] VIDEO SERVICE INITIALIZED VERSION 4.1 (REST-BEIJING-SAFENET) ===")
        # 阿里云 OSS 配置并强制清洗空格
        self.oss_endpoint = os.environ.get("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com").strip()
        self.oss_bucket_name = os.environ.get("OSS_BUCKET_NAME", "lxczai").strip()
        self.access_key_id = os.environ.get("OSS_ACCESS_KEY_ID", "").strip()
        self.access_key_secret = os.environ.get("OSS_ACCESS_KEY_SECRET", "").strip()
        self.dashscope_api_key = (os.environ.get("AI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")).strip()

    def _get_oss_bucket(self):
        if not self.access_key_id or not self.access_key_secret:
            raise ValueError("Missing OSS credentials")
        auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        return oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)

    async def upload_file_to_oss(self, file_content: bytes, filename: str, content_type: str = "video/mp4") -> str:
        """从二进制内容上传文件到 OSS"""
        bucket = self._get_oss_bucket()
        headers = {
            'x-oss-object-acl': oss2.OBJECT_ACL_PUBLIC_READ,
            'Content-Disposition': 'inline',
            'Content-Type': content_type
        }
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: bucket.put_object(filename, file_content, headers=headers))
        
        ext_endpoint = self.oss_endpoint.replace("http://", "").replace("https://", "")
        if ext_endpoint.startswith(self.oss_bucket_name + "."):
            public_url = f"https://{ext_endpoint}/{filename}"
        else:
            public_url = f"https://{self.oss_bucket_name}.{ext_endpoint}/{filename}"
        
        return public_url.strip().replace("\n", "").replace("\r", "")

    def upload_to_oss_sync(self, local_file_path: str, object_name: str) -> str:
        bucket = self._get_oss_bucket()
        # 显式设置 inline，虽然 REST 通道对这个不敏感，但为了预览一致性保留
        headers = {
            'x-oss-object-acl': oss2.OBJECT_ACL_PUBLIC_READ,
            'Content-Disposition': 'inline'
        }
        if local_file_path.endswith('.mp3'):
            headers['Content-Type'] = 'audio/mpeg'
        elif local_file_path.endswith('.mp4'):
            headers['Content-Type'] = 'video/mp4'
        elif local_file_path.endswith('.jpg') or local_file_path.endswith('.jpeg'):
            headers['Content-Type'] = 'image/jpeg'
        elif local_file_path.endswith('.png'):
            headers['Content-Type'] = 'image/png'

        logger.info(f"[OSS] Uploading {local_file_path} to {object_name}...")
        bucket.put_object_from_file(object_name, local_file_path, headers=headers)
        
        ext_endpoint = self.oss_endpoint.replace("http://", "").replace("https://", "")
        if ext_endpoint.startswith(self.oss_bucket_name + "."):
            public_url = f"https://{ext_endpoint}/{object_name}"
        else:
            public_url = f"https://{self.oss_bucket_name}.{ext_endpoint}/{object_name}"
        
        # 彻底清洗掉任何不可见的空格或换行等非法字符
        public_url = public_url.strip().replace("\n", "").replace("\r", "")
        return public_url

    async def generate_generic_talking_head(self, user_id: str, avatar_local_path: str, audio_local_path: str) -> str:
        """
        核心方法：使用 REST API 调用万象 (wan2.2-s2v) 视频合成 (北京端点)
        
        开关控制：
        - 默认关闭（节省费用）
        - 开启方式：在 .env 文件中设置 VIDEO_GENERATION_ENABLED=True
        """
        # 检查视频生成开关
        if not settings.video_generation_enabled:
            logger.warning(f"[视频生成] ⚠️ 功能已关闭：{settings.video_generation_reason}")
            raise Exception(settings.video_generation_reason)
        
        logger.info(f"[视频生成] ✅ 功能已开启，开始处理请求...")
