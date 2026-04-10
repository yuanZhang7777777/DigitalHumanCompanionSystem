import logging
import base64
import os
from app.config import settings

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.api_key = settings.ai_api_key
        self.api_base = settings.ai_base_url
        self.model_name = settings.vision_model
    
    def _get_full_url(self, url: str) -> str:
        """
        将相对路径转换为完整URL
        /static/uploads/chat/xxx.jpg → http://localhost:8000/static/uploads/chat/xxx.jpg
        """
        if not url:
            return url
        
        # 如果已经是完整URL，直接返回
        if url.startswith('http://') or url.startswith('https://') or url.startswith('data:'):
            return url
        
        # 获取服务器基础URL（从配置或请求上下文）
        # 开发环境默认使用 localhost:8000
        base_url = getattr(settings, 'server_base_url', 'http://127.0.0.1:8000')
        
        # 确保路径以 / 开头
        if not url.startswith('/'):
            url = '/' + url
            
        full_url = f"{base_url}{url}"
        logger.info(f"转换图片URL: {url} → {full_url}")
        return full_url
    
    def _image_to_base64(self, file_path: str) -> str:
        """
        将本地图片文件转换为 base64 格式
        用于 AI API 无法访问本地服务器时
        """
        try:
            # 转换为实际文件系统路径
            if file_path.startswith('/static/') or file_path.startswith('/static\\'):
                # 相对路径转绝对路径：/static/uploads/chat/xxx.jpg → backend/app/static/uploads/chat/xxx.jpg
                relative_path = file_path.replace('/', os.sep).lstrip(os.sep)
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                full_path = os.path.join(base_dir, relative_path)
            else:
                full_path = file_path
            
            if not os.path.exists(full_path):
                logger.error(f"图片文件不存在: {full_path}")
                return None
            
            # 读取并编码
            with open(full_path, 'rb') as f:
                image_data = f.read()
                
            # 判断图片类型
            ext = os.path.splitext(full_path)[1].lower()
            mime_types = {
                '.jpg': 'jpeg', '.jpeg': 'jpeg',
                '.png': 'png', '.gif': 'gif',
                '.webp': 'webp', '.bmp': 'bmp'
            }
            mime_type = mime_types.get(ext, 'jpeg')
            
            b64 = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/{mime_type};base64,{b64}"
            
            logger.info(f"图片转换为base64成功: {full_path} (大小: {len(image_data)/1024:.1f}KB)")
            return data_url
            
        except Exception as e:
            logger.error(f"图片转换为base64失败: {e}")
            return None
    
    def process_vision_message(self, text: str, file_urls: list) -> list:
        """
        构建兼容 OpenAI 格式的 Vision Message
        qwen-vl-plus 支持传入图片和视频的 URL 或 base64
        """
        content = [{"type": "text", "text": text or "请描述这张图片的内容"}]
        
        for url in file_urls:
            full_url = self._get_full_url(url)
            
            # 简单判断，实际应用中可以看 MIME type
            if url.lower().endswith(('.mp4', '.avi', '.mov')):
                content.append({"type": "video_url", "video_url": {"url": full_url}})
                logger.info(f"附加视频到视觉消息: {full_url}")
            else:
                # 尝试使用完整URL，如果不可用则使用base64
                image_url = full_url
                
                # 检查是否需要使用base64（本地开发环境）
                if 'localhost' in full_url or '127.0.0.1' in full_url:
                    logger.info("检测到本地环境，尝试将图片转为base64格式")
                    b64_data = self._image_to_base64(url)
                    if b64_data:
                        image_url = b64_data
                    else:
                        logger.warning("base64转换失败，仍使用原始URL")
                
                content.append({"type": "image_url", "image_url": {"url": image_url}})
                logger.info(f"附加图片到视觉消息: {url[:50]}... (模式: {'base64' if image_url.startswith('data:') else 'URL'})")
                
        return [{
            "role": "user",
            "content": content
        }]
