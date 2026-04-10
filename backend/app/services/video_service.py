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
        self.dashscope_api_key = (settings.video_api_key or os.environ.get("AI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")).strip()

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
        核心方法：使用 REST API 调用阿里云万象 (wan2.1-i2v-turbo) 图生视频接口
        
        开关控制：
        - 默认关闭（节省费用）
        - 开启方式：在 .env 文件中设置 VIDEO_GENERATION_ENABLED=True
        
        流程：
        1. 上传头像图片到 OSS 获取公开 URL
        2. 调用万象图生视频 API 提交任务
        3. 轮询任务状态直到完成
        4. 下载生成的视频并上传到 OSS 永久保存
        5. 返回永久视频 URL
        """
        # 检查视频生成开关
        if not settings.video_generation_enabled:
            logger.warning(f"[视频生成] ⚠️ 功能已关闭：{settings.video_generation_reason}")
            raise Exception(settings.video_generation_reason)

        logger.info(f"[视频生成] ✅ 功能已开启，开始处理请求...")

        # ── Step 1: 上传头像到 OSS，获取公开图片 URL ───────────────────────
        avatar_object_name = f"avatars/input_{user_id}_{int(time.time())}.jpg"
        logger.info(f"[视频生成] Step1: 上传头像到 OSS: {avatar_object_name}")
        loop = asyncio.get_event_loop()
        image_url = await loop.run_in_executor(
            None, self.upload_to_oss_sync, avatar_local_path, avatar_object_name
        )
        logger.info(f"[视频生成] 头像 OSS URL: {image_url}")

        # ── Step 2: 调用万象图生视频 API ────────────────────────────────────
        api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
        headers = {
            "Authorization": f"Bearer {self.dashscope_api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",  # 必须异步提交
        }
        payload = {
            "model": "wan2.6-i2v-flash",  # 最新百炼图生视频万象模型
            "input": {
                "img_url": image_url,
                "prompt": "a person speaking naturally, slight head movement, realistic, cinematic",
            },
            "parameters": {
                "size": "480*832",   # 竖屏 9:16 比例，适合数字人展示
                "duration": 5,       # 生成 5 秒视频
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            logger.info(f"[视频生成] Step2: 提交视频生成任务...")
            resp = await client.post(api_url, headers=headers, json=payload)

        if resp.status_code not in (200, 202):
            raise Exception(f"视频生成任务提交失败，HTTP {resp.status_code}: {resp.text}")

        task_data = resp.json()
        task_id = task_data.get("output", {}).get("task_id")
        if not task_id:
            raise Exception(f"未获取到 task_id，响应内容: {task_data}")

        logger.info(f"[视频生成] 任务提交成功，task_id={task_id}")

        # ── Step 3: 轮询任务状态直到完成 ────────────────────────────────────
        poll_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        poll_headers = {"Authorization": f"Bearer {self.dashscope_api_key}"}
        video_download_url = None
        max_wait_seconds = 300   # 最多等待 5 分钟
        poll_interval = 10       # 每 10 秒轮询一次
        elapsed = 0

        while elapsed < max_wait_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            async with httpx.AsyncClient(timeout=30) as client:
                poll_resp = await client.get(poll_url, headers=poll_headers)

            poll_data = poll_resp.json()
            task_status = poll_data.get("output", {}).get("task_status", "")
            logger.info(f"[视频生成] 轮询状态（{elapsed}s）: {task_status}")

            if task_status == "SUCCEEDED":
                # 取出视频 URL（万象返回的是临时下载地址）
                video_download_url = poll_data.get("output", {}).get("video_url")
                if not video_download_url:
                    # 兼容返回列表格式
                    videos = poll_data.get("output", {}).get("videos", [])
                    if videos:
                        video_download_url = videos[0].get("url")
                break
            elif task_status in ("FAILED", "CANCELED"):
                err_msg = poll_data.get("output", {}).get("message", "未知错误")
                raise Exception(f"视频生成任务失败: {err_msg}")
            # 其余状态（PENDING / RUNNING）继续等待

        if not video_download_url:
            raise Exception(f"视频生成超时（已等待 {max_wait_seconds}s），task_id={task_id}")

        logger.info(f"[视频生成] Step3: 任务完成，临时下载地址: {video_download_url[:80]}...")

        # ── Step 4: 下载视频并上传到 OSS 永久保存 ───────────────────────────
        logger.info(f"[视频生成] Step4: 下载视频并上传到 OSS 永久保存...")
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            video_resp = await client.get(video_download_url)

        if video_resp.status_code != 200:
            raise Exception(f"下载视频失败，HTTP {video_resp.status_code}")

        video_bytes = video_resp.content
        video_object_name = f"videos/speaking_{user_id}_{int(time.time())}.mp4"
        permanent_url = await self.upload_file_to_oss(video_bytes, video_object_name, content_type="video/mp4")

        logger.info(f"[视频生成] ✅ 全部完成，永久 OSS URL: {permanent_url}")
        return permanent_url
