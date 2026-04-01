import logging
from app.config import settings

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.api_key = settings.ai_api_key
        self.api_base = settings.ai_base_url
        self.model_name = settings.vision_model
    
    def process_vision_message(self, text: str, file_urls: list) -> list:
        """
        构建兼容 OpenAI 格式的 Vision Message
        qwen-vl-plus 支持传入图片和视频的 URL
        """
        content = [{"type": "text", "text": text}]
        
        for url in file_urls:
            # 简单判断，实际应用中可以看 MIME type
            if url.lower().endswith(('.mp4', '.avi', '.mov')):
                content.append({"type": "video_url", "video_url": {"url": url}})
                logger.info(f"Attached video to vision message: {url}")
            else:
                content.append({"type": "image_url", "image_url": {"url": url}})
                logger.info(f"Attached image to vision message: {url}")
                
        return [{
            "role": "user",
            "content": content
        }]
